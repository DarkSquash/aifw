from pathlib import Path
import json
import pytest
from aifw.routing import route_task, classify_change
from aifw.permissions import authorize_action

GOLDEN = json.loads((Path(__file__).parent / "fixtures/legacy-parity.json").read_text())


@pytest.mark.parametrize("case", GOLDEN["routing"])
def test_routing_matches_typescript(case):
    assert route_task(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", GOLDEN["classification"])
def test_classification_matches_typescript(case):
    assert classify_change(case["input"]) == case["expected"]


@pytest.mark.parametrize("case", GOLDEN["permissions"])
def test_permissions_match_typescript(case):
    assert authorize_action(case["request"], case["policy"]) == case["expected"]
