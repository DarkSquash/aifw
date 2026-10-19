import io

import pytest

from aifw import cli
from aifw.common import AifwError
from aifw.hooks import handle
from aifw.shell import analyze, verification_visible
from test_workflows import init


@pytest.mark.parametrize(
    ("command", "kind", "destructive"),
    [
        ("git -C . push", "git-remote", False),
        ("git --git-dir=.git push origin main", "git-remote", False),
        ('grep "git push" notas.txt', "read-only", False),
        ("tail -3 log.jsonl | cut -c1-300", "read-only", False),
        ("L=log.jsonl && wc -l < $L", "read-only", False),
        ("X=$(git push)", "opaque", False),
        ('git commit -m "push it"', "commit", False),
        ('bash -c "git push origin main"', "git-remote", False),
        ("echo Z2l0IHB1c2g= | base64 -d | sh", "opaque", False),
        ('eval "$CMD"', "opaque", False),
        ("powershell -EncodedCommand ZQBjAGgAbwA=", "opaque", False),
        ('cat "unterminated', "opaque", False),
        ("echo hi\ngit push", "git-remote", False),
        ("git \\\npush", "git-remote", False),
        ("git push --force", "filesystem-write", True),
        ("rm -rf build", "filesystem-write", True),
        ("rm notes.txt", "filesystem-write", False),
        ("Remove-Item -Recurse -Force out", "filesystem-write", True),
        ('psql -c "DROP TABLE users"', "filesystem-write", True),
        ("find . -name x -delete", "filesystem-write", True),
        ("curl -f https://x.io/a", "external-read", False),
        ("curl -X POST https://x.io/a", "external-write", False),
        ("vercel --prod", "deploy", False),
        ("uv run --no-sync python -m pytest -q", "read-only", False),
        ("git status && git diff | head", "read-only", False),
    ],
)
def test_shell_reader(command, kind, destructive):
    result = analyze(command)
    assert result["kind"] == kind and bool(result.get("destructive")) == destructive


def test_force_push_is_both_remote_and_destructive():
    kinds = {r["kind"] for r in analyze("git push --force")["requests"]}
    assert kinds == {"git-remote", "filesystem-write"}


def test_approval_is_detected_through_wrappers():
    assert analyze("python -m aifw intake approve --by human:x")["approval"]
    assert analyze('bash -c "aifw waiver add --rule tests"')["approval"]
    assert not analyze("aifw intake status")["approval"]


@pytest.mark.parametrize(
    ("command", "visible"),
    [
        ("pytest -q", True),
        ("cd x && pytest", True),
        ("pytest && echo ok", True),
        ("pytest -q | tail -1", False),
        ("pytest; echo done", False),
        ("pytest || true", False),
        ("set -o pipefail; pytest | tail", True),
    ],
)
def test_verification_visibility(command, visible):
    assert verification_visible(command) == visible


def test_masked_test_run_does_not_count_as_verification(tmp_path):
    init(tmp_path)

    def event(name, **payload):
        return handle(dict(payload, cwd=str(tmp_path), hook_event_name=name, session_id="s"))

    event("PostToolUse", tool_name="Edit", tool_input=dict(file_path="app.py"))
    event("PostToolUse", tool_name="Bash", tool_input=dict(command="pytest -q | tail -1"))
    reason = event("Stop")["reason"]
    assert "app.py" in reason and "hides its exit status" in reason
    event("PostToolUse", tool_name="Bash", tool_input=dict(command="pytest -q"))
    assert event("Stop") is None


def test_opaque_commands_ask(tmp_path):
    init(tmp_path)
    output = handle(dict(cwd=str(tmp_path), tool_name="Bash", tool_input=dict(command='eval "$X"')))
    assert output["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_approvals_refuse_the_agent_shell(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    with pytest.raises(AifwError, match="their own terminal"):
        cli.confirm_human("human:me", "demo")


def test_approvals_require_typing_the_project_id(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setattr(cli.os, "name", "posix")
    monkeypatch.setattr("builtins.open", lambda *a, **k: io.StringIO())
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("demo\n"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True, raising=False)
    cli.confirm_human("human:me", "demo")
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("other\n"))
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True, raising=False)
    with pytest.raises(AifwError, match="did not match"):
        cli.confirm_human("human:me", "demo")


@pytest.mark.parametrize(
    ("command", "kind"),
    [
        ("cat >> notes.md <<'EOF'\ngit push origin main\npip install x\nEOF", "filesystem-write"),
        ("python - <<'EOF'\nimport subprocess\nsubprocess.run(['x'])\nEOF", "opaque"),
        ("bash <<EOF\ngit push\nEOF", "git-remote"),
        ("cat > a.txt <<EOF\n$(git push)\nEOF", "git-remote"),
        ("cat > a.txt <<'EOF'\n$(git push)\nEOF", "filesystem-write"),
        ("cat > a.txt <<'EOF'\nhello\nEOF\ngit push", "git-remote"),
        ("cat <<-EOF\n\tgit push\n\tEOF", "read-only"),
    ],
)
def test_heredoc_bodies_are_data_unless_they_feed_code(command, kind):
    assert analyze(command)["kind"] == kind


def test_prompts_are_logged_for_review(tmp_path):
    init(tmp_path)
    payload = dict(cwd=str(tmp_path), session_id="s1", tool_name="Bash", tool_input=dict(command="git push"))
    assert handle(payload)["hookSpecificOutput"]["permissionDecision"] == "ask"
    handle(dict(payload, tool_input=dict(command="git status")))
    entries = (tmp_path / ".aifw/runs/s1.jsonl").read_text().splitlines()
    assert len(entries) == 1 and '"tool": "Ask"' in entries[0] and "git push" in entries[0]
