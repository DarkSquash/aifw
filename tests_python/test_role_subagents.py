"""Role subagents installed by `aifw claude enable` (ADR-0038)."""

from hashlib import sha256
from pathlib import Path
import shutil

import pytest
import yaml

from aifw import __version__, assessment, claude
from aifw.claude import AGENTS, HASH, STAMP, check_project, enable_project
from test_workflows import init

EXPECTED = {
    "aifw-explorer": ("haiku", "low"),
    "aifw-quick": ("haiku", "low"),
    "aifw-executor": ("sonnet", "medium"),
    "aifw-adversary": ("opus", "high"),
    "aifw-qa": ("sonnet", "high"),
}


def agent_file(root, name):
    return Path(root) / ".claude/agents" / f"{name}.md"


def frontmatter(path):
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])


def tools(meta):
    return [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]


@pytest.fixture
def project(tmp_path):
    init(tmp_path)
    return tmp_path


def test_enable_installs_the_five_subagents(project):
    result = enable_project(project)
    assert result["agents"] == [f".claude/agents/{n}.md" for n in AGENTS]
    for name, (model, effort) in EXPECTED.items():
        path = agent_file(project, name)
        meta = frontmatter(path)
        assert meta["name"] == name
        assert (meta["model"], meta["effort"]) == (model, effort)
        text = path.read_text(encoding="utf-8")
        body = text.split("\n\n" + STAMP.format(__version__))[0]
        digest = sha256(body.encode()).hexdigest()
        assert text.endswith(f"{STAMP.format(__version__)}\n{HASH.format(digest)}\n")
    assert tools(frontmatter(agent_file(project, "aifw-explorer"))) == ["Read", "Grep", "Glob"]
    for name in ("aifw-adversary", "aifw-qa"):
        assert "Edit" not in tools(frontmatter(agent_file(project, name)))


def test_second_enable_changes_nothing(project):
    enable_project(project)
    before = {n: agent_file(project, n).read_bytes() for n in AGENTS}
    assert enable_project(project)["agentBackups"] == []
    assert before == {n: agent_file(project, n).read_bytes() for n in AGENTS}


def test_edited_copy_is_backed_up_and_restored(project):
    enable_project(project)
    path = agent_file(project, "aifw-executor")
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "\nedited\n", encoding="utf-8", newline="\n")
    result = enable_project(project)
    assert result["agentBackups"] == [".claude/agents/aifw-executor.md.bak"]
    assert path.with_name("aifw-executor.md.bak").read_text(encoding="utf-8") == original + "\nedited\n"
    assert path.read_text(encoding="utf-8") == original


COPIES = [
    (
        "templates/claude/skills/aifw-workflow/SKILL.md",
        ".claude/skills/aifw-workflow/SKILL.md",
        "skillBackup",
    ),
    ("templates/claude/agents/aifw-qa.md", ".claude/agents/aifw-qa.md", "agentBackups"),
]


def backups(result, key):
    found = result[key]
    return found if isinstance(found, list) else [found] if found else []


@pytest.fixture
def newer_assets(project, monkeypatch):
    """Point the installer at a copy of the templates, so a test can change a template."""
    folder = project / "assets"
    shutil.copytree(claude.assets() / "templates", folder / "templates")
    monkeypatch.setattr(claude, "assets", lambda: folder)
    return folder


@pytest.mark.parametrize("template,target,key", COPIES)
def test_new_template_replaces_an_untouched_copy_without_backup(project, newer_assets, template, target, key):
    enable_project(project)
    source = newer_assets / template
    source.write_text(source.read_text(encoding="utf-8") + "\nnew rule\n", encoding="utf-8", newline="\n")
    assert backups(enable_project(project), key) == []
    assert "new rule" in (project / target).read_text(encoding="utf-8")
    assert not (project / (target + ".bak")).exists()


@pytest.mark.parametrize("template,target,key", COPIES)
def test_edited_copy_is_backed_up_even_when_the_template_changed(
    project, newer_assets, template, target, key
):
    enable_project(project)
    path = project / target
    stamp = "\n\n" + STAMP.format(__version__)
    edited = path.read_text(encoding="utf-8").replace(stamp, "\nlocal rule" + stamp)
    path.write_text(edited, encoding="utf-8", newline="\n")
    (newer_assets / template).write_text("different\n", encoding="utf-8", newline="\n")
    assert backups(enable_project(project), key) == [target + ".bak"]
    assert (project / (target + ".bak")).read_text(encoding="utf-8") == edited


@pytest.mark.parametrize("template,target,key", COPIES)
def test_copy_without_a_hash_is_backed_up(project, template, target, key):
    enable_project(project)
    path = project / target
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    old = "".join(line for line in lines if "aifw-sha256" not in line)
    old = old.replace(STAMP.format(__version__), STAMP.format("0.0.1"))
    path.write_text(old, encoding="utf-8", newline="\n")
    assert backups(enable_project(project), key) == [target + ".bak"]
    assert (project / (target + ".bak")).read_text(encoding="utf-8") == old
    findings = check_project(project, project / "home")["findings"]
    assert not any("subagent" in f or "project skill" in f for f in findings)


def test_check_reports_missing_subagents_until_enable(project):
    home = project / "home"
    findings = check_project(project, home)["findings"]
    for name in AGENTS:
        assert any(f"subagent {name}" in f for f in findings)
    enable_project(project)
    assert not any("subagent" in f for f in check_project(project, home)["findings"])


def test_check_reports_a_subagent_from_another_version(project):
    home = project / "home"
    enable_project(project)
    path = agent_file(project, "aifw-qa")
    old = path.read_text(encoding="utf-8").replace(STAMP.format(__version__), STAMP.format("0.0.1"))
    path.write_text(old, encoding="utf-8", newline="\n")
    findings = check_project(project, home)["findings"]
    assert f"subagent aifw-qa is not from aifw {__version__}: run `aifw claude enable`" in findings
    assert enable_project(project)["agentBackups"] == []  # untouched: the hash still matches the body
    assert not any("subagent" in f for f in check_project(project, home)["findings"])


def context(path, risk):
    return assessment.path_context(
        dict(
            status="recorded",
            risk=dict(value=risk),
            finalRisk=risk,
            importance=dict(value="media"),
            complexity=dict(value="simples"),
            path=path,
        )
    )


@pytest.mark.parametrize(
    "path,risk,named",
    [
        ("FAST", "L0", ["aifw-quick"]),
        ("WORK", "L1", ["aifw-executor"]),
        ("PLANNED", "L2", ["aifw-executor", "aifw-quick", "aifw-adversary", "aifw-qa", "Opus planeja"]),
        ("CRITICAL", "L3", ["aifw-executor", "aifw-quick", "aifw-adversary", "aifw-qa", "Opus planeja"]),
    ],
)
def test_path_context_names_the_subagents(path, risk, named):
    text = context(path, risk)
    for item in named:
        assert item in text


def test_workflow_skill_documents_the_subagents():
    skill = (Path(__file__).parents[1] / "templates/claude/skills/aifw-workflow/SKILL.md").read_text(
        encoding="utf-8"
    )
    for item in (*AGENTS, "subagent_type", "terceira reprovação"):
        assert item in skill
