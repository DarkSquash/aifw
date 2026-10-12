from copy import deepcopy

import pytest

from aifw.common import AifwError
from aifw.policy import resolve_framework


def rule(statement, overridable=True):
    return dict(
        id="test.rule",
        version="1.0.0",
        keyword="MUST",
        statement=statement,
        scope=["project"],
        rationale="Test",
        owner="human:test",
        enforcement=dict(mode="hard", evidence=["test"]),
        source="test",
        overridable=overridable,
    )


def inputs():
    return dict(coreRules=[], personalRules=[], profiles=[], projectRules=[])


def profile(name, **overrides):
    value = dict(id=name, version="1.0.0", kind="stack", provides=[], requires=[], conflicts=[], rules=[])
    value.update(overrides)
    return value


def test_project_overrides_personal_default():
    data = inputs()
    data.update(personalRules=[rule("Personal")], projectRules=[rule("Project")])
    result = resolve_framework(data)["rules"][0]
    assert result["statement"] == "Project" and result["origin"] == "project"


def test_core_invariant_blocks_override_but_accepts_identical_definition():
    core = rule("Invariant", False)
    data = inputs()
    data.update(coreRules=[core], projectRules=[rule("Changed")])
    with pytest.raises(AifwError):
        resolve_framework(data)
    data["projectRules"] = [deepcopy(core)]
    assert resolve_framework(data)["rules"][0]["origin"] == "core"


@pytest.mark.parametrize(
    "profiles",
    [
        [profile("one", conflicts=["two"]), profile("two")],
        [profile("one", requires=["missing"])],
        [profile("one", rules=[rule("One")]), profile("two", rules=[rule("Two")])],
    ],
)
def test_conflicting_profiles_fail(profiles):
    data = inputs()
    data["profiles"] = profiles
    with pytest.raises(AifwError):
        resolve_framework(data)


def test_profile_order_does_not_change_lock():
    data = inputs()
    data["profiles"] = [profile("two", requires=["base"]), profile("one", provides=["base"])]
    first = resolve_framework(data)
    data["profiles"].reverse()
    assert resolve_framework(data) == first
