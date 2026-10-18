import json
import subprocess

import pytest

from aifw import brownfield, impasse, permissions
from aifw.claude import enable_project
from aifw.common import read_yaml, write_yaml
from aifw.hooks import handle
from aifw.shell import analyze, service_of
from test_workflows import AT, init

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def pre(root, tool, **tool_input):
    out = handle(dict(cwd=str(root), tool_name=tool, tool_input=tool_input))
    return out and out["hookSpecificOutput"]["permissionDecision"]


def policy(root, **values):
    data = read_yaml(root / ".aifw/permissions.yaml")
    data.update(values)
    write_yaml(root / ".aifw/permissions.yaml", data)


@pytest.mark.parametrize(
    ("command", "kind"),
    [
        ("echo $(git push)", "git-remote"),
        ("echo `git push`", "git-remote"),
        ("cat <(git push)", "git-remote"),
        ("cd $(git rev-parse --show-toplevel)", "read-only"),
        ("ls src/{a,b}", "read-only"),
        ("echo ${HOME}", "read-only"),
        ("G=git; $G push", "opaque"),
        ("Invoke-Command -ScriptBlock { git push }", "git-remote"),
        ("Invoke-Command -ComputerName srv -ScriptBlock { dir }", "external-write"),
        ("&{ git push }", "git-remote"),
        ("{ echo a; echo b; }", "read-only"),
        ("$(echo git) push", "opaque"),
        (". ./deploy.ps1", "opaque"),
        ("printenv", "secret-read"),
        ("env", "secret-read"),
        ("Get-ChildItem env:", "secret-read"),
        ("git commit -S -m x", "signing"),
        ("git -c commit.gpgsign=true commit -m x", "signing"),
        ("git commit -m x", "commit"),
    ],
)
def test_embedded_code_variables_and_signing(command, kind):
    assert analyze(command)["kind"] == kind


def test_allowlist_matches_domains_not_labels():
    assert service_of("https://api.github.com/x", ["github"]) == "github"
    assert service_of("https://raw.githubusercontent.com/x", ["github"]) == "github"
    assert service_of("https://github.attacker.example/x", ["github"]) != "github"
    assert service_of("https://docs.internal.example/x", {"docs": ["internal.example"]}) == "docs"


def test_custom_service_domains_and_protected_paths(tmp_path):
    init(tmp_path)
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"]["externalAllowlist"] = ["docs"]
    write_yaml(tmp_path / "aifw.yaml", manifest)
    policy(tmp_path, serviceDomains=dict(docs=["internal.example"]), protectedPaths=["src/core/"])
    assert pre(tmp_path, "WebFetch", url="https://wiki.internal.example/a") is None
    assert pre(tmp_path, "Edit", file_path="src/core/engine.py") == "ask"
    assert pre(tmp_path, "Edit", file_path="src/ui/view.py") is None


def test_grep_and_glob_on_secret_files_ask(tmp_path):
    init(tmp_path)
    assert pre(tmp_path, "Grep", pattern="KEY", path=".env") == "ask"
    assert pre(tmp_path, "Glob", pattern="**/*.pem") == "ask"
    assert pre(tmp_path, "Grep", pattern="TODO", path="src") is None


def test_break_glass_use_is_logged(tmp_path):
    init(tmp_path)
    grant = dict(incidentId="inc-9", scope=["git-remote"], reason="outage", approvedBy="human:me")
    permissions.grant_break_glass(tmp_path, dict(grant, approvedAt=AT, expiresAt="2999-01-01T00:00:00Z"))
    assert pre(tmp_path, "Bash", command="git push origin hotfix") is None
    entry = json.loads((tmp_path / ".aifw/break-glass/inc-9.log").read_text().splitlines()[0])
    assert entry["kind"] == "git-remote" and "git push" in entry["detail"]


def test_signed_mode_covers_impasse_decisions_and_adoption(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="x"\nversion="1"\n')
    init(tmp_path, "python", True)
    brownfield.write_analysis(tmp_path, AT)
    brownfield.apply_mapping(tmp_path, AT)
    brownfield.approve_mapping(tmp_path, "human:me", AT)
    case = impasse.create_impasse_case("impasse:x", "L2")
    case = dict(
        case, state="HALF_OPEN", humanDecision=dict(decidedBy="human:me"), stopDestructiveChanges=True
    )
    impasse.save_case(tmp_path, case)
    assert pre(tmp_path, "Edit", file_path="app.py") is None
    policy(tmp_path, approvals=dict(requireSignedCommit=True))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(GIT + ["add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(GIT + ["commit", "-qm", "unsigned"], cwd=tmp_path, check=True)
    assert pre(tmp_path, "Edit", file_path="app.py") == "deny"
    assert brownfield.assess_adoption(tmp_path)["status"] == "invalid"


def test_enable_backs_up_an_edited_project_skill(tmp_path):
    init(tmp_path)
    assert enable_project(tmp_path)["skillBackup"] is None
    skill = tmp_path / ".claude/skills/aifw-workflow/SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal rule\n", encoding="utf-8")
    result = enable_project(tmp_path)
    assert result["skillBackup"] and "local rule" in (tmp_path / result["skillBackup"]).read_text(
        encoding="utf-8"
    )
