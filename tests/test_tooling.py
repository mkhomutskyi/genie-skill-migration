from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import pytest
import yaml

from portable_genie_skills.cli import main
from portable_genie_skills.core import adapt_skill, check_skill, scan_path, validate_skill

REPOSITORY = Path(__file__).resolve().parents[1]
CUSTOM_SKILLS = (
    "business-pulse",
    "cost-investigator",
    "solution-planner",
    "technical-answer",
    "workload-radar",
)
RUNTIME_VARIANTS = ("genie", "cursor", "claude-code")


def variant_dir(skill_name: str, runtime: str) -> Path:
    if runtime == "genie":
        return REPOSITORY / "skills" / skill_name
    return REPOSITORY / "other-runtimes" / runtime / skill_name


def make_skill(
    root: Path,
    *,
    body: str = "# Instructions\n\nFollow the documented review process.\n",
    extra_frontmatter: str = "",
) -> Path:
    root.mkdir()
    header = (
        "---\n"
        f"name: {root.name}\n"
        "description: A portable process for reviewing supplied material.\n"
        f"{extra_frontmatter}"
        "---\n"
    )
    (root / "SKILL.md").write_text(header + body, encoding="utf-8")
    return root


def blocker_codes(path: Path) -> set[str]:
    return {finding.code for finding in validate_skill(path).blockers}


def test_successful_simple_adaptation(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "simple-skill",
        extra_frontmatter="disable-model-invocation: true\n",
    )
    references = source / "references"
    references.mkdir()
    (references / "guide.md").write_text(
        "# Guide\n\nReview the supplied facts.\n",
        encoding="utf-8",
    )
    skill_file = source / "SKILL.md"
    skill_file.write_text(
        skill_file.read_text(encoding="utf-8") + "\nSee [the guide](references/guide.md).\n",
        encoding="utf-8",
    )

    destination = tmp_path / "adapted"
    report = adapt_skill(source, destination, "cursor")

    assert report.ok
    assert report.source_sha256
    assert report.destination_sha256
    assert report.copied_files == ["SKILL.md", "references/guide.md"]
    assert [item["field"] for item in report.removed_fields] == [
        "disable-model-invocation",
    ]
    assert [warning.code for warning in report.warnings] == ["frontmatter.removed-runtime-field"]
    adapted = (destination / "SKILL.md").read_text(encoding="utf-8")
    header = yaml.safe_load(adapted.split("---", 2)[1])
    assert header == {
        "name": "simple-skill",
        "description": "A portable process for reviewing supplied material.",
    }
    assert "disable-model-invocation" not in adapted
    assert not ((destination / "SKILL.md").stat().st_mode & 0o111)


def test_claude_code_frontmatter_is_removed_with_warning(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "claude-skill",
        extra_frontmatter="allowed-tools: Read, Grep\nargument-hint: '[question]'\n",
    )

    report = adapt_skill(source, tmp_path / "adapted", "claude-code")

    assert report.ok
    assert [item["field"] for item in report.removed_fields] == [
        "allowed-tools",
        "argument-hint",
    ]
    assert len(report.warnings) == 2


def test_source_runtime_mismatch_is_rejected(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "mismatched-skill",
        extra_frontmatter="allowed-tools: Read\n",
    )

    report = adapt_skill(source, tmp_path / "adapted", "cursor")

    assert "frontmatter.source-runtime-mismatch" in {finding.code for finding in report.blockers}
    assert not (tmp_path / "adapted").exists()


def test_cli_writes_json_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = make_skill(tmp_path / "cli-skill")
    destination = tmp_path / "output"
    report_path = tmp_path / "report.json"

    exit_code = main(
        [
            "adapt",
            str(source),
            str(destination),
            "--source-runtime",
            "claude-code",
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 0
    disk_report = json.loads(report_path.read_text(encoding="utf-8"))
    stdout_report = json.loads(capsys.readouterr().out)
    assert disk_report == stdout_report
    assert disk_report["status"] == "accepted"


def test_report_cannot_be_written_inside_skill(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "report-skill")
    destination = tmp_path / "output"
    report_path = source / "report.json"

    exit_code = main(
        [
            "adapt",
            str(source),
            str(destination),
            "--source-runtime",
            "cursor",
            "--report",
            str(report_path),
        ]
    )

    assert exit_code == 1
    assert not report_path.exists()
    assert not destination.exists()


def test_reports_are_deterministic(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "stable-skill")

    first = validate_skill(source)
    second = validate_skill(source)

    assert first.to_json() == second.to_json()
    assert first.to_markdown() == second.to_markdown()


def test_all_supported_relative_reference_forms(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "reference-skill",
        body=(
            "# References\n\n"
            "Read [the guide](references/guide.md#review).\n"
            "Use [the checklist][check].\n"
            "![Diagram](assets/diagram.txt)\n"
            '<a href="references/guide.md">Guide</a>\n'
            "[check]: references/checklist.md\n"
        ),
    )
    (source / "references").mkdir()
    (source / "references" / "guide.md").write_text("# Review\n", encoding="utf-8")
    (source / "references" / "checklist.md").write_text("# Checklist\n", encoding="utf-8")
    (source / "assets").mkdir()
    (source / "assets" / "diagram.txt").write_text("diagram placeholder\n", encoding="utf-8")

    assert validate_skill(source).ok


def test_unresolved_relative_reference_is_rejected(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "broken-reference",
        body="# Instructions\n\nRead [the missing guide](references/missing.md).\n",
    )

    assert "markdown.unresolved-reference" in blocker_codes(source)


def test_undefined_markdown_reference_label_is_rejected(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "undefined-label",
        body="# Instructions\n\nRead [the missing guide][missing].\n",
    )

    assert "markdown.unresolved-reference" in blocker_codes(source)


def test_binary_file_is_rejected_and_not_copied(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "binary-skill")
    (source / "payload.bin").write_bytes(b"valid\x00binary")
    destination = tmp_path / "output"

    report = adapt_skill(source, destination, "cursor")

    assert "content.binary" in {finding.code for finding in report.blockers}
    assert not destination.exists()


def test_folder_depth_is_rejected(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "deep-skill")
    deep = source / "one" / "two" / "three" / "four"
    deep.mkdir(parents=True)
    (deep / "note.md").write_text("# Too deep\n", encoding="utf-8")

    assert "package.folder-depth" in blocker_codes(source)


def test_entry_count_is_rejected(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "large-skill")
    for index in range(50):
        (source / f"note-{index:02d}.txt").write_text("text\n", encoding="utf-8")

    assert "package.entry-count" in blocker_codes(source)


def test_exact_entry_limit_is_accepted(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "limit-skill")
    for index in range(49):
        (source / f"note-{index:02d}.txt").write_text("text\n", encoding="utf-8")

    assert validate_skill(source).ok


def test_symlink_is_rejected(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "linked-skill")
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (source / "linked.txt").symlink_to(outside)

    assert "path.symlink" in blocker_codes(source)


def test_markdown_path_traversal_is_rejected(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "traversal-skill",
        body="# Instructions\n\nRead [outside](../outside.md).\n",
    )

    assert "path.escape" in blocker_codes(source)


@pytest.mark.parametrize(
    "content",
    [
        "Open /Users/example/private/notes.md.\n",  # portable-scan: allow-test-fixture
        "Read ~/private/notes.md.\n",  # portable-scan: allow-test-fixture
        "Open C:\\Users\\example\\notes.md.\n",  # portable-scan: allow-test-fixture
        "Fetch file:///tmp/private.txt.\n",  # portable-scan: allow-test-fixture
    ],
)
def test_local_paths_are_rejected(tmp_path: Path, content: str) -> None:
    source = make_skill(tmp_path / "local-path-skill", body=content)

    assert "safety.local-path" in blocker_codes(source)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Use the Read tool for the source.\n", "runtime.local-tool-reference"),
        ("Call mcp__files__read for the source.\n", "runtime.local-tool-reference"),
        ("Connect to the catalog-mcp-server.\n", "runtime.mcp-reference"),
        ("```bash\nprintf 'hello'\n```\n", "runtime.shell-assumption"),
        ("Use available tools to obtain the source.\n", "runtime.ambiguous-semantics"),
        ("Inspect local project files before planning.\n", "runtime.ambiguous-semantics"),
        ("Read the files in this repo before planning.\n", "runtime.ambiguous-semantics"),
        ("python scripts/run.py\n", "runtime.shell-assumption"),
        ("databricks jobs run-now 123\n", "runtime.shell-assumption"),
        ("Delete the old table with DROP TABLE.\n", "runtime.mutating-operation"),
    ],
)
def test_unsupported_tool_instructions_are_rejected(
    tmp_path: Path,
    body: str,
    expected: str,
) -> None:
    source = make_skill(tmp_path / "runtime-skill", body=body)

    assert expected in blocker_codes(source)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("Contact analyst@example.com.\n", "safety.email"),  # portable-scan: allow-test-fixture
        (
            "Use workspace 1111222233334444.\n",  # portable-scan: allow-test-fixture
            "safety.workspace-id",
        ),
        ("Open go/private-guide.\n", "safety.go-link"),  # portable-scan: allow-test-fixture
        (
            "Open https://service.example.internal/path.\n",  # portable-scan: allow-test-fixture
            "safety.internal-hostname",
        ),
        (
            "Open https://private-workspace."
            "cloud.databricks.com.\n",  # portable-scan: allow-test-fixture
            "safety.internal-hostname",
        ),
        (
            "Open https://private-workspace."
            "azuredatabricks.net.\n",  # portable-scan: allow-test-fixture
            "safety.internal-hostname",
        ),
        (
            "Open https://private-workspace."
            "gcp.databricks.com.\n",  # portable-scan: allow-test-fixture
            "safety.internal-hostname",
        ),
        (
            "Use warehouse abcdef0123456789.\n",  # portable-scan: allow-test-fixture
            "safety.warehouse-id",
        ),
        (
            "Use cluster 1234-123456-example.\n",  # portable-scan: allow-test-fixture
            "safety.cluster-id",
        ),
        (
            "Connect to http://localhost:8080.\n",  # portable-scan: allow-test-fixture
            "safety.local-host",
        ),
        (
            "Read /Workspace/Users/private/notebook.\n",  # portable-scan: allow-test-fixture
            "safety.local-path",
        ),
        ("api_key = supersecretvalue\n", "safety.secret"),  # portable-scan: allow-test-fixture
    ],
)
def test_safety_scan_patterns(tmp_path: Path, content: str, expected: str) -> None:
    candidate = tmp_path / "candidate.txt"
    candidate.write_text(content, encoding="utf-8")

    report = scan_path(candidate)

    assert expected in {finding.code for finding in report.blockers}


def test_repository_scan_ignores_generated_and_environment_directories(tmp_path: Path) -> None:
    for directory_name in (".git", ".venv", ".pytest_cache", "build", "dist", "reports"):
        ignored = tmp_path / directory_name
        ignored.mkdir()
        (ignored / "private.txt").write_text(
            "analyst@example.com\n",  # portable-scan: allow-test-fixture
            encoding="utf-8",
        )
    (tmp_path / "README.md").write_text("# Public repository\n", encoding="utf-8")

    assert scan_path(tmp_path).ok


def test_repository_scan_allows_png_documentation_images(tmp_path: Path) -> None:
    images = tmp_path / "docs" / "images"
    images.mkdir(parents=True)
    (images / "example.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00example")

    assert scan_path(tmp_path).ok


def test_repository_scan_rejects_binary_outside_documentation_images(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "example.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00example")

    assert "content.binary" in {finding.code for finding in scan_path(tmp_path).blockers}


def test_skill_validation_still_rejects_png_documentation_images(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "image-skill")
    images = source / "docs" / "images"
    images.mkdir(parents=True)
    (images / "example.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00example")

    assert "content.binary" in blocker_codes(source)


def test_fixture_marker_does_not_suppress_findings_outside_validator_sources(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "public.md"
    candidate.write_text(
        "Contact analyst@example.com. # portable-scan: allow-test-fixture\n",
        encoding="utf-8",
    )

    assert "safety.email" in {finding.code for finding in scan_path(candidate).blockers}


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("name: invalid\n", "frontmatter.missing-field"),
        ("name: wrong-name\ndescription: Valid description.\n", "frontmatter.name-mismatch"),
        ("name: malformed-skill\ndescription: [broken\n", "frontmatter.invalid-yaml"),
        (
            "name: malformed-skill\ndescription: Valid description.\nparent: databricks-core\n",
            "frontmatter.unsupported-field",
        ),
        (
            "name: malformed-skill\ndescription: Valid description.\ncompatibility: ''\n",
            "frontmatter.invalid-compatibility",
        ),
        (
            "name: malformed-skill\ndescription: Valid description.\nmetadata:\n  version: 1\n",
            "frontmatter.invalid-metadata",
        ),
        (
            "name: malformed-skill\ndescription: Valid description.\nlicense: ''\n",
            "frontmatter.invalid-license",
        ),
        (
            "name: malformed-skill\nname: malformed-skill\ndescription: Valid.\n",
            "frontmatter.invalid-yaml",
        ),
    ],
)
def test_malformed_frontmatter(
    tmp_path: Path,
    header: str,
    expected: str,
) -> None:
    source = tmp_path / "malformed-skill"
    source.mkdir()
    (source / "SKILL.md").write_text(f"---\n{header}---\nBody.\n", encoding="utf-8")

    assert expected in blocker_codes(source)


def test_spec_optional_fields_pass_adapt_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "comms-skill"
    (source / "examples").mkdir(parents=True)
    original = (
        "---\n"
        "name: comms-skill\n"
        "description: >\n"
        "  Write internal updates.\n"
        "  Use for weekly status notes.\n"
        "license: Complete terms in LICENSE.txt\n"
        "compatibility: Text-only; no tools required\n"
        "metadata:\n"
        '  version: "1.0"\n'
        "---\n"
        "Read [the example](examples/update.md).\n"
    )
    (source / "SKILL.md").write_text(original, encoding="utf-8")
    (source / "examples" / "update.md").write_text("Progress, plans, problems.\n", encoding="utf-8")
    destination = tmp_path / "out" / "comms-skill"

    report = adapt_skill(source, destination, "claude-code", report_path=tmp_path / "r.json")

    assert report.ok
    assert (destination / "SKILL.md").read_text(encoding="utf-8") == original
    assert not report.edits


def test_tool_field_removal_preserves_spec_optional_fields(tmp_path: Path) -> None:
    source = tmp_path / "tool-skill"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: tool-skill\ndescription: Valid.\nlicense: MIT\n"
        "allowed-tools: Read\n---\nBody.\n",
        encoding="utf-8",
    )
    destination = tmp_path / "out" / "tool-skill"

    report = adapt_skill(source, destination, "claude-code", report_path=tmp_path / "r.json")

    text = (destination / "SKILL.md").read_text(encoding="utf-8")
    assert report.ok
    assert "license: MIT" in text
    assert "allowed-tools" not in text


def test_missing_frontmatter_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "missing-frontmatter"
    source.mkdir()
    (source / "SKILL.md").write_text("# No frontmatter\n", encoding="utf-8")

    assert "frontmatter.malformed" in blocker_codes(source)


def test_target_validation_rejects_runtime_specific_frontmatter(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "target-skill",
        extra_frontmatter="allowed-tools: Read\n",
    )

    assert "frontmatter.runtime-specific-field" in blocker_codes(source)


def test_inline_code_markdown_example_is_not_a_reference(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "inline-code-skill",
        body="Document the syntax `[example](missing.md)` without linking it.\n",
    )

    assert validate_skill(source).ok


def test_shorter_fence_does_not_close_longer_fence(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "fence-skill",
        body=("````markdown\n```text\n[example](missing.md)\n```\n````\n"),
    )

    assert validate_skill(source).ok


def test_ci_cd_prose_is_not_a_shell_command(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "ci-skill",
        body="Review the CI/CD workflow and report its current status.\n",
    )

    assert validate_skill(source).ok


@pytest.mark.skipif(os.name == "nt", reason="Windows does not expose POSIX executable mode bits.")
def test_executable_file_is_rejected(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "executable-skill")
    helper = source / "helper.txt"
    helper.write_text("plain text\n", encoding="utf-8")
    helper.chmod(0o755)

    assert "path.executable" in blocker_codes(source)


def test_all_repository_variants_are_present_and_named() -> None:
    for skill_name in CUSTOM_SKILLS:
        for runtime in RUNTIME_VARIANTS:
            skill_file = variant_dir(skill_name, runtime) / "SKILL.md"
            assert skill_file.is_file()
            header = yaml.safe_load(skill_file.read_text(encoding="utf-8").split("---", 2)[1])
            assert header["name"] == skill_name
            assert header["description"]


def test_all_repository_genie_skills_pass_portability_validation() -> None:
    for skill_name in CUSTOM_SKILLS:
        first = validate_skill(variant_dir(skill_name, "genie"))
        second = validate_skill(variant_dir(skill_name, "genie"))
        assert first.ok, first.to_json()
        assert first.to_json() == second.to_json()


def test_repository_portable_example_adapts_with_reference(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = repository / "examples" / "portable-source" / "table-review"
    destination = tmp_path / "table-review"

    report = adapt_skill(source, destination, "cursor")

    assert report.ok
    assert report.copied_files == ["SKILL.md", "references/checklist.md"]
    assert report.source == "examples/portable-source/table-review"
    assert (destination / "references" / "checklist.md").is_file()


def test_repository_source_variants_fail_closed_for_manual_semantic_porting() -> None:
    for skill_name in CUSTOM_SKILLS:
        for runtime in ("cursor", "claude-code"):
            report = validate_skill(variant_dir(skill_name, runtime))
            assert not report.ok
            assert "runtime.ambiguous-semantics" in {finding.code for finding in report.blockers}


def test_workload_radar_preserves_jobs_timeline_semantics() -> None:
    variants = [variant_dir("workload-radar", runtime) / "SKILL.md" for runtime in RUNTIME_VARIANTS]

    for skill_file in variants:
        text = skill_file.read_text(encoding="utf-8")
        assert "GROUP BY workspace_id, job_id, run_id" in text
        assert "median(duration_seconds)" in text
        assert "max_by(result_state, period_end_time)" in text
        assert "SUM(timestampdiff(SECOND, period_start_time, period_end_time))" in text
        assert "AS explicit_retry_runs" in text
        assert "AS repair_like_attempts_heuristic" in text
        assert "retry_count" not in text
        assert "completed_at" in text
        assert "ONETIME_RETRY" in text
        assert "'TIMED_OUT'" in text
        assert "'CANCELLED'" in text
        assert "'SUCCESS'" not in text
        assert "median run duration" in text
        assert "195" in text


@pytest.mark.parametrize(
    ("skill_name", "tokens"),
    [
        ("cost-investigator", ("SKU_A", "16 USD", "SKU_B", "12 USD")),
        ("workload-radar", ("100", "195", "20", "32 USD", "5", "14")),
        ("business-pulse", ("180", "220", "22.2%")),
        ("technical-answer", ("Product status", "Sources")),
        ("solution-planner", ("validation", "rollback")),
    ],
)
def test_variants_preserve_contract_evidence(
    skill_name: str,
    tokens: tuple[str, ...],
) -> None:
    variants = [variant_dir(skill_name, runtime) / "SKILL.md" for runtime in RUNTIME_VARIANTS]

    for skill_file in variants:
        text = skill_file.read_text(encoding="utf-8")
        for token in tokens:
            assert token.casefold() in text.casefold()


def test_lockfile_uses_only_public_python_package_sources() -> None:
    repository = Path(__file__).resolve().parents[1]
    lockfile = (repository / "uv.lock").read_text(encoding="utf-8")

    assert "https://pypi.org/simple" in lockfile
    assert "https://files.pythonhosted.org/" in lockfile
    assert "pypi-proxy" not in lockfile


def test_claude_code_variants_do_not_preapprove_bash() -> None:
    variants = [variant_dir(skill_name, "claude-code") / "SKILL.md" for skill_name in CUSTOM_SKILLS]

    for skill_file in variants:
        header = yaml.safe_load(skill_file.read_text(encoding="utf-8").split("---", 2)[1])
        assert "Bash" not in str(header.get("allowed-tools", ""))


def test_repository_public_safety_scan_passes() -> None:
    repository = Path(__file__).resolve().parents[1]

    report = scan_path(repository)

    assert report.ok, report.to_json()


def check_codes(path: Path, product: str) -> tuple[str, set[str], set[str]]:
    report = check_skill(path, product)
    return (
        report.status,
        {finding.code for finding in report.blockers},
        {finding.code for finding in report.warnings},
    )


def test_check_accepts_spec_optional_fields_and_skips_license_text(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "licensed-skill", extra_frontmatter="license: Apache-2.0\n")
    (source / "LICENSE.txt").write_text(
        "You may delete, drop and overwrite copies under the license terms.\n", encoding="utf-8"
    )

    assert check_codes(source, "genie-one") == ("accepted", set(), set())


def test_check_turns_keyword_heuristics_into_review_items(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "heuristic-skill",
        body="# Instructions\n\nUse available tools or ask the user directly.\n",
        extra_frontmatter='argument-hint: "<topic>"\n',
    )

    status, blockers, review = check_codes(source, "genie-code")
    assert status == "review"
    assert not blockers
    assert {"frontmatter.client-field", "runtime.ambiguous-semantics"} <= review


def test_check_binary_blocks_genie_one_only(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "binary-skill")
    (source / "showcase.pdf").write_bytes(b"%PDF-1.4\x00\x01")

    assert check_codes(source, "genie-one")[1] == {"content.binary"}
    status, blockers, review = check_codes(source, "genie-code")
    assert (status, blockers) == ("review", set())
    assert "content.binary" in review


def test_check_flags_scripts_for_genie_one(tmp_path: Path) -> None:
    source = make_skill(tmp_path / "script-skill")
    (source / "scripts").mkdir()
    (source / "scripts" / "summarize.py").write_text("print('summary')\n", encoding="utf-8")

    assert "runtime.script" in check_codes(source, "genie-one")[2]
    assert "runtime.script" not in check_codes(source, "genie-code")[2]


def test_check_blocks_references_outside_the_skill(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "linked-skill",
        body="# Instructions\n\nSee [connectors](../../CONNECTORS.md).\n",
    )

    status, blockers, _ = check_codes(source, "genie-code")
    assert status == "blocked"
    assert "path.escape" in blockers


def test_check_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    clean = make_skill(tmp_path / "clean-skill")
    broken = make_skill(
        tmp_path / "broken-skill",
        body="# Instructions\n\nRead [missing](references/missing.md).\n",
    )

    assert main(["check", str(clean), "--product", "genie-one"]) == 0
    assert json.loads(capsys.readouterr().out)["product"] == "genie-one"
    assert main(["check", str(broken), "--product", "genie-one"]) == 1


def test_relative_parent_links_are_not_local_paths(tmp_path: Path) -> None:
    source = make_skill(
        tmp_path / "relative-skill",
        body="# Instructions\n\nThe source linked to `../../CONNECTORS.md`.\n",
    )

    assert "safety.local-path" not in blocker_codes(source)


def test_repository_scan_allows_only_hash_verified_upstream_binaries(tmp_path: Path) -> None:
    upstream = tmp_path / "migrations" / "demo" / "upstream" / "demo"
    upstream.mkdir(parents=True)
    pdf = upstream / "showcase.pdf"
    pdf.write_bytes(b"%PDF-1.4\x00\x01")
    record = {
        "skills": [
            {
                "upstream_path": "migrations/demo/upstream/demo",
                "upstream": {"showcase.pdf": hashlib.sha256(pdf.read_bytes()).hexdigest()},
            }
        ]
    }
    (tmp_path / "migrations" / "PROVENANCE.json").write_text(json.dumps(record), encoding="utf-8")

    assert scan_path(tmp_path).ok
    pdf.write_bytes(b"%PDF-1.4\x00\x02")
    assert "content.binary" in {finding.code for finding in scan_path(tmp_path).blockers}


MIGRATION_EXPECTATIONS = {
    "write-query": ({"path.escape"}, "accepted"),
    "internal-comms": (set(), "review"),
    "theme-factory": ({"content.binary"}, "accepted"),
    "define-goal": (set(), "accepted"),
    "security-threat-model": (set(), "accepted"),
}


@pytest.mark.parametrize("name", sorted(MIGRATION_EXPECTATIONS))
def test_migrations_check_as_documented(name: str) -> None:
    upstream_blockers, genie_status = MIGRATION_EXPECTATIONS[name]
    base = REPOSITORY / "migrations" / name

    assert check_codes(base / "upstream" / name, "genie-one")[1] == upstream_blockers
    for product in ("genie-one", "genie-code"):
        status, blockers, _ = check_codes(base / "genie" / name, product)
        assert not blockers
        assert status == genie_status


@pytest.mark.parametrize("name", sorted(MIGRATION_EXPECTATIONS))
def test_migration_provenance_hashes_match(name: str) -> None:
    record = json.loads((REPOSITORY / "migrations" / "PROVENANCE.json").read_text(encoding="utf-8"))
    skill = next(item for item in record["skills"] if item["name"] == name)
    for variant in ("upstream", "genie"):
        root = REPOSITORY / skill[f"{variant}_path"]
        actual = {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }
        assert actual == skill[variant]


def published_skill_hashes() -> dict[str, str]:
    text = (REPOSITORY / "docs" / "live-results.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| ([a-z-]+) \| `([0-9a-f]{12})` \|", text, flags=re.M)
    tested: dict[str, str] = {}
    for name, digest in rows:
        if name in CUSTOM_SKILLS:
            tested.setdefault(name, digest)
    changed = re.findall(
        r"^\| ([a-z-]+) \| `([0-9a-f]{12})` \| `([0-9a-f]{12})` \|$", text, flags=re.M
    )
    for name, tested_digest, current_digest in changed:
        assert tested[name] == tested_digest
        tested[name] = current_digest
    return tested


@pytest.mark.parametrize("name", CUSTOM_SKILLS)
def test_custom_skill_matches_published_hash(name: str) -> None:
    digest = hashlib.sha256((variant_dir(name, "genie") / "SKILL.md").read_bytes()).hexdigest()
    assert digest[:12] == published_skill_hashes()[name]
