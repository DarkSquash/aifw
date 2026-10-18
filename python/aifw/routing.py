"""Impact classification and deterministic cognitive routing."""

from pathlib import Path
import math
import re
import subprocess

from .common import AifwError, human, now, read_yaml, require, write_yaml

ALIASES = {"FAST": "haiku", "WORK": "sonnet", "BRAIN": "opus"}


def classify_change(signals):
    l3 = [
        ("frameworkCore", "framework-core"),
        ("constitution", "constitution"),
        ("securityBoundary", "security-boundary"),
        ("destructiveMigration", "destructive-migration"),
        ("breakingContract", "breaking-contract"),
        ("irreversibleProduction", "irreversible-production"),
    ]
    l2 = [
        ("crossModule", "cross-module"),
        ("sharedContract", "shared-contract"),
        ("sensitiveData", "sensitive-data"),
        ("globalDesignSystem", "global-design-system"),
        ("externalCost", "external-cost"),
        ("production", "production"),
        ("touchesAuth", "authorization"),
    ]
    reasons3 = [reason for key, reason in l3 if signals.get(key) is True]
    reasons2 = [reason for key, reason in l2 if signals.get(key) is True]
    if reasons3:
        level, reasons, approval = "L3", reasons3, "required"
        artifacts = [
            "change-case",
            "rfc",
            "spec",
            "technical-plan",
            "adr",
            "threat-model",
            "migration",
            "rollback",
            "independent-review",
            "human-approval",
        ]
    elif reasons2:
        level, reasons = "L2", reasons2
        approval = "required" if any(r != "cross-module" for r in reasons) else "conditional"
        artifacts = ["change-case", "spec", "technical-plan", "tests", "rollback", "independent-review"]
    elif signals.get("behaviorChange"):
        level, reasons, approval = (
            "L1",
            ["local-behavior" if signals.get("localOnly") else "behavior"],
            "none",
        )
        artifacts = ["change-case", "tests", "rollback"]
    else:
        level, reasons, approval = "L0", ["documentation" if signals.get("docsOnly") else "read-only"], "none"
        artifacts = ["change-record", "evidence"]
    route = signals.get(
        "semanticComplexity", "brain" if level == "L3" else "fast" if level == "L0" else "work"
    ).upper()
    return dict(
        level=level,
        humanApproval=approval,
        reasons=reasons,
        requiredArtifacts=artifacts,
        suggestedRoute=route,
    )


def route_task(task, aliases=None, enabled=False):
    if task["impact"] == "L3":
        route, reasons = "BRAIN", ["impact:L3"]
    elif task["operation"] == "architecture-decision":
        route, reasons = "BRAIN", ["operation:architecture-decision"]
    elif task["uncertainty"] == "high" or task.get("failedAttempts", 0) >= 2:
        route, reasons = "BRAIN", ["uncertainty:high" if task["uncertainty"] == "high" else "failed-attempts"]
    elif task.get("requestedRoute") == "BRAIN":
        route, reasons = "BRAIN", ["requested:BRAIN"]
    elif (
        task["impact"] in {"L0", "L1"}
        and task["uncertainty"] == "low"
        and not task.get("crossDomain")
        and task["operation"] in {"single-read", "discovery", "documentation"}
        and task.get("requestedRoute") != "WORK"
    ):
        route, reasons = "FAST", ["bounded-low-risk"]
    else:
        route, reasons = "WORK", [f"impact:{task['impact']}", f"operation:{task['operation']}"]
    return dict(
        route=route,
        suggestedModel=(aliases or ALIASES)[route],
        executionMode="automatic" if enabled else "recommendation-only",
        reasons=reasons,
    )


def evaluate_routing_activation(data):
    blockers, report = [], data["report"]
    if not data.get("humanApproved"):
        blockers.append("human-approval")
    minimum_cases, minimum_rate = data.get("minimumCases", 30), data.get("minimumPassRate", 0.95)
    if report["cases"] < minimum_cases:
        blockers.append(f"minimum-cases:{minimum_cases}")
    if report["passRate"] < minimum_rate:
        blockers.append(f"minimum-pass-rate:{minimum_rate}")
    if report["criticalFailures"] > 0:
        blockers.append("critical-failures:0")
    return {"enabled": not blockers, "blockers": blockers}


def load_routing(root):
    from .common import validate

    return validate(read_yaml(Path(root) / ".aifw/routing.yaml"), "routing.schema.json")


def routing_state(root):
    """Persisted aliases and whether automatic routing is on; with signing required, only a signed activation counts."""
    from . import signing

    file = Path(root) / ".aifw/routing.yaml"
    if not file.is_file():
        return ALIASES, False
    policy = load_routing(root)
    return policy["aliases"], bool(policy["enabled"]) and signing.approved(root, file)


def activate_routing(root, report, by, record):
    human(by)
    require(
        isinstance(record, str) and record.strip(),
        "Routing requires an approval record.",
        "APPROVAL_REQUIRED",
    )
    require(
        all(
            isinstance(report.get(k), (int, float))
            and not isinstance(report.get(k), bool)
            and math.isfinite(report[k])
            for k in ("cases", "passRate", "criticalFailures")
        ),
        "Invalid routing metrics.",
    )
    require(
        report["cases"] >= 0
        and report["cases"] % 1 == 0
        and 0 <= report["passRate"] <= 1
        and report["criticalFailures"] >= 0
        and report["criticalFailures"] % 1 == 0,
        "Invalid routing metrics.",
    )
    policy = load_routing(root)
    activation = evaluate_routing_activation(
        dict(
            humanApproved=True,
            report=report,
            minimumCases=policy["activation"]["minimumCases"],
            minimumPassRate=policy["activation"]["minimumPassRate"],
        )
    )
    require(
        activation["enabled"], "Routing activation is blocked.", "APPROVAL_REQUIRED", activation["blockers"]
    )
    policy.update(
        enabled=True,
        mode="automatic",
        approval=dict(approvedBy=by, record=record, activatedAt=now(), report=dict(report)),
    )
    write_yaml(Path(root) / ".aifw/routing.yaml", policy)
    return policy


AUTH_PATH = re.compile(
    r"(^|/)(auth|security|permissions?|crypto|secrets?|oauth|login|sessions?)(/|\.|_|-|$)", re.I
)
DEPLOY_PATH = re.compile(
    r"(^|/)(\.github/workflows/|Dockerfile|docker-compose|vercel\.json|netlify\.toml|firebase\.json|fly\.toml"
    r"|k8s/|helm/)|\.tf$",
    re.I,
)
CONTROL_PATH = re.compile(r"^(aifw\.yaml|\.aifw/(permissions|routing|gates|project-rules)\.yaml)$")


def changed_files(root, base=None):
    """Files changed against base (default HEAD), plus untracked ones; all files before the first commit."""

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True
        ).stdout

    try:
        untracked = git("ls-files", "--others", "--exclude-standard").splitlines()
        try:
            tracked = git("diff", "--name-only", base or "HEAD").splitlines()
        except subprocess.CalledProcessError:
            tracked = git("ls-files").splitlines()
    except (OSError, subprocess.CalledProcessError) as error:
        raise AifwError("NOT_READY", "Deriving signals from the diff requires a git repository.") from error
    return sorted(set(tracked + untracked))


def derive_signals(root, base=None):
    """Risk signals implied by the changed paths; they can only raise the classification."""
    from .workspace import load_catalog

    files = changed_files(root, base)
    entities = load_catalog(root)["entities"]

    def under(source):
        return [f for f in files if f == source or f.startswith(source.rstrip("/") + "/")]

    signals, reasons = {}, []

    def mark(signal, reason):
        signals[signal] = True
        reasons.append(f"{signal}: {reason}")

    for entity in entities:
        if entity["kind"] == "Contract" and under(entity["source"]):
            mark("sharedContract", entity["source"])
    components = {
        e["id"] for e in entities if e["kind"] == "Component" and e["source"] != "." and under(e["source"])
    }
    if len(components) > 1:
        mark("crossModule", ", ".join(sorted(components)))
    for file in files:
        if AUTH_PATH.search(file):
            mark("touchesAuth", file)
        if DEPLOY_PATH.search(file):
            mark("production", file)
        if file == "CONSTITUTION.md" or file.startswith("policies/"):
            mark("constitution", file)
        if CONTROL_PATH.match(file):
            mark("frameworkCore", file)
    docs = [f for f in files if f.endswith((".md", ".txt", ".rst")) or f.startswith("docs/")]
    if files and len(docs) == len(files):
        mark("docsOnly", "only documentation changed")
    elif files:
        mark("behaviorChange", f"{len(files) - len(docs)} non-documentation files changed")
    return dict(files=files, signals=signals, reasons=sorted(set(reasons)))
