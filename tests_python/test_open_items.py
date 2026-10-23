import json
import subprocess

from aifw import routing, specs
from aifw.common import read_yaml, write_yaml
from aifw.hooks import handle, summarize_runs
from aifw.permissions import decide_action
from aifw.secrets import scan
from aifw.shell import analyze
from aifw.workspace import adapt_gates
from test_hardening import GIT, commit
from test_workflows import AT, init

FAKE_KEY = "AKIA" + "Q" * 16


def pre(root, tool, **tool_input):
    out = handle(dict(cwd=str(root), tool_name=tool, tool_input=tool_input))
    return out and out["hookSpecificOutput"]["permissionDecision"]


def event(root, name, **payload):
    return handle(dict(payload, cwd=str(root), hook_event_name=name, session_id="s"))


def test_delegation_is_free_except_to_cloud_sessions(tmp_path):
    init(tmp_path)
    specs.create_change(tmp_path, dict(id="risky", title="R", summary="S", level="L3", createdAt=AT))
    # The model table is the agent's call, L3 included (ADR-0037).
    assert pre(tmp_path, "Agent", model="claude-haiku-5-5") is None
    assert pre(tmp_path, "Agent", subagent_type="general-purpose") is None
    assert pre(tmp_path, "Agent", subagent_type="general-purpose", isolation="remote") == "ask"


def test_script_files_are_read_like_inline_code(tmp_path):
    (tmp_path / "run.py").write_text("import subprocess\nsubprocess.run(['git', 'push'])\n")
    (tmp_path / "send.py").write_text("import requests\nrequests.post('https://x.example')\n")
    (tmp_path / "plain.py").write_text("print(1)\n")
    assert analyze("python run.py", cwd=tmp_path)["kind"] == "opaque"
    assert analyze("uv run python send.py", cwd=tmp_path)["kind"] == "external-write"
    assert analyze("python plain.py", cwd=tmp_path)["kind"] == "read-only"
    # Without a folder the call keeps the old reading: an ordinary local write.
    assert analyze("python run.py")["kind"] == "filesystem-write"
    # A script that does not exist yet may be written by the same command, so it cannot be read (ADR-0034).
    assert analyze("python missing.py", cwd=tmp_path)["kind"] == "opaque"


def test_ignored_stop_is_recorded_and_reported(tmp_path):
    init(tmp_path)
    event(tmp_path, "PostToolUse", tool_name="Edit", tool_input=dict(file_path="app.py"))
    assert event(tmp_path, "Stop")["decision"] == "block"
    assert event(tmp_path, "Stop", stop_hook_active=True) is None
    summary = summarize_runs(tmp_path, "s")[0]
    assert summary["status"] == "warning" and "Stop warning" in summary["findings"][0]
    test = dict(tool_name="Bash", tool_input=dict(command="python -m pytest -q"))
    event(tmp_path, "PostToolUse", tool_response=dict(exit_code=0), **test)
    assert summarize_runs(tmp_path, "s")[0]["status"] == "pass"


def test_control_file_edits_are_notes_not_findings(tmp_path):
    init(tmp_path)
    event(tmp_path, "PostToolUse", tool_name="Edit", tool_input=dict(file_path=".aifw/gates.yaml"))
    summary = summarize_runs(tmp_path, "s")[0]
    assert summary["status"] == "pass" and "control files" in summary["notes"][0]


def test_unknown_policy_value_asks_instead_of_allowing():
    policy = dict(localGit="yolo", remoteMutation="autonomous", destructiveChanges="human-approval")
    policy.update(previewDeployment="autonomous", productionDeployment="human-approval")
    assert decide_action(dict(kind="git-local"), policy)["decision"] == "require-approval"
    assert decide_action(dict(kind="git-remote"), policy)["decision"] == "allow"


def test_gate_recipe_follows_the_project_tools(tmp_path):
    web = {
        "gates": [{"id": "lint", "command": ["npm", "run", "lint"]}, {"id": "t", "command": ["npm", "test"]}]
    }
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"test": "vitest"}}))
    (tmp_path / "pnpm-lock.yaml").write_text("")
    gates = adapt_gates(tmp_path, web)["gates"]
    assert "command" not in gates[0] and gates[1]["command"] == ["pnpm", "run", "test"]
    py = {"gates": [{"id": "l", "command": ["python", "-m", "ruff", "check", "."]}]}
    py["gates"].append({"id": "t", "command": ["python", "-m", "pytest", "-q"]})
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\ndev = ["pytest"]\n')
    (tmp_path / "uv.lock").write_text("")
    gates = adapt_gates(tmp_path, py)["gates"]
    assert "command" not in gates[0] and gates[1]["command"][:3] == ["uv", "run", "python"]


def test_new_project_keeps_the_recipe(tmp_path):
    init(tmp_path, "web-ts")
    commands = {g["id"]: g.get("command") for g in read_yaml(tmp_path / ".aifw/gates.yaml")["gates"]}
    assert commands["lint"] == ["npm", "run", "lint"]


def test_secret_scan_can_read_the_history(tmp_path):
    (tmp_path / "config.py").write_text(f"KEY = '{FAKE_KEY}'\n")
    commit(tmp_path)
    (tmp_path / "config.py").write_text("KEY = None\n")
    subprocess.run(GIT + ["commit", "-qam", "remove"], cwd=tmp_path, check=True)
    assert scan(tmp_path)["status"] == "pass"
    found = scan(tmp_path, history=True)["findings"]
    assert [(f["path"], f["rule"]) for f in found] == [("config.py", "aws-access-key")]
    assert len(found[0]["commit"]) == 12


def test_routing_is_always_on_signed_or_not(tmp_path):
    init(tmp_path)
    assert routing.routing_state(tmp_path) == (routing.ALIASES, True)  # ADR-0037
    permissions = read_yaml(tmp_path / ".aifw/permissions.yaml")
    write_yaml(
        tmp_path / ".aifw/permissions.yaml", dict(permissions, approvals=dict(requireSignedCommit=True))
    )
    commit(tmp_path)
    assert routing.routing_state(tmp_path)[1]
