"""Find committed or pending secrets in project files; reports locations, never the values."""

from pathlib import Path
import re
import subprocess

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


def matches(path, number, line):
    if ALLOW in line:
        return []
    return [dict(path=path, line=number, rule=rule) for rule, rx in PATTERNS.items() if rx.search(line)]


def scan_history(root):
    """Lines added in any commit of any branch; a secret removed later is still in the history."""
    log = subprocess.run(
        ["git", "log", "--all", "-p", "-U0", "--no-color", "--no-ext-diff", "--format=commit %H"],
        cwd=root,
        capture_output=True,
    )
    findings, commit, path = [], None, None
    for line in log.stdout.decode("utf-8", "replace").splitlines():
        if line.startswith("commit "):
            commit = line[7:19]
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
            if path and SECRET_FILE.search(path) and not path.endswith(".example"):
                findings.append(dict(path=path, line=0, rule="secret-file", commit=commit))
        elif line.startswith("+") and path:
            findings += [dict(f, commit=commit) for f in matches(path, 0, line[1:])]
    return findings


def scan(root, history=False):
    from .specs import project_files

    findings = scan_history(root) if history else []
    for path in project_files(root):
        if SECRET_FILE.search(path) and not path.endswith(".example"):
            findings.append(dict(path=path, line=0, rule="secret-file"))
            continue
        file = Path(root) / path
        data = file.read_bytes() if file.stat().st_size <= MAX_BYTES else b""
        if b"\0" in data:
            continue
        for number, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            findings += matches(path, number, line)
    return dict(status="pass" if not findings else "blocked", findings=findings)
