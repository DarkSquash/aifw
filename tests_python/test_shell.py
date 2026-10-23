import io

import pytest

from aifw import cli
from aifw.common import AifwError, read_yaml, write_yaml
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


@pytest.mark.parametrize(
    ("command", "kind"),
    [
        ("sed -n 305,335p hooks.py", "read-only"),
        ("sed -E -n 's/a/b/p' x.txt", "read-only"),
        ("sed --silent --expression=1p x.txt", "read-only"),
        ("sed -i s/a/b/ x.txt", "filesystem-write"),
        ("sed -i.bak s/a/b/ x.txt", "filesystem-write"),
        ("sed -Ei s/a/b/ x.txt", "filesystem-write"),
        ("sed -ni 1p x.txt", "filesystem-write"),
        ("sed --in-place s/a/b/ x.txt", "filesystem-write"),
        ("sed --in-place=.bak s/a/b/ x.txt", "filesystem-write"),
        ("awk 'NR>=310 && NR<=335' x.txt", "read-only"),
        ("awk 'NR>=310 {print $1}' x.txt", "read-only"),
        ("gawk '$1 > 5 {print}' x.txt", "read-only"),
        ("awk '{print \"a;b>c\"}' x.txt", "read-only"),
        ("awk -i inplace '{print}' x.txt", "filesystem-write"),
        ("gawk --include=inplace '{print}' x.txt", "filesystem-write"),
        ("awk '{print > \"x\"}' x.txt", "filesystem-write"),
        ("awk '{print $1 >> \"x\"}' x.txt", "filesystem-write"),
        ("awk '{print > $1\".txt\"}' x.txt", "filesystem-write"),
        ("awk '{printf(\"%s\n\", $1) > \"x\"}' x.txt", "filesystem-write"),
        ("awk '{print \"a;b\" > \"x\"}' x.txt", "filesystem-write"),
        ("awk '{print | \"sort\"}' x.txt", "filesystem-write"),
        ("awk '{print |& \"sort\"}' x.txt", "filesystem-write"),
        ("awk '{system(\"touch x\")}' x.txt", "filesystem-write"),
    ],
)
def test_sed_and_awk_read_unless_they_write(command, kind):
    assert analyze(command)["kind"] == kind


def test_sed_and_awk_reading_a_control_file_do_not_ask(tmp_path):
    init(tmp_path)

    def decision(command):
        output = handle(dict(cwd=str(tmp_path), tool_name="Bash", tool_input=dict(command=command)))
        return output and output["hookSpecificOutput"]["permissionDecision"]

    reads = "sed -n 305,335p python/aifw/hooks.py; cat .aifw/specs/current/task-assessor.yaml"
    assert decision(reads) is None
    assert decision("awk 'NR>=310' .aifw/gates.yaml") is None
    assert decision("sed -i 's/a/b/' .aifw/permissions.yaml") == "ask"
    assert decision("""awk '{print > "x"}' .aifw/gates.yaml""") == "ask"
    assert decision("sed -n 1p .env") == "deny"


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


def test_opaque_commands_ask_when_the_project_asks_for_them(tmp_path):
    init(tmp_path)
    payload = dict(cwd=str(tmp_path), tool_name="Bash", tool_input=dict(command='eval "$X"'))
    assert handle(payload) is None  # new projects allow code the hook cannot read (ADR-0037)
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    write_yaml(tmp_path / ".aifw/permissions.yaml", dict(policy, opaqueCode="ask"))
    assert handle(payload)["hookSpecificOutput"]["permissionDecision"] == "ask"


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
