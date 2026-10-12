"""Bundle authoritative framework documents without duplicating source assets."""

from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

ASSET_DIRS = (
    "schemas",
    "templates",
    "profiles",
    "decision-catalogs",
    "principle-catalogs",
    "policies",
    "evals",
)


class BuildWithAssets(build_py):
    def run(self):
        super().run()
        root = Path(__file__).parent
        target = Path(self.build_lib) / "aifw/data"
        for name in ASSET_DIRS:
            shutil.copytree(root / name, target / name, dirs_exist_ok=True)
        for name in ("CONSTITUTION.md", "LICENSE"):
            shutil.copy2(root / name, target / name)


setup(cmdclass={"build_py": BuildWithAssets})
