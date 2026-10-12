"""Two-phase factual discovery and human-reviewed catalog baselines."""

from copy import deepcopy
from pathlib import Path, PurePosixPath
import re

from .common import (
    API,
    AifwError,
    digest,
    human,
    read_json,
    read_yaml,
    require,
    sort_key,
    timestamp,
    validate,
    write_json,
    write_yaml,
)
from .discovery import discover_project
from .workspace import build_workspace_map, load_catalog, load_manifest, write_catalog


def reference_slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def analyze_brownfield(root, generated_at):
    timestamp(generated_at)
    manifest, discovery = load_manifest(root), discover_project(root)
    require(
        manifest["spec"]["projectType"] == "existing",
        "Brownfield adoption requires --existing.",
        "POLICY_CONFLICT",
    )
    project_id = manifest["metadata"]["id"]

    def entity(entity_id, kind, name, source, description):
        return dict(
            id=entity_id,
            kind=kind,
            name=name,
            description=description,
            owner="human:unassigned",
            source=source,
            visibility="internal",
            origin="discovered",
            confidence="candidate",
            lastVerifiedAt=generated_at,
            relations=[dict(type="partOf", target=f"system:{project_id}")],
        )

    entities = []
    for file in discovery["moduleManifests"]:
        directory = str(PurePosixPath(file).parent)
        module_id = f"{project_id}-root" if directory == "." else reference_slug(directory)
        entities.append(
            entity(
                f"component:{module_id}",
                "Component",
                f"{project_id} root module" if directory == "." else directory,
                file,
                f"Discovered module manifest at {file}; responsibility requires review.",
            )
        )
    for key, prefix, kind, description in [
        ("contracts", "contract", "Contract", "machine-readable contract"),
        ("adrFiles", "decision", "Decision", "architecture decision reference"),
        ("ciFiles", "resource", "Resource", "continuous-integration configuration"),
    ]:
        entities.extend(
            entity(
                f"{prefix}:{reference_slug(file)}", kind, file, file, f"Discovered {description} at {file}."
            )
            for file in discovery[key]
        )
    sources = [dict(topic="Brownfield discovery", source=".aifw/adoption/discovery.json")]
    sources += [dict(topic=f"Contract {file}", source=file) for file in discovery["contracts"]]
    sources += [dict(topic=f"Decision {file}", source=file) for file in discovery["adrFiles"]]
    payload = dict(
        apiVersion=API,
        kind="BrownfieldDiscovery",
        projectId=project_id,
        discovery=discovery,
        candidates=dict(
            sourcesOfTruth=sorted(sources, key=lambda s: (sort_key(s["topic"]), sort_key(s["source"]))),
            entities=sorted(entities, key=lambda e: sort_key(e["id"])),
        ),
        unknowns=[
            "Confirm module responsibilities and boundaries from code evidence.",
            "Confirm owners, runtime relationships, data flows and deployment topology.",
            "Resolve conflicting or stale documentation before marking the mapping current.",
        ],
    )
    return dict(payload, generatedAt=generated_at, digest=digest(payload))


def write_analysis(root, generated_at):
    report = analyze_brownfield(root, generated_at)
    state = dict(
        apiVersion=API,
        kind="BrownfieldAdoption",
        projectId=report["projectId"],
        status="analyzed",
        reportDigest=report["digest"],
        analyzedAt=report["generatedAt"],
    )
    write_json(Path(root) / ".aifw/adoption/discovery.json", report)
    write_yaml(Path(root) / ".aifw/adoption/status.yaml", state)
    return dict(
        reportPath=".aifw/adoption/discovery.json",
        statePath=".aifw/adoption/status.yaml",
        report=report,
        state=state,
    )


def load_files(root):
    root = Path(root)
    try:
        report, state = (
            read_json(root / ".aifw/adoption/discovery.json"),
            read_yaml(root / ".aifw/adoption/status.yaml"),
        )
    except FileNotFoundError as error:
        raise AifwError(
            "NOT_READY", "Run brownfield analysis with persistence before applying the map."
        ) from error
    validate(report, "brownfield-discovery.schema.json")
    validate(state, "brownfield-adoption.schema.json")
    payload = {k: v for k, v in report.items() if k not in {"digest", "generatedAt"}}
    require(report["digest"] == digest(payload), "Brownfield discovery digest does not match its content.")
    require(
        state["projectId"] == report["projectId"] and state["reportDigest"] == report["digest"],
        "Brownfield state does not match discovery report.",
    )
    return report, state


def render_architecture(report):
    lines = [
        "# Discovered architecture inventory",
        "",
        f"> Generated from factual repository discovery ({report['digest']}). This is not an approved semantic architecture. This mapping requires human review of candidate responsibilities, owners and relations.",
        "",
    ]
    for title, key in [
        ("Module manifests", "moduleManifests"),
        ("Entrypoints", "entrypoints"),
        ("Source roots", "sourceRoots"),
        ("Contracts", "contracts"),
        ("CI", "ciFiles"),
        ("ADRs", "adrFiles"),
        ("Configuration", "configurationFiles"),
        ("Documentation", "documentationFiles"),
    ]:
        lines += [
            f"## {title}",
            "",
            *([f"- `{v}`" for v in report["discovery"][key]] or ["_None discovered._"]),
            "",
        ]
    return "\n".join(lines + ["## Review questions", "", *[f"- {v}" for v in report["unknowns"]], ""])


def apply_mapping(root, applied_at):
    timestamp(applied_at)
    report, state = load_files(root)
    catalog = load_catalog(root)
    entities = {e["id"]: e for e in catalog["entities"]}
    for candidate in report["candidates"]["entities"]:
        existing = entities.get(candidate["id"])
        require(
            existing is None or existing.get("origin") == "discovered",
            f"Brownfield candidate {candidate['id']} conflicts with a manually governed entity.",
            "POLICY_CONFLICT",
        )
        entities[candidate["id"]] = deepcopy(candidate)
    sources = {
        (s["topic"], s["source"]): s
        for s in catalog["sourcesOfTruth"] + report["candidates"]["sourcesOfTruth"]
    }
    catalog["entities"] = sorted(entities.values(), key=lambda e: sort_key(e["id"]))
    catalog["sourcesOfTruth"] = sorted(
        sources.values(), key=lambda s: (sort_key(s["topic"]), sort_key(s["source"]))
    )
    catalog["project"]["verifiedRevision"] = "discovery:" + report["digest"][:12]
    write_catalog(root, catalog)
    architecture = Path(root) / "docs/architecture/discovered.md"
    architecture.parent.mkdir(parents=True, exist_ok=True)
    architecture.write_text(render_architecture(report), encoding="utf-8", newline="\n")
    next_state = {k: v for k, v in state.items() if k != "approval"}
    next_state.update(status="review-required", appliedAt=applied_at)
    write_yaml(Path(root) / ".aifw/adoption/status.yaml", next_state)
    return dict(
        state=next_state,
        appliedEntityIds=sorted(e["id"] for e in report["candidates"]["entities"]),
        architecturePath="docs/architecture/discovered.md",
        projectMap=build_workspace_map(root, write=True),
    )


def approve_mapping(root, by, at):
    human(by)
    timestamp(at)
    report, state = load_files(root)
    require(
        state["status"] == "review-required",
        "Apply and review brownfield candidates before approval.",
        "NOT_READY",
    )
    catalog = load_catalog(root)
    ids = {e["id"] for e in report["candidates"]["entities"]}
    for entity in catalog["entities"]:
        if entity["id"] in ids and entity.get("origin") == "discovered":
            entity.update(owner=by, confidence="confirmed")
    approved = sorted([e for e in catalog["entities"] if e["id"] in ids], key=lambda e: sort_key(e["id"]))
    require(len(approved) == len(ids), "Catalog no longer contains every discovery candidate.", "NOT_READY")
    state.update(
        status="approved",
        approval=dict(
            approvedBy=by,
            approvedAt=at,
            contentDigest=digest(dict(reportDigest=report["digest"], entities=approved)),
        ),
    )
    write_catalog(root, catalog)
    write_yaml(Path(root) / ".aifw/adoption/status.yaml", state)
    return dict(state=state, projectMap=build_workspace_map(root, write=True))


def assess_adoption(root):
    result = dict(
        id="brownfield-mapping",
        owner="agent",
        blockingHumanApproval=False,
        status="current",
        artifact=".aifw/adoption/status.yaml",
    )
    if load_manifest(root)["spec"]["projectType"] != "existing":
        return dict(result, reason="Not applicable to a new project.")
    try:
        report, state = load_files(root)
        if state["status"] == "approved":
            ids = {e["id"] for e in report["candidates"]["entities"]}
            entities = sorted(
                [e for e in load_catalog(root)["entities"] if e["id"] in ids], key=lambda e: sort_key(e["id"])
            )
            current_digest = digest(dict(reportDigest=report["digest"], entities=entities))
            if len(entities) != len(ids) or current_digest != state.get("approval", {}).get("contentDigest"):
                return dict(
                    result,
                    status="invalid",
                    blockingHumanApproval=True,
                    reason="The approved brownfield catalog changed after its recorded content digest.",
                    nextAction="aifw adopt apply",
                )
            return dict(result, reason="The discovered mapping is applied and approved by a human.")
        if state["status"] == "review-required":
            return dict(
                result,
                status="review-required",
                blockingHumanApproval=True,
                reason="Factual candidates were written and require human review.",
                nextAction="aifw adopt approve --by human:<identity>",
            )
        return dict(
            result,
            status="pending",
            reason="Discovery is persisted but has not been applied to the catalog.",
            nextAction="aifw adopt apply",
        )
    except AifwError as error:
        if error.code == "NOT_READY":
            return dict(
                result,
                status="pending",
                reason="No persisted brownfield discovery report exists.",
                nextAction="aifw adopt analyze --write",
            )
        return dict(result, status="invalid", reason=str(error), nextAction="aifw adopt analyze --write")
