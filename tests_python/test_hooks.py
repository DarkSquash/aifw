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
        ('git commit -m "x"', "commit"),
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
    assert decision(tmp_path, "Bash", command="aifw intake approve --by human:me") == "deny"
    assert decision(tmp_path, "WebFetch", url="https://unknown.example/x") == "ask"
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    policy["remoteMutation"] = "denied"
    write_yaml(tmp_path / ".aifw/permissions.yaml", policy)
    assert decision(tmp_path, "Bash", command="git push") == "deny"


def test_broken_policy_asks_instead_of_passing(tmp_path):
    init(tmp_path)
    (tmp_path / ".aifw/permissions.yaml").write_text("kind: nonsense\n")
    assert decision(tmp_path, "Edit", file_path="a.py") == "ask"


def test_impasse_lifecycle_freezes_and_releases_mutations(tmp_path, monkeypatch):
    monkeypatch.setattr("aifw.cli.confirm_human", lambda *_: None)
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
    pre = [h["hooks"][0] for h in data["hooks"]["PreToolUse"]]
    assert len(pre) == 1 and pre[0]["command"].startswith("aifw-hook ||") and pre[0]["onFailure"] == "block"
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
        ("Edit", dict(file_path=".aifw/charter.yaml"), "ask"),
    ],
)
def test_hook_guards_aifw_control_files(tmp_path, tool, tool_input, expected):
    init(tmp_path)
    assert decision(tmp_path, tool, **tool_input) == expected


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("pip install requests", "ask"),
        ("npx create-next-app demo", "ask"),
        ("winget install Git.Git", "ask"),
        ("git clone https://github.com/a/b", "ask"),
        ('git commit -m "x"', "ask"),
        ("git rebase main", "ask"),
        ("git add -A", None),
        ("uv sync", None),
        ("python -m pytest -q", None),
    ],
)
def test_installs_and_commits_need_the_person(tmp_path, command, expected):
    init(tmp_path)
    set_allowlist = read_yaml(tmp_path / "aifw.yaml")
    set_allowlist["spec"]["externalAllowlist"] = ["github", "package-registry"]
    write_yaml(tmp_path / "aifw.yaml", set_allowlist)  # allowlisting a registry no longer skips the question
    assert decision(tmp_path, "Bash", command=command) == expected


def test_opaque_code_asks_unless_the_project_allows_it(tmp_path):
    init(tmp_path)
    command = "python -c \"import subprocess; subprocess.run(['x'])\""
    assert decision(tmp_path, "Bash", command=command) == "ask"
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    write_yaml(tmp_path / ".aifw/permissions.yaml", dict(policy, opaqueCode="allow"))
    assert decision(tmp_path, "Bash", command=command) is None
    assert decision(tmp_path, "Bash", command="pip install x") == "ask"
    hidden = "python -c \"import os; os.system('aifw intake approve --by human:me')\""
    assert decision(tmp_path, "Bash", command=hidden) == "deny"


def test_commits_allowed_by_policy_still_ask_with_control_files_changed(tmp_path):
    init(tmp_path)
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    write_yaml(tmp_path / ".aifw/permissions.yaml", dict(policy, commits="allow"))
    command = 'git commit -m "x"'
    assert decision(tmp_path, "Bash", command=command) == "ask"  # no git repository
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run(
        ["git", "init", "-q"], cwd=tmp_path, check=True, stdin=subprocess.DEVNULL, capture_output=True
    )
    subprocess.run(
        ["git", "add", "-A"], cwd=tmp_path, check=True, stdin=subprocess.DEVNULL, capture_output=True
    )
    subprocess.run(
        [*git, "commit", "-qm", "init"],
        cwd=tmp_path,
        check=True,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    (tmp_path / "app.py").write_text("x = 1\n")
    assert decision(tmp_path, "Bash", command=command) is None
    assert decision(tmp_path, "Bash", command="git push") == "ask"
    assert decision(tmp_path, "Bash", command="git commit -S -m x") == "ask"
    assert decision(tmp_path, "Bash", command="git add -A && git commit -m x") is None
    assert decision(tmp_path, "Bash", command="python gen.py && git commit -am x") == "ask"
    (tmp_path / ".aifw/waivers").mkdir(exist_ok=True)
    (tmp_path / ".aifw/waivers/w.yaml").write_text("id: w\n")
    assert decision(tmp_path, "Bash", command=command) == "ask"


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("npx ctx7@latest library react", None),
        ("npx -y ctx7 docs /vercel/next.js routing", None),
        ("npx create-next-app demo", "ask"),
        ("npx --package=evil ctx7 library x", "ask"),
        ("npx -p evil ctx7", "ask"),
        ("pip install ctx7", "ask"),
    ],
)
def test_trusted_packages_run_without_asking(tmp_path, command, expected):
    init(tmp_path)
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    write_yaml(tmp_path / ".aifw/permissions.yaml", dict(policy, trustedPackages=["ctx7"]))
    assert decision(tmp_path, "Bash", command=command) == expected


def test_validation_cache_follows_the_schema(tmp_path, monkeypatch):
    from aifw import common

    monkeypatch.setattr(common.Path, "home", lambda: tmp_path / "home")
    (tmp_path / "schemas").mkdir()
    schema = tmp_path / "schemas" / "x.schema.json"
    schema.write_text('{"type": "object"}')
    monkeypatch.setattr(common, "assets", lambda: tmp_path)
    monkeypatch.setattr(common, "validate", lambda value, name: value)
    file = tmp_path / "doc.yaml"
    file.write_text("a: 1\n")
    common.read_valid_yaml(file, "x.schema.json")
    calls = []
    monkeypatch.setattr(common, "validate", lambda value, name: calls.append(name) or value)
    common.read_valid_yaml(file, "x.schema.json")
    assert calls == []  # same schema, same content: cached
    schema.write_text('{"type": "object", "required": ["b"]}')
    common.read_valid_yaml(file, "x.schema.json")
    assert calls == ["x.schema.json"]  # a changed schema validates again


def test_every_subprocess_gets_its_own_stdin():
    # An inherited stdin can be an invalid handle on Windows (WinError 6), which made git look absent.
    from pathlib import Path

    for file in (Path(__file__).parents[1] / "python/aifw").glob("*.py"):
        text = file.read_text(encoding="utf-8")
        assert text.count("subprocess.run(") == text.count("stdin=subprocess.DEVNULL"), file.name


def test_repeated_failures_reset_after_a_pass():
    from aifw.hooks import streak

    run = [
        dict(command="pytest", ok=False),
        dict(command="pytest", ok=True),
        dict(command="pytest", ok=False),
    ]
    assert streak(run, "pytest") == 1
    assert streak([*run, dict(command="pytest", ok=False)], "pytest") == 2
    assert streak([*run, dict(command="other", ok=False), dict(command="pytest", ok=None)], "pytest") == 1
