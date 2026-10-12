import json
import subprocess
import sys

import pytest

from aifw.cli import create_parser, execute
from aifw.common import read_yaml, write_yaml
from aifw.hooks import classify, handle
from test_workflows import AT, init


def run(root, *args):
    return execute(create_parser().parse_args([*args, "--json"]), root)


def decision(root, tool, **tool_input):
    output = handle(dict(cwd=str(root), tool_name=tool, tool_input=tool_input))
    return output and output["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize(
    ("command", "kind"),
    [
        ("git status && git diff", "read-only"),
        ("git push origin main", "git-remote"),
        ('git commit -m "x"', "git-local"),
        ("rm -rf build", "filesystem-write"),
        ("vercel deploy --prod", "deploy"),
        ("curl -X POST https://api.github.com/repos", "external-write"),
        ("echo hi > notes.txt", "filesystem-write"),
    ],
)
def test_shell_classification(command, kind):
    assert classify("Bash", dict(command=command), ["github"])["kind"] == kind


def test_hook_is_silent_outside_aifw_projects(tmp_path):
    assert decision(tmp_path, "Bash", command="git push --force") is None


def test_hook_applies_permission_policy(tmp_path):
    init(tmp_path)
    assert decision(tmp_path, "Edit", file_path="a.py") is None
    assert decision(tmp_path, "Bash", command="git status") is None
    assert decision(tmp_path, "Bash", command="git push") == "ask"
    assert decision(tmp_path, "Bash", command="rm -rf src") == "ask"
    assert decision(tmp_path, "Bash", command="aifw intake approve --by human:me") == "ask"
    assert decision(tmp_path, "WebFetch", url="https://unknown.example/x") == "ask"
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    policy["remoteMutation"] = "denied"
    write_yaml(tmp_path / ".aifw/permissions.yaml", policy)
    assert decision(tmp_path, "Bash", command="git push") == "deny"


def test_broken_policy_asks_instead_of_passing(tmp_path):
    init(tmp_path)
    (tmp_path / ".aifw/permissions.yaml").write_text("kind: nonsense\n")
    assert decision(tmp_path, "Edit", file_path="a.py") == "ask"


def test_impasse_lifecycle_freezes_and_releases_mutations(tmp_path):
    init(tmp_path)
    assert run(tmp_path, "impasse", "open", "--id", "login", "--impact", "L2")[0]["state"] == "NORMAL"
    for n in (1, 2):
        case, code = run(
            tmp_path,
            *("impasse", "attempt", "--id", "login", "--outcome", "failure", "--at", AT),
            *("--hypothesis", f"cause {n}", "--intervention", f"fix {n}", "--evidence", "log.txt"),
        )
    assert case["state"] == "OPEN" and code == 2
    assert decision(tmp_path, "Edit", file_path="a.py") == "deny"
    assert decision(tmp_path, "Bash", command="python build.py") == "ask"
    assert decision(tmp_path, "Bash", command="aifw impasse status") is None
    assert run(tmp_path, "impasse", "status")[0]["frozen"] == ["impasse:login"]
    run(
        tmp_path,
        *("impasse", "review", "--id", "login", "--rule", "ui.radius"),
        *("--explanation", "rule conflicts", "--proposal", "relax radius"),
    )
    (tmp_path / "decision.md").write_text("approved")
    run(
        tmp_path,
        "impasse",
        "decide",
        "--id",
        "login",
        "--by",
        "human:me",
        "--record",
        "decision.md",
        "--at",
        AT,
    )
    assert decision(tmp_path, "Edit", file_path="a.py") is None
    assert decision(tmp_path, "Bash", command="rm -rf src") == "deny"
    case, code = run(
        tmp_path,
        *("impasse", "revalidate", "--id", "login", "--result", "passed"),
        *("--evidence", "tests.log", "--artifacts", "policy.yaml"),
    )
    assert case["state"] == "RESOLVED" and code == 0
    assert decision(tmp_path, "Bash", command="rm -rf src") == "ask"


def test_hook_entrypoint_speaks_claude_code_json(tmp_path):
    init(tmp_path)
    payload = json.dumps(dict(cwd=str(tmp_path), tool_name="Bash", tool_input=dict(command="git push")))
    result = subprocess.run(
        [sys.executable, "-m", "aifw.hooks"], input=payload, text=True, capture_output=True, check=True
    )
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_claude_enable_is_per_project_and_idempotent(tmp_path):
    from aifw.claude import enable_project, install_command
    from aifw.common import AifwError

    with pytest.raises(AifwError):
        enable_project(tmp_path)
    init(tmp_path)
    settings = tmp_path / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text('{"model": "opus", "hooks": {"Stop": []}}')
    assert "PreToolUse" in enable_project(tmp_path)["hooksChanged"]
    assert enable_project(tmp_path)["hooksChanged"] == []
    data = json.loads(settings.read_text())
    assert data["model"] == "opus"
    assert [h["hooks"][0]["command"] for h in data["hooks"]["PreToolUse"]] == ["aifw-hook"]
    assert "name: aifw-workflow" in (tmp_path / ".claude/skills/aifw-workflow/SKILL.md").read_text("utf-8")
    home = tmp_path / "home"
    install_command(home)
    assert "disable-model-invocation: true" in (home / ".claude/skills/aifw/SKILL.md").read_text("utf-8")


def test_claude_enable_refuses_malformed_settings(tmp_path):
    from aifw.claude import enable_project
    from aifw.common import AifwError

    init(tmp_path)
    settings = tmp_path / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text("{broken")
    with pytest.raises(AifwError):
        enable_project(tmp_path)
    assert settings.read_text() == "{broken"


@pytest.mark.parametrize(
    ("tool", "tool_input", "expected"),
    [
        ("Edit", dict(file_path=".aifw/permissions.yaml"), "ask"),
        ("Write", dict(file_path=".aifw/impasses/login.yaml"), "ask"),
        ("Edit", dict(file_path=".aifw/changes/active/x/evidence/validation.json"), "ask"),
        ("Edit", dict(file_path=".claude/settings.json"), "ask"),
        ("Bash", dict(command=r"echo enabled > .aifw\routing.yaml"), "ask"),
        ("Bash", dict(command="cat .aifw/permissions.yaml"), None),
        ("Edit", dict(file_path=".aifw/changes/active/x/proposal.md"), None),
        ("Edit", dict(file_path=".aifw/charter.yaml"), None),
    ],
)
def test_hook_guards_aifw_control_files(tmp_path, tool, tool_input, expected):
    init(tmp_path)
    assert decision(tmp_path, tool, **tool_input) == expected
