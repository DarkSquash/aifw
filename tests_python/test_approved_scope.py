"""Edits stay inside the approved plan's paths; the approved tasks.yaml is a control file (ADR-0039)."""

import pytest

from aifw.common import read_yaml, write_yaml
from aifw.hooks import handle
from test_workflows import init

PATHS = ["python/aifw/claude.py", "docs/", "templates/claude/agents/*.md"]


@pytest.fixture
def project(tmp_path):
    init(tmp_path)
    return tmp_path


def add_change(root, change_id, approved=True, paths=PATHS):
    folder = root / ".aifw/changes/active" / change_id
    folder.mkdir(parents=True)
    change = dict(metadata=dict(id=change_id), status="draft")
    if approved:
        change["approval"] = dict(approvedBy="human:x", approvedAt="2026-10-25T00:00:00Z", record="x")
    write_yaml(folder / "change.yaml", change)
    write_yaml(folder / "tasks.yaml", dict(changeId=change_id, tasks=[dict(id="TASK-X", paths=paths)]))
    return folder


def edit(root, path, tool="Edit", agent_id="sub"):
    tool_input = dict(file_path=str(root / path), old_string="a", new_string="b", content="x")
    output = handle(
        dict(cwd=str(root), session_id="s", agent_id=agent_id, tool_name=tool, tool_input=tool_input)
    )
    return output and output["hookSpecificOutput"]


@pytest.mark.parametrize(
    "path",
    [
        "python/aifw/claude.py",
        "docs/x.md",
        "docs/deep/y.md",
        "templates/claude/agents/aifw-qa.md",
        ".aifw/changes/active/plan/evidence/tests.txt",
        ".aifw/changes/active/other/proposal.md",
    ],
)
def test_planned_paths_and_change_folders_do_not_ask(project, path):
    add_change(project, "plan")
    assert edit(project, path) is None


def test_edit_outside_the_plan_asks(project):
    add_change(project, "plan")
    out = edit(project, "python/aifw/hooks.py")
    assert out["permissionDecision"] == "ask"
    assert "outside the approved plan of plan" in out["permissionDecisionReason"]
    assert edit(project, "python/aifw/hooks.py", tool="Write")["permissionDecision"] == "ask"


def test_without_an_approved_change_nothing_asks(project):
    assert edit(project, "python/aifw/hooks.py") is None
    add_change(project, "draft", approved=False)
    assert edit(project, "python/aifw/hooks.py") is None
    assert edit(project, ".aifw/changes/active/draft/tasks.yaml") is None


def test_change_scope_off(project):
    add_change(project, "plan")
    policy_file = project / ".aifw/permissions.yaml"
    policy = read_yaml(policy_file)
    policy["changeScope"] = "off"
    write_yaml(policy_file, policy)
    assert edit(project, "python/aifw/hooks.py") is None
    assert edit(project, ".aifw/changes/active/plan/tasks.yaml") is None


def test_dot_slash_paths_match(project):
    add_change(project, "plan", paths=["./docs/", r".\python\aifw\claude.py"])
    assert edit(project, "docs/x.md") is None
    assert edit(project, "python/aifw/claude.py") is None


def test_paths_of_every_approved_change_count(project):
    add_change(project, "plan")
    add_change(project, "other", paths=["python/aifw/hooks.py"])
    assert edit(project, "python/aifw/hooks.py") is None
    assert "approved plan of other, plan" in edit(project, "README.md")["permissionDecisionReason"]


TASKS = "changeId: plan\ntasks:\n- id: TASK-X\n  status: pending\n  paths:\n  - docs/\n  - python/aifw/claude.py\n"
TASKS_FILE = ".aifw/changes/active/plan/tasks.yaml"


def plan_call(root, tool, **tool_input):
    tool_input["file_path"] = str(root / TASKS_FILE)
    out = handle(dict(cwd=str(root), session_id="s", agent_id="sub", tool_name=tool, tool_input=tool_input))
    return out and out["hookSpecificOutput"]


def swap(old, new):
    return dict(old_string=old, new_string=new)


def planned(root):
    add_change(root, "plan")
    (root / TASKS_FILE).write_text(TASKS, encoding="utf-8")


def asks(out):
    assert out["permissionDecision"] == "ask"
    assert "tasks.yaml of the approved change plan" in out["permissionDecisionReason"]


def test_status_edits_of_the_approved_plan_do_not_ask(project):
    planned(project)
    assert plan_call(project, "Edit", **swap("status: pending", "status: done")) is None
    assert plan_call(project, "Write", content=TASKS.replace("pending", "done")) is None
    edits = [swap("status: pending", "status: running"), swap("running", "done")]
    assert plan_call(project, "MultiEdit", edits=edits) is None


def test_path_edits_of_the_approved_plan_ask(project):
    planned(project)
    asks(plan_call(project, "Edit", **swap("  - docs/\n", "  - docs/\n  - README.md\n")))
    asks(plan_call(project, "Edit", **swap("- docs/", "- src/")))
    asks(plan_call(project, "Write", content=TASKS.replace("docs/", "src/")))
    edits = [swap("pending", "done"), swap("- docs/", "- src/")]
    asks(plan_call(project, "MultiEdit", edits=edits))


def test_duplicate_key_asks_and_keeps_the_plan_on(project):
    planned(project)
    asks(plan_call(project, "Edit", **swap("status: pending\n", "status: pending\n  status: done\n")))
    assert edit(project, "python/aifw/hooks.py")["permissionDecision"] == "ask"


BLOCK = "- id: TASK-X\n  status: pending\n  paths:\n  - docs/\n  - python/aifw/claude.py\n"


def test_duplicate_or_idless_tasks_with_paths_ask(project):
    planned(project)
    extra = BLOCK.replace("  - docs/\n", "  - docs/\n  - README.md\n")
    asks(plan_call(project, "Edit", **swap(BLOCK, BLOCK + extra)))
    asks(plan_call(project, "Write", content=TASKS + extra))
    asks(plan_call(project, "Write", content=TASKS + "- status: pending\n  paths:\n  - README.md\n"))


def test_title_edits_of_the_approved_plan_do_not_ask(project):
    planned(project)
    assert (
        plan_call(project, "Edit", **swap("  status: pending\n", "  title: Novo\n  status: pending\n"))
        is None
    )
    assert plan_call(project, "Edit", **swap("TASK-X\n", "TASK-X\n  title: A\n")) is None


def test_edits_that_do_not_apply_ask(project):
    planned(project)
    asks(plan_call(project, "Edit", **swap("status: missing", "status: done")))
    asks(plan_call(project, "Edit", **swap("", "x")))
    asks(plan_call(project, "Write", content="tasks: ["))


def test_the_approved_plan_is_a_control_file_in_the_shell(project):
    planned(project)
    command = "sed -i 's/pending/done/' .aifw/changes/active/plan/tasks.yaml"
    shell = handle(dict(cwd=str(project), session_id="s", tool_name="Bash", tool_input=dict(command=command)))
    asks(shell["hookSpecificOutput"])


def test_change_scope_off_lets_every_plan_edit_through(project):
    planned(project)
    policy_file = project / ".aifw/permissions.yaml"
    policy = read_yaml(policy_file)
    policy["changeScope"] = "off"
    write_yaml(policy_file, policy)
    assert plan_call(project, "Edit", **swap("- docs/", "- src/")) is None
    assert plan_call(project, "Edit", **swap("status: missing", "x")) is None
    assert plan_call(project, "Write", content="tasks: [") is None


def test_a_broken_change_is_left_out(project):
    folder = add_change(project, "plan")
    (folder / "tasks.yaml").write_text("tasks: [", encoding="utf-8")
    assert edit(project, "python/aifw/hooks.py") is None


def test_files_outside_the_project_do_not_ask(project, tmp_path_factory):
    add_change(project, "plan")
    outside = tmp_path_factory.mktemp("probe") / "probe.py"  # absolute, so project / outside is outside
    assert edit(project, outside, tool="Write") is None
