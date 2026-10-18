"""Optional proof of human approval: the approval file must sit unchanged in a signed git commit.

An agent can write any file the person can, but it cannot sign a commit with a key whose
passphrase only the person knows. Enable with `approvals.requireSignedCommit` in permissions.yaml.
"""

from pathlib import Path
import subprocess


def required(root):
    from .permissions import load_permission_policy

    if not (Path(root) / ".aifw/permissions.yaml").is_file():
        return False
    return bool(load_permission_policy(root).get("approvals", {}).get("requireSignedCommit"))


def signed_and_unchanged(root, path):
    """The file's last commit has a good signature and the file has not changed since."""

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True
        )

    relative = (
        Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
        if Path(path).is_absolute()
        else path
    )
    clean = git("status", "--porcelain", "--", relative)
    signature = git("log", "-1", "--format=%G?", "--", relative)
    return clean.returncode == 0 and not clean.stdout.strip() and signature.stdout.strip() in {"G", "U"}


def approved(root, path):
    """True when signing is not required, or when the file is in a signed commit, unchanged."""
    return not required(root) or signed_and_unchanged(root, path)
