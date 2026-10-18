import json
import os
from pathlib import Path
import subprocess
import time

import pytest

from aifw import signing, waiver
from aifw.claude import check_project, enable_project, install_command
from aifw.common import read_yaml, write_yaml
from aifw.hooks import handle
from aifw.secrets import scan
from aifw.shell import analyze, runs_tests
from test_workflows import AT, init

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def pre(root, tool, **tool_input):
    out = handle(dict(cwd=str(root), tool_name=tool, tool_input=tool_input))
    return out and out["hookSpecificOutput"]["permissionDecision"]


def event(root, name, **payload):
    return handle(dict(payload, cwd=str(root), hook_event_name=name, session_id="s"))


def commit(root):
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(GIT + ["add", "-A"], cwd=root, check=True)
    subprocess.run(GIT + ["commit", "-qm", "base"], cwd=root, check=True)


@pytest.mark.parametrize(
    "path",
    [
        ".aifw/waivers/waiver-tests.yaml",
        ".aifw/break-glass/inc.yaml",
        ".aifw/runs/s.jsonl",
        ".aifw/charter.yaml",
        ".aifw/changes/active/x/change.yaml",
        str(Path.home() / ".claude/settings.json"),
    ],
)
def test_decision_files_cannot_be_written_silently(tmp_path, path):
    init(tmp_path)
    assert pre(tmp_path, "Write", file_path=path, content="x") == "ask"


def test_secret_files_ask_before_reading(tmp_path):
    init(tmp_path)
    assert pre(tmp_path, "Read", file_path=".env") == "ask"
    assert pre(tmp_path, "Bash", command="cat config/server.pem") == "ask"
    assert pre(tmp_path, "Read", file_path="README.md") is None


@pytest.mark.parametrize(
    ("command", "kind"),
    [
        ("cmd /c git push", "git-remote"),
        ("powershell -Command git push origin main", "git-remote"),
        ("Start-Process git -ArgumentList push", "opaque"),
        ("echo push | xargs git", "opaque"),
        ("git p", "opaque"),
        ('python -c "import os"', "read-only"),
        ('python -c "import subprocess; subprocess.run([1])"', "opaque"),
        ("npm publish", "external-write"),
        ("flutter pub publish", "external-write"),
        ("flutter pub get", "install"),
        ("scp dump.sql host:/tmp", "external-write"),
        ("pip install requests", "install"),
        ("npm install left-pad", "install"),
        ("uv add httpx", "install"),
        ("uv sync --locked", "filesystem-write"),
        ("npx create-next-app demo", "install"),
        ("uvx ruff check", "install"),
        ("winget install Git.Git", "install"),
        ("choco install nodejs", "install"),
        ("brew install jq", "install"),
        ("uv tool install graphifyy", "install"),
        ("npm create vite@latest app", "install"),
        ("git clone https://github.com/a/b", "install"),
        ("gh repo clone a/b", "install"),
        ('git commit -m "x"', "commit"),
        ("git -C . rebase main", "commit"),
        ("git merge feature", "commit"),
        ("git add -A", "git-local"),
    ],
)
def test_shell_reader_covers_indirect_and_remote_actions(command, kind):
    assert analyze(command)["kind"] == kind


@pytest.mark.parametrize(
    ("command", "tests"),
    [
        ("echo pytest", False),
        ("grep pytest README.md", False),
        ("python -m pytest -q", True),
        ("npm run test", True),
        ("npm test", True),
        ("aifw validate --level L1", True),
    ],
)
def test_only_test_runners_count_as_verification(command, tests):
    assert runs_tests(command) == tests


def test_stop_sees_edits_made_outside_the_edit_tool(tmp_path):
    init(tmp_path)
    (tmp_path / "app.py").write_text("x = 1\n")
    commit(tmp_path)
    event(tmp_path, "SessionStart")
    (tmp_path / "app.py").write_text("x = 2\n")  # as a script or sed -i would
    assert "app.py" in event(tmp_path, "Stop")["reason"]
    event(tmp_path, "PostToolUse", tool_name="Bash", tool_input=dict(command="python -m pytest -q"))
    assert event(tmp_path, "Stop") is None
    (tmp_path / "notes.md").write_text("docs only\n")
    assert event(tmp_path, "Stop") is None
    subprocess.run(GIT + ["commit", "-qam", "verified work"], cwd=tmp_path, check=True)
    assert event(tmp_path, "Stop") is None  # committing verified files is not a change


def test_old_session_logs_are_pruned(tmp_path):
    init(tmp_path)
    old = tmp_path / ".aifw/runs/old.jsonl"
    old.parent.mkdir(parents=True)
    old.write_text("{}\n")
    stale = time.time() - 40 * 86400
    os.utime(old, (stale, stale))
    event(tmp_path, "SessionStart")
    assert not old.exists() and (tmp_path / ".aifw/runs/s.jsonl").exists()


def test_secret_scan_reports_locations_not_values(tmp_path):
    init(tmp_path)
    key = "AKIA" + "Q" * 16
    (tmp_path / "config.py").write_text(f"KEY = '{key}'\nFAKE = '{key}'  # aifw:allow-secret\n")
    (tmp_path / ".env").write_text("TOKEN=x\n")
    (tmp_path / ".env.example").write_text("TOKEN=\n")
    result = scan(tmp_path)
    assert result["status"] == "blocked"
    assert {(f["path"], f["rule"]) for f in result["findings"]} == {
        ("config.py", "aws-access-key"),
        (".env", "secret-file"),
    }
    assert key not in json.dumps(result)


def test_signed_commit_mode_rejects_unsigned_approvals(tmp_path):
    init(tmp_path)
    data = dict(ruleId="tests", scope=["ci"], reason="r", requestedBy="agent:t", approvedBy="human:me")
    waiver.add_waiver(tmp_path, dict(data, approvedAt=AT, expiresAt="2999-01-01T00:00:00Z"))
    assert waiver.load_waivers(tmp_path)[0]["active"]
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    policy["approvals"] = dict(requireSignedCommit=True)
    write_yaml(tmp_path / ".aifw/permissions.yaml", policy)
    commit(tmp_path)
    assert signing.required(tmp_path)
    assert not waiver.load_waivers(tmp_path)[0]["active"]
    assert not signing.approved(tmp_path, tmp_path / ".aifw/charter.yaml")


def test_check_flags_an_outdated_global_command(tmp_path):
    init(tmp_path)
    enable_project(tmp_path)
    home = tmp_path / "home"
    install_command(home)
    assert not any("/aifw" in f for f in check_project(tmp_path, home)["findings"])
    (home / ".claude/skills/aifw/SKILL.md").write_text("old")
    assert any("outdated" in f for f in check_project(tmp_path, home)["findings"])
