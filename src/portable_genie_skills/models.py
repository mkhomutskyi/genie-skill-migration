"""Deterministic, JSON-compatible result models."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Severity = Literal["warning", "blocker"]


@dataclass(frozen=True)
class Finding:
    """A validation or safety finding."""

    code: str
    message: str
    path: str = "."
    line: int | None = None
    severity: Severity = "blocker"

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class Edit:
    """A line-aware transformation made during adaptation."""

    path: str
    line: int | None
    kind: str
    message: str
    before: str | None = None
    after: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class Report:
    """Complete deterministic report for a command."""

    command: str
    source: str
    destination: str | None = None
    source_runtime: str | None = None
    product: str | None = None
    source_sha256: str | None = None
    destination_sha256: str | None = None
    removed_fields: list[dict[str, Any]] = field(default_factory=list)
    copied_files: list[str] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    blockers: list[Finding] = field(default_factory=list)
    edits: list[Edit] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    @property
    def status(self) -> str:
        if self.blockers:
            return "blocked"
        if self.command == "check" and self.warnings:
            return "review"
        return "accepted"

    def finalize(self) -> Report:
        """Sort all collections so serialization is stable."""
        self.removed_fields.sort(
            key=lambda item: (
                str(item.get("path", "")),
                int(item.get("line") or 0),
                str(item.get("field", "")),
            )
        )
        self.copied_files = sorted(set(self.copied_files))
        self.warnings = sorted(set(self.warnings), key=_finding_key)
        self.blockers = sorted(set(self.blockers), key=_finding_key)
        self.edits = sorted(set(self.edits), key=_edit_key)
        return self

    def to_dict(self) -> dict[str, Any]:
        self.finalize()
        data = {
            "schema_version": 1,
            "command": self.command,
            "status": self.status,
            "source": self.source,
            "destination": self.destination,
            "source_runtime": self.source_runtime,
            "source_sha256": self.source_sha256,
            "destination_sha256": self.destination_sha256,
            "removed_fields": self.removed_fields,
            "copied_files": self.copied_files,
            "warnings": [finding.to_dict() for finding in self.warnings],
            "blockers": [finding.to_dict() for finding in self.blockers],
            "edits": [edit.to_dict() for edit in self.edits],
        }
        if self.product is not None:
            data["product"] = self.product
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True, ensure_ascii=True) + "\n"

    def to_markdown(self) -> str:
        data = self.to_dict()
        lines = [
            "# Portable skill report",
            "",
            f"- Command: `{data['command']}`",
            f"- Status: `{data['status']}`",
            f"- Source: `{data['source']}`",
        ]
        if self.destination is not None:
            lines.append(f"- Destination: `{self.destination}`")
        if self.source_runtime is not None:
            lines.append(f"- Source runtime: `{self.source_runtime}`")
        if self.source_sha256 is not None:
            lines.append(f"- Source SHA256: `{self.source_sha256}`")
        if self.destination_sha256 is not None:
            lines.append(f"- Destination SHA256: `{self.destination_sha256}`")

        lines.extend(["", "## Copied files"])
        lines.extend(f"- `{path}`" for path in self.copied_files)
        if not self.copied_files:
            lines.append("- None")

        lines.extend(["", "## Removed fields"])
        for item in self.removed_fields:
            location = _location(str(item["path"]), item.get("line"))
            lines.append(f"- `{item['field']}` at {location}")
        if not self.removed_fields:
            lines.append("- None")

        lines.extend(["", "## Edits"])
        for edit in self.edits:
            lines.append(f"- `{edit.kind}` at {_location(edit.path, edit.line)}: {edit.message}")
        if not self.edits:
            lines.append("- None")

        lines.extend(["", "## Warnings"])
        lines.extend(_finding_line(finding) for finding in self.warnings)
        if not self.warnings:
            lines.append("- None")

        lines.extend(["", "## Blockers"])
        lines.extend(_finding_line(finding) for finding in self.blockers)
        if not self.blockers:
            lines.append("- None")
        return "\n".join(lines) + "\n"

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.to_json() if path.suffix.lower() == ".json" else self.to_markdown()
        path.write_text(content, encoding="utf-8", newline="\n")


def _location(path: str, line: int | None) -> str:
    suffix = f":{line}" if line is not None else ""
    return f"`{path}{suffix}`"


def _finding_line(finding: Finding) -> str:
    return f"- `{finding.code}` at {_location(finding.path, finding.line)}: {finding.message}"


def _finding_key(finding: Finding) -> tuple[str, int, str, str]:
    return finding.path, finding.line or 0, finding.code, finding.message


def _edit_key(edit: Edit) -> tuple[str, int, str, str]:
    return edit.path, edit.line or 0, edit.kind, edit.message
