"""Conservative content and Markdown-reference safety checks."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from portable_genie_skills.models import Finding

EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", re.IGNORECASE)
WORKSPACE_ID_RE = re.compile(r"(?<!\d)\d{16}(?!\d)")
WAREHOUSE_ID_RE = re.compile(r"(?<![A-Fa-f0-9])[A-Fa-f0-9]{16}(?![A-Fa-f0-9])")
CLUSTER_ID_RE = re.compile(r"(?<!\w)\d{4}-\d{6}-[A-Za-z0-9-]+(?!\w)")
GO_LINK_RE = re.compile(r"(?<![\w./-])(?:https?://)?go/[A-Za-z0-9][\w./?#=-]*", re.IGNORECASE)
LOCAL_PATH_RES = (
    re.compile(
        # portable-scan: allow-test-fixture
        r"(?<![\w:/.])/"  # portable-scan: allow-test-fixture
        r"(?!/)[A-Za-z0-9._-]+(?:/[A-Za-z0-9._~+-]+)+"
    ),
    re.compile(r"(?<!\w)~/(?:[^\s`'\"<>)]+)"),  # portable-scan: allow-test-fixture
    re.compile(  # portable-scan: allow-test-fixture
        r"(?<!\w)[A-Za-z]:\\(?:[^\s`'\"<>]+)"
    ),
    re.compile(r"file://[^\s`'\"<>]+", re.IGNORECASE),  # portable-scan: allow-test-fixture
)
INTERNAL_HOST_RE = re.compile(
    r"\b(?:https?://)?(?:"
    # portable-scan: allow-test-fixture
    r"(?:[a-z0-9-]+\.)+(?:internal|corp|local|lan|intranet)(?![a-z0-9_-])"
    r"|[a-z0-9-]+\.cloud\.databricks\.com"  # portable-scan: allow-test-fixture
    r"|[a-z0-9.-]+\.azuredatabricks\.net"  # portable-scan: allow-test-fixture
    r"|[a-z0-9.-]+\.gcp\.databricks\.com"  # portable-scan: allow-test-fixture
    r"|[a-z0-9-]+-\d+\.aws\.databricksapps\.com"  # portable-scan: allow-test-fixture
    r")\b",
    re.IGNORECASE,
)
LOCAL_HOST_RE = re.compile(
    # portable-scan: allow-test-fixture
    r"\b(?:https?://)?"  # portable-scan: allow-test-fixture
    r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?\b",  # portable-scan: allow-test-fixture
    re.IGNORECASE,
)
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "service token",
        re.compile(r"\b(?:gh[opsu]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b"),
    ),
    (
        "assigned secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)"
            r"\s*[:=]\s*[\"']?(?!example|placeholder|redacted|<)[A-Za-z0-9_./+=-]{8,}"
        ),
    ),
)
LOCAL_TOOL_RE = re.compile(
    r"(?i)(?:\bmcp__[a-z0-9_-]+|\bfunctions\.[a-z0-9_-]+|"
    r"<tool_(?:call|use)>|\bcall\s+the\s+`?[\w.-]+`?\s+tool\b|"
    r"\buse\s+the\s+`?[\w.-]+`?\s+tool\b|"
    r"`(?:Read|Write|Edit|Bash|Grep|Glob|Task|WebFetch|TodoWrite)`)"
)
MCP_RE = re.compile(
    r"(?i)(?:\bMCP\b|\bmodel context protocol\b|"  # portable-scan: allow-test-fixture
    r"\b[a-z0-9_-]+-mcp(?:-server)?\b|\bmcp[_-]server\b)"
)
SHELL_RES = (
    re.compile(r"^```(?:ba)?sh|^```(?:zsh|shell|console)\b", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^#!\s*/(?:usr/bin/env\s+)?(?:ba)?sh\b", re.MULTILINE),
    re.compile(r"(?m)^\s*(?:\$|%)\s+\S+"),
    re.compile(r"(?i)\b(?:run|execute)\s+(?:this\s+)?(?:shell\s+)?command\b"),
    re.compile(r"(?i)(?<![\w/])(?:cd|chmod|curl|wget|sudo)\s+(?:-[A-Za-z]+\s+)?[^\s`]+"),
    re.compile(r"(?im)^\s*(?:python3?|pip|uv|databricks)\s+\S+"),
    re.compile(r"\$(?:HOME|PWD|SHELL|USER)\b"),
)
AMBIGUOUS_RUNTIME_RE = re.compile(
    r"(?i)(?:\bCursor\b|\bClaude Code\b|\.cursor/|\.claude/|"
    r"\bslash command\b|\bavailable tools?\b|\btool availability\b|"
    r"\b(?:inspect|read|search)\s+(?:the\s+)?local\s+(?:project|repository|workspace)|"
    r"\b(?:inspect|read|search)\s+(?:the\s+|this\s+|nearby\s+)?"
    r"(?:project|repository|repo|codebase)\s+(?:files|context)\b|"
    r"\bread\s+(?:the\s+)?files\s+in\s+(?:this\s+|the\s+)?"
    r"(?:repo|repository|project|codebase)\b|"
    r"\blocal\s+(?:project|repository|workspace)\s+(?:files|context)\b)"
)
DANGEROUS_OPERATION_RE = re.compile(
    r"(?i)\b(?:drop|delete|truncate|alter|insert|update|merge|grant|revoke)\s+"
    r"(?:table|view|schema|catalog|volume|function|model|permission|row|rows)\b|"
    r"\b(?:delete|terminate|destroy|deploy|create|resize|restart)\s+"
    r"(?:a\s+|the\s+)?(?:cluster|warehouse|endpoint|job|pipeline|app|resource)\b"
)
ONE_CLICK_RE = re.compile(r"(?i)\b(?:one[- ]" r"click|import un" r"changed|un" r"changed import)\b")
SCAN_FIXTURE_MARKER = "portable-scan: allow-test-fixture"
DOCUMENTED_INSTALL_PATH_RE = re.compile(
    r"(?:"
    r"/(?:Workspace/)?Users/\{(?:email|user|username)\}/\.assistant/skills"
    r"|<project>/\.(?:cursor|claude)/skills"
    r")(?:/[A-Za-z0-9._{}<>-]+)*/?"
)

INLINE_LINK_RE = re.compile(r"!?\[[^\]]*]\(\s*([^)]+?)\s*\)")
REFERENCE_DEFINITION_RE = re.compile(
    r"^\s{0,3}\[([^\]]+)]:\s*(\S+)",
    re.MULTILINE,
)
REFERENCE_USE_RE = re.compile(r"!?\[([^\]]+)]\[([^\]]*)]")
HTML_LINK_RE = re.compile(r"(?i)\b(?:href|src)\s*=\s*[\"']([^\"']+)[\"']")


def decode_text(data: bytes, relative_path: str) -> tuple[str | None, list[Finding]]:
    """Decode a text file without accepting binary/control content."""
    findings: list[Finding] = []
    if b"\x00" in data:
        return None, [
            Finding(
                code="content.binary",
                message="NUL bytes are not allowed in skill files.",
                path=relative_path,
            )
        ]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [
            Finding(
                code="content.not-utf8",
                message="Skill files must be valid UTF-8 text.",
                path=relative_path,
                line=_byte_line(data, exc.start),
            )
        ]
    for index, character in enumerate(text):
        if ord(character) < 32 and character not in "\n\r\t":
            findings.append(
                Finding(
                    code="content.control-character",
                    message="Control characters are not allowed in skill files.",
                    path=relative_path,
                    line=text.count("\n", 0, index) + 1,
                )
            )
            break
    return (None if findings else text), findings


def scan_text(text: str, relative_path: str) -> list[Finding]:
    """Return conservative safety blockers for a text file."""
    checks: tuple[tuple[str, str, re.Pattern[str]], ...] = (
        ("safety.email", "Email addresses are not portable.", EMAIL_RE),
        (
            "safety.workspace-id",
            "Workspace identifiers are environment-specific and are not allowed.",
            WORKSPACE_ID_RE,
        ),
        (
            "safety.warehouse-id",
            "SQL warehouse identifiers are environment-specific and are not allowed.",
            WAREHOUSE_ID_RE,
        ),
        (
            "safety.cluster-id",
            "Cluster identifiers are environment-specific and are not allowed.",
            CLUSTER_ID_RE,
        ),
        ("safety.go-link", "Internal `go/` links are not allowed.", GO_LINK_RE),
        (
            "safety.internal-hostname",
            "Internal hostnames are not allowed.",
            INTERNAL_HOST_RE,
        ),
        ("safety.local-host", "Local host references are not portable.", LOCAL_HOST_RE),
        (
            "runtime.local-tool-reference",
            "Local tool references require runtime-specific behavior and are not portable.",
            LOCAL_TOOL_RE,
        ),
        (
            "runtime.mcp-reference",
            "MCP server names or instructions are not portable.",
            MCP_RE,
        ),
        (
            "runtime.ambiguous-semantics",
            "Runtime-specific or tool-availability semantics are ambiguous.",
            AMBIGUOUS_RUNTIME_RE,
        ),
        (
            "runtime.mutating-operation",
            "Mutating platform operations require manual target-runtime review.",
            DANGEROUS_OPERATION_RE,
        ),
        (
            "portability.unsupported-claim",
            "One-click or unchanged-import claims are not allowed.",
            ONE_CLICK_RE,
        ),
    )
    findings: list[Finding] = []
    for code, message, pattern in checks:
        findings.extend(_matches(pattern, text, relative_path, code, message))
    for pattern in LOCAL_PATH_RES:
        findings.extend(
            _matches(
                pattern,
                text,
                relative_path,
                "safety.local-path",
                "Absolute or local filesystem paths are not portable.",
            )
        )
    for label, pattern in SECRET_PATTERNS:
        findings.extend(
            _matches(
                pattern,
                text,
                relative_path,
                "safety.secret",
                f"Possible {label} detected.",
            )
        )
    for pattern in SHELL_RES:
        findings.extend(
            _matches(
                pattern,
                text,
                relative_path,
                "runtime.shell-assumption",
                "Shell commands and shell-environment assumptions are not portable.",
            )
        )
    return findings


def scan_public_text(text: str, relative_path: str) -> list[Finding]:
    """Scan publishable repository text while allowing marked test fixtures."""
    marker_allowed = relative_path in {
        "src/portable_genie_skills/safety.py",
        "tests/test_tooling.py",
    }
    cleaned = (
        "".join(
            "\n" if SCAN_FIXTURE_MARKER in line else line for line in text.splitlines(keepends=True)
        )
        if marker_allowed
        else text
    )
    cleaned = DOCUMENTED_INSTALL_PATH_RE.sub("<documented-install-path>", cleaned)
    return [
        finding
        for finding in scan_text(cleaned, relative_path)
        if finding.code.startswith("safety.")
    ]


def validate_markdown_references(
    text: str,
    relative_path: str,
    root: Path,
    known_paths: set[str],
) -> list[Finding]:
    """Validate every local Markdown, reference-style, and HTML reference."""
    findings: list[Finding] = []
    cleaned = _without_inline_code(_without_fenced_code(text))
    references: list[tuple[str, int]] = []
    for pattern in (INLINE_LINK_RE, HTML_LINK_RE):
        for match in pattern.finditer(cleaned):
            target = match.group(1).strip().strip("<>")
            target = target.split(maxsplit=1)[0].strip("'\"")
            references.append((target, cleaned.count("\n", 0, match.start(1)) + 1))
    definitions: dict[str, str] = {}
    for match in REFERENCE_DEFINITION_RE.finditer(cleaned):
        label = _normalize_reference_label(match.group(1))
        target = match.group(2).strip().strip("<>").strip("'\"")
        definitions[label] = target
        references.append((target, cleaned.count("\n", 0, match.start(2)) + 1))
    for match in REFERENCE_USE_RE.finditer(cleaned):
        label_text = match.group(2) or match.group(1)
        label = _normalize_reference_label(label_text)
        if label not in definitions:
            findings.append(
                Finding(
                    code="markdown.unresolved-reference",
                    message=f"Markdown reference label `{label_text}` is not defined.",
                    path=relative_path,
                    line=cleaned.count("\n", 0, match.start()) + 1,
                )
            )

    parent = PurePosixPath(relative_path).parent
    for target, line in references:
        parsed = urlsplit(target)
        if parsed.scheme in {"http", "https"}:
            continue
        if parsed.scheme or parsed.netloc:
            findings.append(
                Finding(
                    code="markdown.unsupported-uri",
                    message=f"Unsupported URI reference `{target}`.",
                    path=relative_path,
                    line=line,
                )
            )
            continue
        raw_path = unquote(parsed.path)
        if not raw_path or raw_path == "." or target.startswith("#"):
            continue
        if raw_path.startswith("/") or raw_path.startswith("~"):
            findings.append(
                Finding(
                    code="markdown.absolute-reference",
                    message=f"Absolute Markdown reference `{target}` is not portable.",
                    path=relative_path,
                    line=line,
                )
            )
            continue
        candidate = _collapse_path(parent / PurePosixPath(raw_path))
        if candidate is None:
            findings.append(
                Finding(
                    code="path.escape",
                    message=f"Markdown reference `{target}` escapes the skill root.",
                    path=relative_path,
                    line=line,
                )
            )
            continue
        candidate_text = candidate.as_posix()
        if candidate_text not in known_paths and not _directory_exists(candidate_text, known_paths):
            findings.append(
                Finding(
                    code="markdown.unresolved-reference",
                    message=f"Relative Markdown reference `{target}` does not resolve.",
                    path=relative_path,
                    line=line,
                )
            )
            continue
        resolved = (root / candidate_text).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            findings.append(
                Finding(
                    code="path.escape",
                    message=f"Markdown reference `{target}` escapes the skill root.",
                    path=relative_path,
                    line=line,
                )
            )
    return findings


def _matches(
    pattern: re.Pattern[str],
    text: str,
    path: str,
    code: str,
    message: str,
) -> Iterable[Finding]:
    for match in pattern.finditer(text):
        yield Finding(
            code=code,
            message=message,
            path=path,
            line=text.count("\n", 0, match.start()) + 1,
        )


def _collapse_path(path: PurePosixPath) -> PurePosixPath | None:
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return PurePosixPath(*parts)


def _directory_exists(candidate: str, known_paths: set[str]) -> bool:
    prefix = candidate.rstrip("/") + "/"
    return any(path.startswith(prefix) for path in known_paths)


def _normalize_reference_label(label: str) -> str:
    return " ".join(label.casefold().split())


def _without_fenced_code(text: str) -> str:
    lines = text.splitlines(keepends=True)
    inside = False
    marker_character = ""
    marker_length = 0
    output: list[str] = []
    for line in lines:
        match = re.match(r"^\s*(```+|~~~+)", line)
        if match:
            current = match.group(1)
            if not inside:
                inside = True
                marker_character = current[0]
                marker_length = len(current)
            elif current[0] == marker_character and len(current) >= marker_length:
                inside = False
            output.append("\n" if line.endswith("\n") else "")
        elif inside:
            output.append("\n" if line.endswith("\n") else "")
        else:
            output.append(line)
    return "".join(output)


def _without_inline_code(text: str) -> str:
    return re.sub(
        r"(?<!`)`+[^`\n]*`+",
        lambda match: " " * len(match.group(0)),
        text,
    )


def _byte_line(data: bytes, offset: int) -> int:
    return data.count(b"\n", 0, offset) + 1
