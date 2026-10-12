"""Human product intent and agent-owned readiness assessments."""

from copy import deepcopy
from pathlib import Path

from . import signing
from .brownfield import assess_adoption
from .common import digest, human, read_yaml, require, timestamp, validate, write_yaml
from .workspace import build_workspace_map, load_catalog, write_catalog

PROMPTS = {
    "problem": "Qual problema este projeto precisa resolver?",
    "audiences": "Quem usará ou será afetado pelo resultado?",
    "outcomes": "Como reconheceremos que o projeto teve sucesso?",
    "scope.in": "O que precisa fazer parte da primeira entrega?",
    "scope.out": "O que explicitamente não faz parte desta entrega?",
    "dataClassification": "Que classificação possuem os dados envolvidos?",
    "autonomy": "Quais ações o agente pode executar sem nova aprovação?",
}


def assess_charter(charter):
    missing = []
    if not charter["problem"].strip():
        missing.append("problem")
    for key in ("audiences", "outcomes"):
        if not charter[key]:
            missing.append(key)
    for key in ("in", "out"):
        if not charter["scope"][key]:
            missing.append("scope." + key)
    for key in ("dataClassification", "autonomy"):
        if key not in charter:
            missing.append(key)
    unknowns = sorted(u["id"] for u in charter["unknowns"] if u["blocking"])
    return dict(
        ready=not missing and not unknowns,
        questions=[dict(field=key, prompt=PROMPTS[key]) for key in missing],
        blockingUnknownIds=unknowns,
    )


def load_charter(root):
    return validate(read_yaml(Path(root) / ".aifw/charter.yaml"), "charter.schema.json")


def assess_intake(root):
    charter = load_charter(root)
    assessment = assess_charter(charter)
    agents = []
    if charter["projectType"] == "existing":
        agents.append(assess_adoption(root))
    approved = charter_approved(charter) and signing.approved(root, Path(root) / ".aifw/charter.yaml")
    result = dict(
        assessment,
        charterApproved=approved,
        complete=assessment["ready"] and approved and all(a["status"] == "current" for a in agents),
        agentAssessments=agents,
    )
    if assessment["ready"] and not approved:
        result["nextAction"] = "aifw intake approve --by human:<identity>"
    return result


def charter_approved(charter):
    """Approved and unchanged since: editing an approved Charter requires approving it again."""
    approval = charter.get("approval") or {}
    content = {k: v for k, v in charter.items() if k != "approval"}
    return charter.get("state") == "approved" and approval.get("contentDigest") == digest(content)


def approve_charter(charter, by, at):
    human(by)
    timestamp(at)
    assessment = assess_charter(charter)
    require(
        assessment["ready"],
        "Project Charter is not ready.",
        "NOT_READY",
        [q["field"] for q in assessment["questions"]] + assessment["blockingUnknownIds"],
    )
    approved = dict(deepcopy(charter), state="approved")
    approved.pop("approval", None)
    approved["approval"] = dict(approvedBy=by, approvedAt=at, contentDigest=digest(approved))
    return approved


def approve_workspace(root, by, at):
    charter = approve_charter(load_charter(root), by, at)
    write_yaml(Path(root) / ".aifw/charter.yaml", charter)
    catalog = load_catalog(root)
    catalog["project"]["purpose"] = charter["problem"]
    write_catalog(root, catalog)
    return dict(charter=charter, projectMapDigest=build_workspace_map(root, write=True)["digest"])


EDITABLE_FIELDS = {
    "problem",
    "audiences",
    "outcomes",
    "scope.in",
    "scope.out",
    "constraints",
    "dataClassification",
    "autonomy",
    "technicalPreference",
    "unknowns",
}


def set_charter_field(root, field, value):
    """Record one human decision in the Charter; editing an approved Charter reopens it."""
    require(field in EDITABLE_FIELDS, f"Editable fields: {', '.join(sorted(EDITABLE_FIELDS))}.")
    charter = load_charter(root)
    target, *parents = charter, *field.split(".")[:-1]
    for key in parents:
        target = target.setdefault(key, {})
    target[field.split(".")[-1]] = value
    reopened = charter.get("state") == "approved"
    if reopened:
        charter["state"] = "draft"
        charter.pop("approval", None)
    validate(charter, "charter.schema.json")
    write_yaml(Path(root) / ".aifw/charter.yaml", charter)
    return dict(field=field, reopened=reopened, **assess_charter(charter))
