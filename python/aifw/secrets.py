"""Find committed or pending secrets in project files; reports locations, never the values."""

from pathlib import Path
import re

from .shell import SECRET_FILE

PATTERNS = {
    "private-key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "api-key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "slack-token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "assigned-secret": re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|client[_-]?secret|secret[_-]?key|password)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"
    ),
}
ALLOW = "aifw:allow-secret"  # put on a line holding a deliberate fake, such as a test fixture
MAX_BYTES = 1_000_000


def scan(root):
    from .specs import project_files

    findings = []
    for path in project_files(root):
        if SECRET_FILE.search(path) and not path.endswith(".example"):
            findings.append(dict(path=path, line=0, rule="secret-file"))
            continue
        file = Path(root) / path
        data = file.read_bytes() if file.stat().st_size <= MAX_BYTES else b""
        if b"\0" in data:
            continue
        for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            if ALLOW in line:
                continue
            findings += [
                dict(path=path, line=number, rule=rule) for rule, rx in PATTERNS.items() if rx.search(line)
            ]
    return dict(status="pass" if not findings else "blocked", findings=findings)
