"""Exercise an installed release outside the checkout, with Node absent from PATH.

Usage: <isolated-env-python> scripts/verify_wheel.py
The caller installs the wheel in that environment first.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def verify():
    # Keep only Python scripts and the OS tools needed to start Python on Windows.
    scripts = Path(sys.executable).parent
    command = scripts / ("aifw.exe" if os.name == "nt" else "aifw")
    env = dict(os.environ, PATH=str(scripts), PYTHONPATH="", PYTHONUTF8="1")
    assert shutil.which("node", path=env["PATH"]) is None
    with tempfile.TemporaryDirectory(prefix="aifw-wheel-") as directory:
        command_count = 0

        def run(*args, expected=0):
            nonlocal command_count
            command_count += 1
            result = subprocess.run(
                [str(command), *args],
                cwd=directory,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=60,
            )
            assert result.returncode == expected, result.stderr or result.stdout
            return result.stdout

        assert run("--version").strip() == "0.4.1"
        run("init", "--id", "installed", "--name", "Installed", "--python", "--json")
        run("map", "check", "--json")
        run("resolve", "build", "--json")
        run("resolve", "check", "--json")
        run("principle", "list", "--json")
        run("decision", "list", "--json")
        run("intake", "status", "--json", expected=2)
        assert json.loads(run("route", "eval", "--json"))["passed"] == 32
        assert json.loads(run("eval", "--json"))["pass"]
        project = Path(directory)
        (project / "docs").mkdir(exist_ok=True)
        (project / "docs/login.md").write_text("---\nscope: login\n---\n# Login\n", encoding="utf-8")
        (project / ".aifw/project-instructions.md").write_text("# Local rules\n", encoding="utf-8")
        run("instructions", "build", "--json")
        run("instructions", "check", "--json")
        run("context", "index", "--write", "--json")
        run("context", "check", "--json")
        selected = json.loads(run("context", "select", "--task", "login", "--json"))
        assert any(doc["path"] == "docs/login.md" for doc in selected["selected"])
        run("gates", "check", "--level", "L1", "--json", expected=2)
        import aifw
        from aifw.common import assets

        assert Path(aifw.__file__).is_relative_to(Path(sys.prefix))
        assert (assets() / "templates/project-scaffold.json").is_file()
        assert (assets() / "schemas/context-index.schema.json").is_file()
        assert (assets() / "templates/context/project-instructions.md").is_file()
        print(
            json.dumps(
                dict(
                    status="pass",
                    version="0.4.1",
                    nodeOnPath=False,
                    isolatedPackage=str(aifw.__file__),
                    commands=command_count,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    verify()
