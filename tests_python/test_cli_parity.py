import json
from pathlib import Path

from aifw.cli import create_parser, execute
from aifw.common import read_yaml, write_yaml
from aifw.workspace import build_workspace_map
from test_workflows import init


def test_document_and_catalog_commands_match_typescript(tmp_path):
    init(tmp_path)
    # The golden CLI ran v0.2.0. Map content intentionally includes the pin.
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"]["frameworkVersion"] = "0.2.0"
    write_yaml(tmp_path / "aifw.yaml", manifest)
    build_workspace_map(tmp_path, write=True)
    cases = json.loads((Path(__file__).parent / "fixtures/cli-parity.json").read_text(encoding="utf-8"))
    for case in cases:
        actual, code = execute(create_parser().parse_args([*case["args"], "--json"]), tmp_path)
        assert code == case["code"], case["args"]
        assert actual == case["output"], case["args"]
