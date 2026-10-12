"""Read-only inventory. Filenames establish facts, never semantic ownership."""

import os
from pathlib import Path, PurePosixPath
import re

from .common import read_json, read_yaml


def inventory(root):
    root = Path(root)
    result = []
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [
            d
            for d in dirs
            if d
            not in {
                "node_modules",
                ".git",
                ".aifw",
                ".venv",
                "venv",
                "__pycache__",
                ".pytest_cache",
                "build",
                ".ruff_cache",
            }
            and not (Path(base) / d).is_symlink()
        ]
        result.extend(
            (Path(base) / name).relative_to(root).as_posix()
            for name in files
            if not (Path(base) / name).is_symlink()
        )
    return sorted(result)


def discover_project(root):
    root = Path(root)
    files = inventory(root)
    package = read_json(root / "package.json") if (root / "package.json").is_file() else {}
    pubspec = (read_yaml(root / "pubspec.yaml") or {}) if (root / "pubspec.yaml").is_file() else {}
    flutter = (
        (pubspec.get("dependencies", {}).get("flutter") or {}).get("sdk") == "flutter"
        if isinstance(pubspec.get("dependencies", {}).get("flutter", {}), dict)
        else False
    )
    flutter_test = pubspec.get("dev_dependencies", {}).get("flutter_test", {})
    flutter = flutter or (isinstance(flutter_test, dict) and flutter_test.get("sdk") == "flutter")
    stacks = (
        (["node"] if (root / "package.json").exists() else [])
        + (["dart"] if (root / "pubspec.yaml").exists() else [])
        + (["flutter"] if flutter else [])
        + (["python"] if (root / "pyproject.toml").exists() else [])
    )
    package_manager = next(
        (
            manager
            for file, manager in [
                ("pnpm-lock.yaml", "pnpm"),
                ("yarn.lock", "yarn"),
                ("package-lock.json", "npm"),
                ("bun.lock", "bun"),
                ("bun.lockb", "bun"),
            ]
            if file in files
        ),
        "unknown",
    )
    contracts, ci, adrs, manifests, entrypoints, configs, docs = [], [], [], [], [], [], []
    for file in files:
        p = PurePosixPath(file)
        name = p.name
        if re.fullmatch(r"(?:openapi|asyncapi).*\.(?:yaml|yml|json)", name) or p.suffix in {
            ".graphql",
            ".proto",
        }:
            contracts.append(file)
        if (
            file.startswith(".github/workflows/") and len(p.parts) == 3 and p.suffix in {".yml", ".yaml"}
        ) or file in {".gitlab-ci.yml", "azure-pipelines.yml"}:
            ci.append(file)
        if (
            p.suffix == ".md"
            and name.lower() not in {"readme.md", "template.md", "_template.md", "index.md"}
            and (
                name.lower().startswith("adr-")
                or any(part.lower() in {"adr", "adrs", "decisions"} for part in p.parts[:-1])
            )
        ):
            adrs.append(file)
        if name in {"package.json", "pubspec.yaml", "pyproject.toml", "go.mod", "Cargo.toml"}:
            manifests.append(file)
        script_entry = (
            p.stem in {"index", "main", "app"}
            and p.suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".py"}
            and (p.parent.name == "src" or len(p.parts) == 1)
        )
        if (
            script_entry
            or file == "manage.py"
            or file.endswith("lib/main.dart")
            or file.endswith("src/main.rs")
            or re.search(r"(?:^|/)cmd/[^/]+/main.go$", file)
            or name == "__main__.py"
        ):
            entrypoints.append(file)
        if name in {
            "package.json",
            "pubspec.yaml",
            "pyproject.toml",
            "analysis_options.yaml",
        } or re.fullmatch(
            r"(?:tsconfig.*\.json|requirements.*\.txt|Dockerfile.*|docker-compose.*\.(?:yaml|yml)|next\.config\..*|vite\.config\..*)",
            name,
        ):
            configs.append(file)
        if re.fullmatch(r"README.*\.md", name) or (file.startswith("docs/") and p.suffix == ".md"):
            docs.append(file)
    roots = set()
    for entry in entrypoints:
        parts = entry.split("/")
        positions = [i for i, part in enumerate(parts[:-1]) if part in {"src", "lib", "app"}]
        if positions:
            roots.add("/".join(parts[: positions[-1] + 1]))
    dependencies = sorted(
        {
            key
            for section in ("dependencies", "devDependencies", "peerDependencies")
            for key in package.get(section, {})
        }
    )
    return dict(
        packageManager=package_manager,
        stacks=stacks,
        platformTargets=[
            target
            for target in ("android", "ios", "web", "windows", "macos", "linux")
            if flutter and (root / target).is_dir()
        ],
        scripts=dict(sorted(package.get("scripts", {}).items())),
        dependencies=dependencies,
        contracts=contracts,
        ciFiles=ci,
        adrFiles=adrs,
        moduleManifests=manifests,
        entrypoints=entrypoints,
        configurationFiles=configs,
        documentationFiles=docs,
        sourceRoots=sorted(roots),
    )
