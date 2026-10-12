import pytest

from aifw.common import read_yaml, write_yaml
from aifw.hooks import handle
from aifw.shell import analyze
from test_workflows import init


def pre(root, tool, **tool_input):
    out = handle(dict(cwd=str(root), tool_name=tool, tool_input=tool_input))
    return out and out["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize(
    ("command", "kind", "approval"),
    [
        ('script -qec "git push" /dev/null', "git-remote", False),
        ('script -c "aifw intake approve --by human:x" /dev/null', "read-only", True),
        ("script /dev/null", "opaque", False),
        ('expect -c "spawn aifw"', "opaque", False),
        ("unbuffer aifw intake approve", "opaque", False),
        ('python -c "print(2 + 2)"', "read-only", False),
        ("python -c \"open('x.txt', 'w').write('a')\"", "filesystem-write", False),
        ('python -c "import urllib.request"', "external-write", False),
        ("node -e \"require('child_process').execSync('ls')\"", "opaque", False),
        ('python -c "from aifw import intake; intake.approve_workspace(1, 2, 3)"', "read-only", True),
        ('perl -e "print 1"', "opaque", False),
    ],
)
def test_pseudo_terminals_and_inline_code(command, kind, approval):
    result = analyze(command)
    assert result["kind"] == kind and result["approval"] == approval


def test_external_actions_outside_the_allowlist_ask_unless_data_is_sensitive(tmp_path):
    init(tmp_path)
    assert pre(tmp_path, "Bash", command="npm publish") == "ask"
    assert pre(tmp_path, "Bash", command="scp dump.sql host:/tmp") == "ask"
    assert pre(tmp_path, "Bash", command="curl -X POST https://unknown.example/x") == "ask"
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"]["dataClassification"] = "confidential"
    write_yaml(tmp_path / "aifw.yaml", manifest)
    assert pre(tmp_path, "Bash", command="npm publish") == "deny"


def test_approval_through_a_pseudo_terminal_is_denied(tmp_path):
    init(tmp_path)
    command = 'printf "aifw\\n" | script -qec "aifw intake approve --by human:x" /dev/null'
    assert pre(tmp_path, "Bash", command=command) == "deny"
