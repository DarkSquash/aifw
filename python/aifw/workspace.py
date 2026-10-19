"""Project scaffolding and deterministic architecture map generation."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

from . import __version__
from .common import (
    assets,
    ignore_local_logs,
    normalize,
    read_json,
    read_yaml,
    require,
    sort_key,
    validate,
    write_yaml,
)


def load_manifest(root):
    return validate(read_yaml(Path(root) / "aifw.yaml"), "project-manifest.schema.json")


def load_catalog(root):
    return validate(read_yaml(Path(root) / ".aifw/catalog.yaml"), "catalog.schema.json")


def write_catalog(root, catalog):
    validate(catalog, "catalog.schema.json")
    write_yaml(Path(root) / ".aifw/catalog.yaml", catalog)


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def build_project_map(data):
    entities = sorted(deepcopy(data["entities"]), key=lambda e: (sort_key(e["kind"]), sort_key(e["id"])))
    ids = [e["id"] for e in entities]
    require(len(ids) == len(set(ids)), "Duplicate catalog entity id.")
    lines = [
        f"# PROJECT_MAP — {data['project']['name']}",
        "",
        "> Compiled entrypoint. Edit authoritative sources, then regenerate this file.",
        "",
        "## Project",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Project ID | {cell(data['project']['id'])} |",
        f"| Framework | {cell(data['frameworkVersion'])} |",
        f"| Verified revision | {cell(data['verifiedRevision'])} |",
        "",
        "## Purpose",
        "",
        data["purpose"].strip(),
        "",
        "## Sources of truth",
        "",
        "| Topic | Source |",
        "| --- | --- |",
    ]
    lines.extend(
        f"| {cell(s['topic'])} | {cell(s['source'])} |"
        for s in sorted(data["sourcesOfTruth"], key=lambda s: sort_key(s["topic"]))
    )
    lines.extend(
        [
            "",
            "## Catalog",
            "",
            "| ID | Kind | Name | Owner | Visibility | Origin | Confidence | Verified | Source | Description |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for entity in entities:
        values = [
            entity["id"],
            entity["kind"],
            entity["name"],
            entity["owner"],
            entity["visibility"],
            entity.get("origin", "manual"),
            entity.get("confidence", "confirmed"),
            entity.get("lastVerifiedAt", "not-recorded"),
            entity["source"],
            entity["description"],
        ]
        lines.append("| " + " | ".join(map(cell, values)) + " |")
    lines.extend(["", "## Relationships", "", "| Source | Relation | Target |", "| --- | --- | --- |"])
    for entity in entities:
        for relation in sorted(
            entity["relations"], key=lambda r: (sort_key(r["type"]), sort_key(r["target"]))
        ):
            lines.append(f"| {cell(entity['id'])} | {relation['type']} | {cell(relation['target'])} |")
    body = "\n".join(lines + [""])
    checksum = sha256(body.encode()).hexdigest()
    return {
        "markdown": f"<!-- aifw:project-map digest={checksum} -->\n{body}",
        "digest": checksum,
        "entities": entities,
    }


def build_workspace_map(root, write=False):
    root = Path(root)
    manifest, catalog = load_manifest(root), load_catalog(root)
    generated = build_project_map(
        dict(
            project=manifest["metadata"],
            frameworkVersion=manifest["spec"]["frameworkVersion"],
            entities=catalog["entities"],
            sourcesOfTruth=catalog["sourcesOfTruth"],
            **catalog["project"],
        )
    )
    file = root / "PROJECT_MAP.md"
    current = file.is_file() and normalize(file.read_text(encoding="utf-8")) == normalize(
        generated["markdown"]
    )
    if write and not current:
        file.write_text(generated["markdown"], encoding="utf-8", newline="\n")
        current = True
    return dict(
        current=current, digest=generated["digest"], markdown=generated["markdown"], outputPath=str(file)
    )


def gate_recipe(root, profiles):
    """The gate set shipped by the first selected profile that has one, adapted to the project."""
    for profile in profiles:
        folder = assets() / "profiles" / profile
        if profile == "flutter-mobile":
            fvm = (Path(root) / ".fvmrc").exists() or (Path(root) / ".fvm").exists()
            return folder / ("gates.windows-fvm.yaml" if fvm else "gates.windows.yaml")
        if (folder / "gates.yaml").is_file():
            return folder / "gates.yaml"
    return None


LOCKFILES = (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"), ("bun.lockb", "bun"))


def adapt_gates(root, gates):
    """Fit a profile recipe to the project: its package manager, `uv run` and the tools it declares.

    A gate whose script or tool the project does not declare loses its command, so validation says
    "set one" instead of failing on a missing program. Without package.json or pyproject.toml yet
    (a new project), the recipe stays as shipped.
    """
    root = Path(root)
    package = read_json(root / "package.json") if (root / "package.json").is_file() else None
    manager = next((m for lock, m in LOCKFILES if (root / lock).is_file()), "npm")
    manifests = [root / "pyproject.toml", *sorted(root.glob("requirements*.txt"))]
    declared = " ".join(f.read_text(encoding="utf-8", errors="replace") for f in manifests if f.is_file())
    for gate in gates["gates"]:
        command = gate.get("command", [])
        if command[:1] == ["npm"]:
            script = command[2] if command[1:2] == ["run"] else command[1]
            if package is not None and script not in package.get("scripts", {}):
                del gate["command"]
            else:
                gate["command"] = [manager, "run", script]
        elif command[:2] == ["python", "-m"] and command[2] != "aifw":
            if declared and not re.search(rf"\b{command[2]}\b", declared):
                del gate["command"]
            elif (root / "uv.lock").is_file():
                gate["command"] = ["uv", "run", *command]
    return gates


def initialize_project(root, options):
    root = Path(root)
    template = json.dumps(read_json(assets() / "templates/project-scaffold.json"), ensure_ascii=False)

    # Replace values recursively, never interpolate user text into serialized JSON.
    def substitute(value):
        if isinstance(value, str):
            return value.replace("aifw-template", options["id"]).replace("AIFW Template", options["name"])
        if isinstance(value, dict):
            return {k: substitute(v) for k, v in value.items()}
        if isinstance(value, list):
            return [substitute(v) for v in value]
        return value

    files = substitute(json.loads(template))
    manifest = files["aifw.yaml"]
    manifest["spec"].update(
        frameworkVersion=__version__,
        projectType=options.get("projectType", "new"),
        locale=options.get("locale", "pt-BR"),
        primaryEnvironment=options.get("primaryEnvironment", "windows"),
        validationTargets=list(
            dict.fromkeys(options.get("validationTargets", ["windows", "wsl", "linux-ci"]))
        ),
        profiles=list(dict.fromkeys(options.get("profiles", []))),
    )
    files[".aifw/charter.yaml"]["projectType"] = manifest["spec"]["projectType"]
    recipe = gate_recipe(root, manifest["spec"]["profiles"])
    if recipe:
        files[".aifw/gates.yaml"] = adapt_gates(
            root, validate(read_yaml(recipe), "quality-gates.schema.json")
        )
    files[".aifw/framework.lock.yaml"].update(frameworkVersion=__version__, generatedBy=f"aifw/{__version__}")
    validate(manifest, "project-manifest.schema.json")
    conflicts = [name for name in [*files, "PROJECT_MAP.md"] if (root / name).exists()]
    require(
        not conflicts,
        "Initialization would overwrite existing framework files.",
        "POLICY_CONFLICT",
        sorted(conflicts),
    )
    for name, value in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(value)
        else:
            write_yaml(target, value, exclusive=True)
    build_workspace_map(root, write=True)
    ignored = ignore_local_logs(root)
    return {"createdFiles": sorted([*files, "PROJECT_MAP.md"]), "gitignored": ignored, "manifest": manifest}
