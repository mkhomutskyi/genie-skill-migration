"""Validation, scanning, and fail-closed skill adaptation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from portable_genie_skills.frontmatter import (
    SOURCE_RUNTIME_FIELDS,
    FrontmatterResult,
    parse_and_normalize,
)
from portable_genie_skills.models import Finding, Report
from portable_genie_skills.safety import (
    decode_text,
    scan_public_text,
    scan_text,
    validate_markdown_references,
)

MAX_ENTRIES = 50
MAX_FOLDER_DEPTH = 3
SKILL_FILE = "SKILL.md"
RUNTIMES = frozenset({"cursor", "claude-code"})
PRODUCTS = ("genie-one", "genie-code")
PROVENANCE_FILE = "migrations/PROVENANCE.json"
LICENSE_PREFIXES = ("LICENSE", "LICENCE", "NOTICE", "COPYING")
SCRIPT_SUFFIXES = frozenset({".sh", ".bash", ".py", ".js", ".ts", ".ps1", ".rb"})
CHECK_BLOCKING_PREFIXES = (
    "package.",
    "path.",
    "frontmatter.",
    "markdown.",
    "content.",
    "safety.secret",
)
CHECK_REVIEW_CODES = frozenset(
    {
        "frontmatter.client-field",
        "frontmatter.unsupported-field",
        "markdown.unsupported-uri",
        "path.executable",
        "path.runtime-directory",
    }
)
FORBIDDEN_PATH_PARTS = frozenset({".cursor", ".claude", ".git", "__pycache__"})
SCAN_IGNORED_NAMES = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "reports",
    }
)
DOCUMENTATION_IMAGE_PREFIX = "docs/images/"
DOCUMENTATION_IMAGE_SUFFIXES = frozenset({".png"})


@dataclass(frozen=True)
class _Entry:
    relative_path: str
    path: Path
    kind: str
    mode: int
    data: bytes | None = None
    text: str | None = None
    link_target: str | None = None


@dataclass(frozen=True)
class _Inspection:
    entries: tuple[_Entry, ...]
    findings: tuple[Finding, ...]
    sha256: str | None


def scan_path(path: str | Path) -> Report:
    """Scan a file or directory for binary data and unsafe content."""
    source = Path(path).expanduser().resolve()
    report = Report(command="scan", source=_display_path(source))
    inspection = _inspect(
        source,
        enforce_skill_limits=False,
        ignored_directory_names=SCAN_IGNORED_NAMES,
        allow_documentation_images=True,
    )
    report.source_sha256 = inspection.sha256
    verified = _verified_upstream_files(source) if source.is_dir() else frozenset()
    report.blockers.extend(
        finding
        for finding in inspection.findings
        if not (finding.code == "content.binary" and finding.path in verified)
    )
    for entry in inspection.entries:
        if entry.text is not None:
            report.blockers.extend(scan_public_text(entry.text, entry.relative_path))
    return report.finalize()


def _verified_upstream_files(root: Path) -> frozenset[str]:
    """Upstream files whose SHA-256 matches the provenance record."""
    manifest = root / PROVENANCE_FILE
    if not manifest.is_file():
        return frozenset()
    try:
        skills = json.loads(manifest.read_text(encoding="utf-8"))["skills"]
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()
    verified: set[str] = set()
    for skill in skills:
        base = PurePosixPath(str(skill.get("upstream_path", "")))
        for relative, digest in dict(skill.get("upstream", {})).items():
            candidate = PurePosixPath(base, relative).as_posix()
            path = root / candidate
            if (
                candidate.startswith("migrations/")
                and ".." not in PurePosixPath(candidate).parts
                and path.is_file()
                and not path.is_symlink()
                and hashlib.sha256(path.read_bytes()).hexdigest() == digest
            ):
                verified.add(candidate)
    return frozenset(verified)


def validate_skill(path: str | Path) -> Report:
    """Validate an Agent Skill package for portable Genie constraints."""
    source = Path(path).expanduser().resolve()
    report = Report(command="validate", source=_display_path(source))
    inspection = _inspect(source, enforce_skill_limits=True)
    report.source_sha256 = inspection.sha256
    report.blockers.extend(inspection.findings)
    _validate_inspection(source, inspection, report)
    return report.finalize()


def check_skill(path: str | Path, product: str) -> Report:
    """Check a third-party skill for one Genie product.

    Blockers are documented product limits, specification errors, broken references and
    likely secrets. Keyword heuristics become review items, and license files are not
    scanned for them.
    """
    source = Path(path).expanduser().resolve()
    report = Report(command="check", source=_display_path(source), product=product)
    if product not in PRODUCTS:
        report.blockers.append(
            Finding(
                code="product.unsupported",
                message=f"Product must be one of: {', '.join(PRODUCTS)}.",
            )
        )
        return report.finalize()
    inspection = _inspect(source, enforce_skill_limits=product == "genie-one")
    report.source_sha256 = inspection.sha256
    findings = list(inspection.findings)
    if not source.is_dir():
        findings.append(
            Finding(code="package.not-directory", message="A skill package must be a directory.")
        )
    else:
        files = {e.relative_path: e for e in inspection.entries if e.kind == "file"}
        skill_entry = files.get(SKILL_FILE)
        if skill_entry is None:
            findings.append(
                Finding(
                    code="package.missing-skill-file",
                    message="Skill root must contain `SKILL.md`.",
                )
            )
        elif skill_entry.text is not None:
            frontmatter = parse_and_normalize(skill_entry.text, source.name)
            findings.extend(frontmatter.blockers)
            findings.extend(
                Finding(
                    code="frontmatter.client-field",
                    message=f"Field `{item['field']}` is client metadata outside the spec.",
                    path=str(item["path"]),
                    line=int(item["line"]),
                )
                for item in frontmatter.removed_fields
            )
        for entry in inspection.entries:
            if entry.text is None:
                continue
            if not _is_license_file(entry.relative_path):
                findings.extend(scan_text(entry.text, entry.relative_path))
            if entry.relative_path.lower().endswith((".md", ".markdown")):
                findings.extend(
                    validate_markdown_references(
                        entry.text, entry.relative_path, source, set(files)
                    )
                )
            if product == "genie-one" and _is_script(entry.relative_path):
                findings.append(
                    Finding(
                        code="runtime.script",
                        message="Genie One does not document running skill scripts.",
                        path=entry.relative_path,
                    )
                )
    for finding in findings:
        if _blocks_product(finding, product):
            report.blockers.append(finding)
        else:
            report.warnings.append(replace(finding, severity="warning"))
    return report.finalize()


def _is_license_file(relative_path: str) -> bool:
    name = PurePosixPath(relative_path).name.upper()
    return "/" not in relative_path and name.startswith(LICENSE_PREFIXES)


def _is_script(relative_path: str) -> bool:
    pure = PurePosixPath(relative_path)
    return pure.parts[0] == "scripts" or pure.suffix.lower() in SCRIPT_SUFFIXES


def _blocks_product(finding: Finding, product: str) -> bool:
    if finding.code == "content.binary":
        return product == "genie-one"
    if finding.code in CHECK_REVIEW_CODES:
        return False
    return finding.code.startswith(CHECK_BLOCKING_PREFIXES)


def adapt_skill(
    source: str | Path,
    destination: str | Path,
    source_runtime: str,
    report_path: str | Path | None = None,
) -> Report:
    """Validate and atomically copy a normalized portable skill."""
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()
    report = Report(
        command="adapt",
        source=_display_path(source_path),
        destination=_display_path(destination_path),
        source_runtime=source_runtime,
    )
    if source_runtime not in RUNTIMES:
        report.blockers.append(
            Finding(
                code="runtime.unsupported",
                message=f"Source runtime must be one of: {', '.join(sorted(RUNTIMES))}.",
            )
        )

    _validate_source_destination(source_path, destination_path, report)
    if report_path is not None:
        _validate_report_path(
            Path(report_path).expanduser().resolve(),
            source_path,
            destination_path,
            report,
        )
    inspection = _inspect(source_path, enforce_skill_limits=True)
    report.source_sha256 = inspection.sha256
    report.blockers.extend(inspection.findings)
    frontmatter = _validate_inspection(
        source_path,
        inspection,
        report,
        adaptation=True,
        source_runtime=source_runtime,
    )
    if report.blockers or frontmatter is None or frontmatter.normalized is None:
        return report.finalize()

    stage: Path | None = None
    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(
            tempfile.mkdtemp(
                prefix=f".{destination_path.name}.",
                dir=destination_path.parent,
            )
        )
        for entry in inspection.entries:
            if entry.kind != "file" or entry.text is None:
                continue
            target = stage / entry.relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            content = (
                frontmatter.normalized.encode("utf-8")
                if entry.relative_path == SKILL_FILE
                else entry.data
            )
            if content is None:
                raise RuntimeError(f"accepted file has no content: {entry.relative_path}")
            target.write_bytes(content)
            target.chmod(0o644)
            report.copied_files.append(entry.relative_path)
        os.replace(stage, destination_path)
        report.destination_sha256 = _inspect(
            destination_path,
            enforce_skill_limits=True,
        ).sha256
        report.removed_fields.extend(frontmatter.removed_fields)
        report.edits.extend(frontmatter.edits)
    except OSError as exc:
        report.blockers.append(
            Finding(
                code="destination.write-failed",
                message=f"Could not write destination atomically: {exc.strerror or exc}.",
                path=".",
            )
        )
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)
    return report.finalize()


def _validate_inspection(
    source: Path,
    inspection: _Inspection,
    report: Report,
    *,
    adaptation: bool = False,
    source_runtime: str | None = None,
) -> FrontmatterResult | None:
    if not source.is_dir():
        report.blockers.append(
            Finding(
                code="package.not-directory",
                message="A skill package must be a directory.",
            )
        )
        return None

    files = {entry.relative_path: entry for entry in inspection.entries if entry.kind == "file"}
    skill_entry = files.get(SKILL_FILE)
    if skill_entry is None:
        report.blockers.append(
            Finding(
                code="package.missing-skill-file",
                message="Skill root must contain `SKILL.md`.",
            )
        )
        frontmatter = None
    elif skill_entry.text is None:
        frontmatter = None
    else:
        frontmatter = parse_and_normalize(skill_entry.text, source.name)
        report.blockers.extend(frontmatter.blockers)
        _validate_runtime_fields(frontmatter, report, adaptation, source_runtime)

    known_paths = set(files)
    for entry in inspection.entries:
        if entry.text is None:
            continue
        report.blockers.extend(scan_text(entry.text, entry.relative_path))
        if entry.relative_path.lower().endswith((".md", ".markdown")):
            report.blockers.extend(
                validate_markdown_references(
                    entry.text,
                    entry.relative_path,
                    source,
                    known_paths,
                )
            )
    return frontmatter


def _validate_runtime_fields(
    frontmatter: FrontmatterResult,
    report: Report,
    adaptation: bool,
    source_runtime: str | None,
) -> None:
    if not frontmatter.removed_fields:
        return
    if not adaptation:
        for item in frontmatter.removed_fields:
            report.blockers.append(
                Finding(
                    code="frontmatter.runtime-specific-field",
                    message=(
                        f"Target Genie package still contains runtime-specific field "
                        f"`{item['field']}`."
                    ),
                    path=str(item["path"]),
                    line=int(item["line"]),
                )
            )
        return

    allowed_fields = SOURCE_RUNTIME_FIELDS.get(source_runtime or "", frozenset())
    for item in frontmatter.removed_fields:
        field_name = str(item["field"])
        if field_name not in allowed_fields:
            report.blockers.append(
                Finding(
                    code="frontmatter.source-runtime-mismatch",
                    message=(
                        f"Field `{field_name}` is not recognized for source runtime "
                        f"`{source_runtime}`."
                    ),
                    path=str(item["path"]),
                    line=int(item["line"]),
                )
            )
            continue
        report.warnings.append(
            Finding(
                code="frontmatter.removed-runtime-field",
                message=(
                    f"Removed `{field_name}`; review trigger and permission behavior "
                    "in the target runtime."
                ),
                path=str(item["path"]),
                line=int(item["line"]),
                severity="warning",
            )
        )


def _inspect(
    path: Path,
    enforce_skill_limits: bool,
    ignored_directory_names: frozenset[str] = frozenset(),
    allow_documentation_images: bool = False,
) -> _Inspection:
    entries: list[_Entry] = []
    findings: list[Finding] = []
    if not path.exists() and not path.is_symlink():
        return _Inspection(
            (),
            (
                Finding(
                    code="path.not-found",
                    message="Source path does not exist.",
                ),
            ),
            None,
        )
    if path.is_symlink():
        return _Inspection(
            (),
            (
                Finding(
                    code="path.symlink",
                    message="The source root must not be a symlink.",
                ),
            ),
            _hash_symlink(path),
        )

    if path.is_file():
        entry, entry_findings = _inspect_file(path, path.name)
        entries.append(entry)
        findings.extend(entry_findings)
    elif path.is_dir():
        _walk_directory(
            path,
            path,
            entries,
            findings,
            ignored_directory_names,
            allow_documentation_images,
        )
    else:
        findings.append(
            Finding(
                code="path.special-file",
                message="Only regular files and directories are allowed.",
            )
        )

    if enforce_skill_limits and path.is_dir():
        if len(entries) > MAX_ENTRIES:
            findings.append(
                Finding(
                    code="package.entry-count",
                    message=(
                        f"A skill may contain at most {MAX_ENTRIES} files and folders; "
                        f"found {len(entries)}."
                    ),
                )
            )
        for entry in entries:
            pure_parts = Path(entry.relative_path).parts
            folder_depth = len(pure_parts) if entry.kind == "directory" else len(pure_parts) - 1
            if folder_depth > MAX_FOLDER_DEPTH:
                findings.append(
                    Finding(
                        code="package.folder-depth",
                        message=(f"Skill content may be at most {MAX_FOLDER_DEPTH} folders deep."),
                        path=entry.relative_path,
                    )
                )

    return _Inspection(
        tuple(sorted(entries, key=lambda item: item.relative_path)),
        tuple(findings),
        _hash_entries(entries),
    )


def _walk_directory(
    root: Path,
    current: Path,
    entries: list[_Entry],
    findings: list[Finding],
    ignored_directory_names: frozenset[str],
    allow_documentation_images: bool,
) -> None:
    try:
        children = sorted(os.scandir(current), key=lambda item: item.name)
    except OSError as exc:
        findings.append(
            Finding(
                code="path.unreadable",
                message=f"Directory cannot be read: {exc.strerror or exc}.",
                path=_relative(root, current),
            )
        )
        return
    for child in children:
        child_path = Path(child.path)
        if child.is_dir(follow_symlinks=False) and child.name in ignored_directory_names:
            continue
        relative_path = _relative(root, child_path)
        if _unsafe_path_name(relative_path):
            findings.append(
                Finding(
                    code="path.invalid-name",
                    message="Path names must not contain control characters or backslashes.",
                    path=relative_path,
                )
            )
        if any(part in FORBIDDEN_PATH_PARTS for part in Path(relative_path).parts):
            findings.append(
                Finding(
                    code="path.runtime-directory",
                    message="Runtime-specific or repository metadata paths are not portable.",
                    path=relative_path,
                )
            )
        try:
            mode = child.stat(follow_symlinks=False).st_mode
        except OSError as exc:
            findings.append(
                Finding(
                    code="path.unreadable",
                    message=f"Path cannot be inspected: {exc.strerror or exc}.",
                    path=relative_path,
                )
            )
            continue
        if stat.S_ISLNK(mode):
            try:
                target = os.readlink(child.path)
            except OSError as exc:
                findings.append(
                    Finding(
                        code="path.unreadable",
                        message=f"Symlink cannot be read: {exc.strerror or exc}.",
                        path=relative_path,
                    )
                )
                target = ""
            entries.append(_Entry(relative_path, child_path, "symlink", mode, link_target=target))
            findings.append(
                Finding(
                    code="path.symlink",
                    message="Symlinks are not allowed in skill packages.",
                    path=relative_path,
                )
            )
        elif stat.S_ISDIR(mode):
            entries.append(_Entry(relative_path, child_path, "directory", mode))
            _walk_directory(
                root,
                child_path,
                entries,
                findings,
                ignored_directory_names,
                allow_documentation_images,
            )
        elif stat.S_ISREG(mode):
            entry, entry_findings = _inspect_file(
                child_path,
                relative_path,
                mode,
                allow_binary=(
                    allow_documentation_images
                    and relative_path.startswith(DOCUMENTATION_IMAGE_PREFIX)
                    and child_path.suffix.lower() in DOCUMENTATION_IMAGE_SUFFIXES
                ),
            )
            entries.append(entry)
            findings.extend(entry_findings)
        else:
            entries.append(_Entry(relative_path, child_path, "special", mode))
            findings.append(
                Finding(
                    code="path.special-file",
                    message="Only regular files and directories are allowed.",
                    path=relative_path,
                )
            )


def _inspect_file(
    path: Path,
    relative_path: str,
    mode: int | None = None,
    *,
    allow_binary: bool = False,
) -> tuple[_Entry, list[Finding]]:
    findings: list[Finding] = []
    actual_mode = path.stat(follow_symlinks=False).st_mode if mode is None else mode
    if actual_mode & 0o111:
        findings.append(
            Finding(
                code="path.executable",
                message="Executable file bits are not allowed in portable skills.",
                path=relative_path,
            )
        )
    try:
        data = path.read_bytes()
    except OSError as exc:
        findings.append(
            Finding(
                code="path.unreadable",
                message=f"File cannot be read: {exc.strerror or exc}.",
                path=relative_path,
            )
        )
        data = b""
    if allow_binary:
        return _Entry(relative_path, path, "file", actual_mode, data=data), findings
    text, text_findings = decode_text(data, relative_path)
    findings.extend(text_findings)
    return _Entry(relative_path, path, "file", actual_mode, data=data, text=text), findings


def _validate_source_destination(source: Path, destination: Path, report: Report) -> None:
    if destination.exists() or destination.is_symlink():
        report.blockers.append(
            Finding(
                code="destination.exists",
                message="Destination must not already exist.",
                path=str(destination),
            )
        )
    if source == destination:
        report.blockers.append(
            Finding(
                code="path.overlap",
                message="Source and destination must be different paths.",
            )
        )
        return
    if _is_relative_to(destination, source) or _is_relative_to(source, destination):
        report.blockers.append(
            Finding(
                code="path.overlap",
                message="Source and destination must not contain one another.",
            )
        )


def _validate_report_path(
    report_path: Path,
    source: Path,
    destination: Path,
    report: Report,
) -> None:
    if (
        report_path in (source, destination)
        or _is_relative_to(report_path, source)
        or _is_relative_to(report_path, destination)
    ):
        report.blockers.append(
            Finding(
                code="report.path-overlap",
                message="Report path must be outside the source and destination.",
                path=str(report_path),
            )
        )


def _hash_entries(entries: list[_Entry]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item.relative_path):
        digest.update(entry.kind.encode("ascii"))
        digest.update(b"\0")
        digest.update(entry.relative_path.encode("utf-8"))
        digest.update(b"\0")
        if entry.data is not None:
            digest.update(entry.data)
        elif entry.link_target is not None:
            digest.update(entry.link_target.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
    return digest.hexdigest()


def _hash_symlink(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(b"symlink\0")
    digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
    return digest.hexdigest()


def _relative(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    return relative or "."


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return f"<external>/{path.name}"


def _unsafe_path_name(relative_path: str) -> bool:
    return "\\" in relative_path or any(
        ord(character) < 32 or ord(character) == 127 for character in relative_path
    )
