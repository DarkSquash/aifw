import json
import subprocess
import sys

import pytest

from aifw import gates, intake, permissions, routing, specs, waiver
from aifw.claude import HOOKS, check_project, enable_project
from aifw.common import AifwError, read_yaml, write_yaml
from aifw.hooks import handle, summarize_runs
from test_workflows import AT, init


def pre(root, tool, **tool_input):
    output = handle(dict(cwd=str(root), tool_name=tool, tool_input=tool_input))
    return output and output["hookSpecificOutput"]["permissionDecision"]


def event(root, name, session="s1", **payload):
    return handle(dict(payload, cwd=str(root), hook_event_name=name, session_id=session))


def set_spec(root, **values):
    manifest = read_yaml(root / "aifw.yaml")
    manifest["spec"].update(values)
    write_yaml(root / "aifw.yaml", manifest)


@pytest.mark.parametrize(
    ("profile", "gate", "command"),
    [
        ("python", "tests", "pytest"),
        ("web-ts", "tests", "npm"),
        ("flutter-mobile", "flutter-test", "flutter"),
    ],
)
def test_init_applies_the_profile_gate_recipe(tmp_path, profile, gate, command):
    init(tmp_path, profile)
    gate_set = {g["id"]: g for g in read_yaml(tmp_path / ".aifw/gates.yaml")["gates"]}
    assert command in gate_set[gate]["command"]


def test_flutter_recipe_follows_fvm(tmp_path):
    (tmp_path / ".fvmrc").write_text("{}")
    init(tmp_path, "flutter-mobile")
    commands = [g.get("command", [""])[0] for g in read_yaml(tmp_path / ".aifw/gates.yaml")["gates"]]
    assert "fvm" in commands


def test_mcp_delegation_and_data_classification(tmp_path):
    init(tmp_path)
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    policy["mcpServers"] = dict(deny=["figma"], ask=["markitdown"])
    write_yaml(tmp_path / ".aifw/permissions.yaml", policy)
    assert pre(tmp_path, "mcp__figma__get_file") == "deny"
    assert pre(tmp_path, "mcp__markitdown__convert") == "ask"
    assert pre(tmp_path, "mcp__other__tool") is None
    specs.create_change(tmp_path, dict(id="routine", title="Routine", summary="S", level="L2", createdAt=AT))
    assert pre(tmp_path, "Agent", model="haiku") is None  # L2 is the agent's call
    specs.create_change(tmp_path, dict(id="risky", title="Risky", summary="S", level="L3", createdAt=AT))
    assert pre(tmp_path, "Agent", model="haiku") == "ask"
    assert pre(tmp_path, "Agent", model="sonnet") is None
    set_spec(tmp_path, externalAllowlist=["github"])
    assert pre(tmp_path, "WebFetch", url="https://api.github.com/x") is None
    assert pre(tmp_path, "WebFetch", url="https://unknown.example") == "ask"
    set_spec(tmp_path, dataClassification="confidential")
    assert pre(tmp_path, "WebFetch", url="https://unknown.example") == "deny"
    set_spec(tmp_path, dataClassification="restricted")
    assert pre(tmp_path, "Bash", command="curl -X POST https://api.github.com/x") == "deny"


def test_break_glass_grant_lifts_policy_prompts_until_it_expires(tmp_path):
    init(tmp_path)
    assert pre(tmp_path, "Bash", command="git push") == "ask"
    grant = dict(incidentId="inc-1", scope=["git-remote"], reason="outage", approvedBy="human:me")
    permissions.grant_break_glass(tmp_path, dict(grant, approvedAt=AT, expiresAt="2999-01-01T00:00:00Z"))
    assert pre(tmp_path, "Bash", command="git push") is None
    with pytest.raises(AifwError):
        permissions.grant_break_glass(
            tmp_path, dict(grant, incidentId="x", scope=["root"], approvedAt=AT, expiresAt=AT)
        )
    assert permissions.list_break_glass(tmp_path)[0]["active"]


def test_session_log_drives_stop_and_impasse_hint(tmp_path):
    init(tmp_path)
    event(tmp_path, "PostToolUse", tool_name="Edit", tool_input=dict(file_path="app.py"))
    blocked = event(tmp_path, "Stop")
    assert blocked["decision"] == "block" and "app.py" in blocked["reason"]
    assert event(tmp_path, "Stop", stop_hook_active=True) is None
    test = dict(tool_name="Bash", tool_input=dict(command="python -m pytest -q"))
    assert event(tmp_path, "PostToolUseFailure", error="1 failed", **test) is None
    hint = event(tmp_path, "PostToolUseFailure", error="1 failed", **test)
    assert "aifw impasse open" in hint["hookSpecificOutput"]["additionalContext"]
    assert event(tmp_path, "Stop") is not None
    event(tmp_path, "PostToolUse", tool_response=dict(exit_code=0), **test)
    assert event(tmp_path, "Stop") is None
    event(tmp_path, "PostToolUse", tool_name="Edit", tool_input=dict(file_path="docs/guide.md"))
    assert event(tmp_path, "Stop") is None
    summary = summarize_runs(tmp_path, "latest")[0]
    # The command passed after failing twice, so the streak is over: no impasse finding.
    assert summary["failedVerifications"] == 2 and summary["status"] == "pass"


def test_session_start_reports_state(tmp_path):
    init(tmp_path)
    specs.create_change(tmp_path, dict(id="feature", title="F", summary="S", level="L2", createdAt=AT))
    context = event(tmp_path, "SessionStart")["hookSpecificOutput"]["additionalContext"]
    assert "Intake is incomplete" in context and "Active change feature (L2, draft)" in context


def test_waiver_passes_a_gate_but_never_human_approval(tmp_path):
    init(tmp_path)
    data = dict(scope=["project"], reason="flaky CI", requestedBy="agent:test", approvedBy="human:me")
    data.update(approvedAt=AT, expiresAt="2999-01-01T00:00:00Z")
    waiver.add_waiver(tmp_path, dict(data, ruleId="tests"))
    report = gates.validate_workspace(tmp_path, "L1", lambda *_: dict(ok=False, stdout="", stderr="x"))
    tests = next(r for r in report["passed"] if r["gateId"] == "tests")
    assert tests["waived"]
    with pytest.raises(AifwError):
        waiver.add_waiver(tmp_path, dict(data, ruleId="human-approval"))
    with pytest.raises(AifwError):
        waiver.add_waiver(tmp_path, dict(data, ruleId="security.no-secret-output"))


def test_intake_set_records_and_reopens(tmp_path):
    init(tmp_path)
    assert intake.set_charter_field(tmp_path, "problem", "Real problem")["field"] == "problem"
    with pytest.raises(AifwError):
        intake.set_charter_field(tmp_path, "state", "approved")
    for field, value in [
        ("audiences", ["Users"]),
        ("outcomes", ["Done"]),
        ("scope.in", ["Core"]),
        ("scope.out", ["Extra"]),
        ("dataClassification", "public"),
        (
            "autonomy",
            dict(
                localGit=True,
                remoteGit="approval-required",
                previewDeploy=True,
                productionDeploy="approval-required",
            ),
        ),
    ]:
        intake.set_charter_field(tmp_path, field, value)
    intake.approve_workspace(tmp_path, "human:me", AT)
    assert intake.set_charter_field(tmp_path, "outcomes", ["Done", "More"])["reopened"]
    assert read_yaml(tmp_path / ".aifw/charter.yaml")["state"] == "draft"


def test_template_copy(tmp_path):
    init(tmp_path)
    specs.create_change(tmp_path, dict(id="feature", title="F", summary="S", level="L3", createdAt=AT))
    assert "threat-model.md" in specs.list_templates()
    created = specs.copy_template(tmp_path, "threat-model.md", change_id="feature")
    assert created["path"].endswith("feature/threat-model.md")
    with pytest.raises(AifwError):
        specs.copy_template(tmp_path, "threat-model.md", change_id="feature")
    with pytest.raises(AifwError):
        specs.copy_template(tmp_path, "../secret", output="x.md")


def test_signals_derived_from_the_diff(tmp_path):
    init(tmp_path)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    assert "frameworkCore" in routing.derive_signals(tmp_path)["signals"]
    subprocess.run(git + ["add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(git + ["commit", "-qm", "init"], cwd=tmp_path, check=True)
    (tmp_path / "src/auth").mkdir(parents=True)
    (tmp_path / "src/auth/login.py").write_text("x = 1\n")
    derived = routing.derive_signals(tmp_path)
    assert {"touchesAuth", "behaviorChange"} <= set(derived["signals"])
    assert routing.classify_change(derived["signals"])["level"] == "L2"


def test_store_python_alias_is_not_used_for_gates(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        gates.shutil, "which", lambda name: r"C:\Users\x\AppData\Local\Microsoft\WindowsApps\python.exe"
    )
    monkeypatch.setattr(
        gates.subprocess,
        "run",
        lambda command, **_: (
            seen.setdefault("cmd", command) and subprocess.CompletedProcess(command, 0, "", "")
        ),
    )
    gates.run_command("python", ["-V"])
    assert seen["cmd"][0] == sys.executable


def test_enable_replaces_outdated_hooks_and_check_reports_gaps(tmp_path):
    init(tmp_path)
    settings = tmp_path / ".claude/settings.json"
    settings.parent.mkdir()
    old = dict(matcher="Bash", hooks=[dict(type="command", command="aifw-hook", timeout=10)])
    settings.write_text(json.dumps(dict(hooks=dict(PreToolUse=[old]))))
    assert check_project(tmp_path, tmp_path / "home")["status"] == "warning"
    enable_project(tmp_path)
    data = json.loads(settings.read_text())
    assert data["hooks"]["PreToolUse"] == [HOOKS["PreToolUse"]]
    findings = check_project(tmp_path, tmp_path / "home")["findings"]
    assert not any(f.startswith("hook ") or "aifw-workflow" in f for f in findings)
    assert any("grilling" in f for f in findings)


def test_init_and_enable_keep_local_logs_out_of_git(tmp_path):
    init(tmp_path)
    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert ".aifw/runs/" in lines and ".aifw/assessments/" in lines
    old = tmp_path / "old"
    old.mkdir()
    init(old)
    (old / ".gitignore").write_text("node_modules\n/.aifw/runs")  # no final newline, leading slash
    assert enable_project(old)["gitignored"] == [".aifw/assessments/"]
    assert (old / ".gitignore").read_text().splitlines()[:2] == ["node_modules", "/.aifw/runs"]
    assert enable_project(old)["gitignored"] == []
    assert (old / ".gitignore").read_text().count(".aifw/assessments/") == 1
