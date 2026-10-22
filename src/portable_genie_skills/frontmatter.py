"""Agent Skills frontmatter parsing and normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import yaml

from portable_genie_skills.models import Edit, Finding

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
KNOWN_TOOL_FIELDS = frozenset(
    {
        "agent",
        "allowed-tools",
        "argument-hint",
        "context",
        "disable-model-invocation",
        "hooks",
        "model",
        "tools",
        "user-invocable",
    }
)
REQUIRED_FIELDS = frozenset({"name", "description"})
SPEC_OPTIONAL_FIELDS = ("license", "compatibility", "metadata")
MAX_COMPATIBILITY_LENGTH = 500
SOURCE_RUNTIME_FIELDS = {
    "cursor": frozenset({"disable-model-invocation"}),
    "claude-code": KNOWN_TOOL_FIELDS,
}


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: _UniqueKeyLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


@dataclass(frozen=True)
class FrontmatterResult:
    data: dict[str, Any] | None
    body: str
    normalized: str | None
    removed_fields: tuple[dict[str, Any], ...]
    edits: tuple[Edit, ...]
    blockers: tuple[Finding, ...]


def parse_and_normalize(text: str, skill_name: str, path: str = "SKILL.md") -> FrontmatterResult:
    """Parse, validate, and deterministically normalize an Agent Skill header."""
    blockers: list[Finding] = []
    removed: list[dict[str, Any]] = []
    edits: list[Edit] = []

    split = _split_frontmatter(text)
    if split is None:
        blockers.append(
            Finding(
                code="frontmatter.malformed",
                message="SKILL.md must begin with YAML frontmatter delimited by `---` lines.",
                path=path,
                line=1,
            )
        )
        return FrontmatterResult(None, "", None, (), (), tuple(blockers))
    header, body, _closing_line = split

    try:
        loaded = yaml.load(header, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 2 if mark is not None else 2
        blockers.append(
            Finding(
                code="frontmatter.invalid-yaml",
                message=f"Frontmatter is not valid YAML: {_yaml_error_message(exc)}.",
                path=path,
                line=line,
            )
        )
        return FrontmatterResult(None, body, None, (), (), tuple(blockers))

    if not isinstance(loaded, dict):
        blockers.append(
            Finding(
                code="frontmatter.not-mapping",
                message="Frontmatter must be a YAML mapping.",
                path=path,
                line=2,
            )
        )
        return FrontmatterResult(None, body, None, (), (), tuple(blockers))
    if any(not isinstance(key, str) for key in loaded):
        blockers.append(
            Finding(
                code="frontmatter.non-string-key",
                message="Every frontmatter field name must be a string.",
                path=path,
                line=2,
            )
        )
        return FrontmatterResult(None, body, None, (), (), tuple(blockers))

    field_lines = _field_lines(header)
    _validate_required_fields(loaded, skill_name, field_lines, path, blockers)
    _validate_optional_fields(loaded, field_lines, path, blockers)

    unsupported = sorted(
        set(loaded) - REQUIRED_FIELDS - KNOWN_TOOL_FIELDS - set(SPEC_OPTIONAL_FIELDS)
    )
    for field_name in unsupported:
        blockers.append(
            Finding(
                code="frontmatter.unsupported-field",
                message=(
                    f"Field `{field_name}` is unsupported and cannot be dropped without "
                    "reviewing its semantics."
                ),
                path=path,
                line=field_lines.get(field_name, 2),
            )
        )

    for field_name in sorted(set(loaded) & KNOWN_TOOL_FIELDS):
        line = field_lines.get(field_name, 2)
        removed.append({"path": path, "field": field_name, "line": line})
        edits.append(
            Edit(
                path=path,
                line=line,
                kind="remove-frontmatter-field",
                message=f"Removed known tool-specific field `{field_name}`.",
                before=field_name,
                after=None,
            )
        )

    normalized = None
    if not blockers and not removed:
        normalized = text
    elif not blockers:
        kept = {"name": loaded["name"], "description": loaded["description"]}
        kept.update({key: loaded[key] for key in SPEC_OPTIONAL_FIELDS if key in loaded})
        normalized_header = yaml.safe_dump(
            kept,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=1000,
        ).rstrip("\n")
        normalized = f"---\n{normalized_header}\n---\n{body}"
        original_header = f"---\n{header}\n---\n"
        new_header = f"---\n{normalized_header}\n---\n"
        if original_header != new_header:
            edits.append(
                Edit(
                    path=path,
                    line=1,
                    kind="normalize-frontmatter",
                    message=(
                        "Normalized frontmatter to name, description, and present "
                        "Agent Skills optional fields."
                    ),
                    before=original_header,
                    after=new_header,
                )
            )

    return FrontmatterResult(
        loaded,
        body,
        normalized,
        tuple(removed),
        tuple(edits),
        tuple(blockers),
    )


def _split_frontmatter(text: str) -> tuple[str, str, int] | None:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].rstrip("\n") == "---":
            header = "".join(lines[1:index]).rstrip("\n")
            body = "".join(lines[index + 1 :])
            return header, body, index + 1
    return None


def _field_lines(header: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, line in enumerate(header.splitlines(), start=2):
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:", line)
        if match:
            result.setdefault(match.group(1), index)
    return result


def _validate_required_fields(
    data: dict[str, Any],
    skill_name: str,
    field_lines: dict[str, int],
    path: str,
    blockers: list[Finding],
) -> None:
    for field_name in sorted(REQUIRED_FIELDS - set(data)):
        blockers.append(
            Finding(
                code="frontmatter.missing-field",
                message=f"Required field `{field_name}` is missing.",
                path=path,
                line=2,
            )
        )

    name = data.get("name")
    if "name" in data:
        line = field_lines.get("name", 2)
        if not isinstance(name, str):
            blockers.append(
                Finding(
                    code="frontmatter.invalid-name",
                    message="Field `name` must be a string.",
                    path=path,
                    line=line,
                )
            )
        elif not 1 <= len(name) <= MAX_NAME_LENGTH or NAME_PATTERN.fullmatch(name) is None:
            blockers.append(
                Finding(
                    code="frontmatter.invalid-name",
                    message=(
                        "Field `name` must contain 1-64 lowercase letters, digits, or "
                        "single hyphens."
                    ),
                    path=path,
                    line=line,
                )
            )
        elif name != skill_name:
            blockers.append(
                Finding(
                    code="frontmatter.name-mismatch",
                    message=f"Frontmatter name `{name}` does not match skill root `{skill_name}`.",
                    path=path,
                    line=line,
                )
            )

    description = data.get("description")
    if "description" in data:
        line = field_lines.get("description", 2)
        if not isinstance(description, str):
            blockers.append(
                Finding(
                    code="frontmatter.invalid-description",
                    message="Field `description` must be a string.",
                    path=path,
                    line=line,
                )
            )
        elif not description.strip():
            blockers.append(
                Finding(
                    code="frontmatter.invalid-description",
                    message="Field `description` must not be empty.",
                    path=path,
                    line=line,
                )
            )
        elif len(description) > MAX_DESCRIPTION_LENGTH:
            blockers.append(
                Finding(
                    code="frontmatter.invalid-description",
                    message=(
                        f"Field `description` must not exceed {MAX_DESCRIPTION_LENGTH} characters."
                    ),
                    path=path,
                    line=line,
                )
            )


def _validate_optional_fields(
    data: dict[str, Any],
    field_lines: dict[str, int],
    path: str,
    blockers: list[Finding],
) -> None:
    if "license" in data and (not isinstance(data["license"], str) or not data["license"].strip()):
        blockers.append(
            Finding(
                code="frontmatter.invalid-license",
                message="Field `license` must be a non-empty string.",
                path=path,
                line=field_lines.get("license", 2),
            )
        )
    if "compatibility" in data:
        value = data["compatibility"]
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_COMPATIBILITY_LENGTH:
            blockers.append(
                Finding(
                    code="frontmatter.invalid-compatibility",
                    message=(
                        "Field `compatibility` must be a string of 1-"
                        f"{MAX_COMPATIBILITY_LENGTH} characters."
                    ),
                    path=path,
                    line=field_lines.get("compatibility", 2),
                )
            )
    if "metadata" in data:
        value = data["metadata"]
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and isinstance(item, str) for key, item in value.items()
        ):
            blockers.append(
                Finding(
                    code="frontmatter.invalid-metadata",
                    message="Field `metadata` must map string keys to string values.",
                    path=path,
                    line=field_lines.get("metadata", 2),
                )
            )


def _yaml_error_message(exc: yaml.YAMLError) -> str:
    problem = getattr(exc, "problem", None)
    if isinstance(problem, str):
        return problem.rstrip(".")
    return exc.__class__.__name__
