"""AIFW command line. Exit 0 succeeds, 1 rejects input, 2 reports blockers."""

import argparse
from datetime import timedelta
import os
from pathlib import Path
import sys

from . import __version__

from .common import (
    AifwError,
    assets,
    json_text,
    now,
    parse_yaml,
    project_path,
    read_json,
    require,
    timestamp,
    write_json,
)

LEVELS = ["L0", "L1", "L2", "L3"]
OPERATIONS = [
    "single-read",
    "discovery",
    "documentation",
    "implementation",
    "review",
    "research",
    "architecture-decision",
    "incident-response",
]
SIGNALS = [
    "read-only",
    "docs-only",
    "behavior-change",
    "local-only",
    "reversible",
    "cross-module",
    "shared-contract",
    "sensitive-data",
    "global-design-system",
    "external-cost",
    "production",
    "touches-auth",
    "framework-core",
    "constitution",
    "security-boundary",
    "destructive-migration",
    "breaking-contract",
    "irreversible-production",
]


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise AifwError("MANIFEST_INVALID", message)


def create_parser():
    parser = Parser(prog="aifw", description="AI Software Engineering Framework control plane (Python)")
    parser.add_argument("--version", "-V", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    leaves = {}
    groups = {}

    def command(name, description):
        parts = name.split()
        parent = sub
        if len(parts) == 2:
            if parts[0] not in groups:
                group = sub.add_parser(parts[0], help=f"Manage {parts[0]}")
                groups[parts[0]] = group.add_subparsers(dest="subcommand", required=True)
            parent = groups[parts[0]]
        leaf = parent.add_parser(parts[-1], help=description, description=description)
        leaf.add_argument("--json", action="store_true", help="emit stable machine-readable JSON")
        leaf.set_defaults(action=name)
        leaves[tuple(parts)] = leaf
        return leaf

    def option(leaf, flag, *, required=False, default=None, choices=None, action=None):
        kwargs = {"help": flag.removeprefix("--").replace("-", " ")}
        if action:
            kwargs["action"] = action
        else:
            kwargs["required"] = required
            if default is not None:
                kwargs["default"] = default
            if choices is not None:
                kwargs["choices"] = choices
        leaf.add_argument(flag, **kwargs)

    def dated(leaf):
        option(leaf, "--at")

    def approval(leaf):
        option(leaf, "--by", required=True)
        dated(leaf)

    init = command("init", "initialize a project control plane")
    for flag in ("--id", "--name"):
        option(init, flag, required=True)
    for flag in ("--existing", "--flutter", "--web", "--python"):
        option(init, flag, action="store_true")
    option(init, "--locale", default="pt-BR")
    option(init, "--primary", default="windows", choices=["windows", "wsl", "linux"])
    option(init, "--targets", default="windows,wsl,linux-ci")
    command("audit", "inspect a project without changing it")
    command("intake status", "show missing human decisions and technical assessments")
    approval(command("intake approve", "persist human approval of a ready charter"))
    leaf = command("intake set", "record one Charter decision; editing an approved Charter reopens it")
    option(leaf, "--field", required=True)
    option(leaf, "--value", required=True)
    command("map build", "regenerate PROJECT_MAP.md")
    command("map check", "verify PROJECT_MAP.md freshness")
    leaf = command("adopt analyze", "discover factual brownfield references")
    option(leaf, "--write", action="store_true")
    dated(leaf)
    dated(command("adopt apply", "write factual discovery candidates for review"))
    command("adopt status", "show brownfield mapping review state")
    approval(command("adopt approve", "confirm mapping after human review"))
    leaf = command("spec new", "create a self-contained active spec change")
    leaf.add_argument("id")
    for flag in ("--title", "--summary"):
        option(leaf, flag, required=True)
    option(leaf, "--level", required=True, choices=LEVELS)
    dated(leaf)
    command("spec list", "list active and archived changes")
    for name, description in [
        ("show", "show a change summary"),
        ("status", "show or advance a change status"),
        ("validate", "validate delta preconditions"),
        ("analyze", "analyze requirement-to-evidence traceability"),
        ("sync", "preview the capability merge without writing"),
        ("approve", "persist human approval for a change"),
        ("archive", "commit validated specs and archive context"),
    ]:
        leaf = command("spec " + name, description)
        leaf.add_argument("id")
        if name == "status":
            option(leaf, "--set", choices=["active", "ready"])
        if name == "sync":
            option(leaf, "--dry-run", action="store_true")
        if name == "approve":
            approval(leaf)
            option(leaf, "--record", required=True)
        if name == "archive":
            dated(leaf)
    leaf = command("decision list", "list decision categories and alternatives")
    option(leaf, "--category")
    leaf = command("decision recommend", "rank alternatives from explicit signals")
    option(leaf, "--category", required=True)
    option(leaf, "--signals", required=True)
    option(leaf, "--selected", default="")
    option(leaf, "--write", action="store_true")
    leaf = command("decision approve", "approve an eligible decision with an ADR")
    approval(leaf)
    for flag in ("--category", "--option", "--adr"):
        option(leaf, flag, required=True)
    leaf = command("principle list", "list engineering principles")
    option(leaf, "--family", choices=["clean-code", "solid", "foundational"])
    for name in ("build", "check"):
        option(
            command("resolve " + name, "resolve authority layers and verify the pinned policy"), "--personal"
        )
    leaf = command("change classify", "classify change impact")
    for flag in SIGNALS:
        option(leaf, "--" + flag, action="store_true")
    option(leaf, "--complexity", choices=["fast", "work", "brain"])
    option(leaf, "--diff", action="store_true")
    option(leaf, "--base")
    leaf = command("route explain", "explain deterministic cognitive routing")
    option(leaf, "--impact", required=True, choices=LEVELS)
    option(leaf, "--operation", required=True, choices=OPERATIONS)
    option(leaf, "--uncertainty", required=True, choices=["low", "medium", "high"])
    option(leaf, "--failed-attempts", default="0")
    option(leaf, "--cross-domain", action="store_true")
    command("route status", "show persisted routing state")
    leaf = command("route eval", "evaluate routing against reviewable cases")
    option(leaf, "--cases")
    option(leaf, "--output")
    leaf = command("route activate", "activate routing after evals and human approval")
    for flag in ("--report", "--by", "--record"):
        option(leaf, flag, required=True)
    leaf = command("waiver add", "record a time-bounded human exception for a gate or overridable rule")
    for flag in ("--rule", "--scope", "--reason", "--expires"):
        option(leaf, flag, required=True)
    option(leaf, "--requested-by", default="agent:claude")
    approval(leaf)
    command("waiver list", "list waivers and whether they are active")
    leaf = command("break-glass grant", "grant temporary incident permissions honored by the Claude hook")
    for flag in ("--incident", "--scope", "--reason"):
        option(leaf, flag, required=True)
    option(leaf, "--hours", default="4")
    approval(leaf)
    command("break-glass list", "list incident grants and whether they are active")
    command("template list", "list document templates")
    leaf = command("template copy", "copy a template into a spec change or a project path")
    option(leaf, "--name", required=True)
    option(leaf, "--change")
    option(leaf, "--output")
    option(command("runs show", "summarize recorded Claude sessions against the workflow rules"), "--session")
    command("claude install", "install the /aifw command in ~/.claude (it activates nothing by itself)")
    command("claude enable", "add the AIFW hooks and workflow skill to this project's .claude folder")
    command("claude check", "report what Claude Code still needs to run AIFW in this project")
    leaf = command("impasse open", "start tracking correction attempts for a problem")
    option(leaf, "--id", required=True)
    option(leaf, "--impact", required=True, choices=LEVELS)
    leaf = command("impasse attempt", "record a distinct correction attempt")
    for flag in ("--id", "--hypothesis", "--intervention", "--evidence"):
        option(leaf, flag, required=True)
    option(leaf, "--outcome", required=True, choices=["success", "failure", "inconclusive"])
    dated(leaf)
    option(command("impasse status", "show impasse cases and whether mutations are frozen"), "--id")
    leaf = command("impasse review", "submit an open impasse with a framework proposal for human review")
    for flag in ("--id", "--rule", "--explanation", "--proposal"):
        option(leaf, flag, required=True)
    leaf = command("impasse decide", "persist the human decision approving the proposed change")
    option(leaf, "--id", required=True)
    option(leaf, "--record", required=True)
    approval(leaf)
    leaf = command("impasse revalidate", "record revalidation after an approved change")
    option(leaf, "--id", required=True)
    option(leaf, "--result", required=True, choices=["passed", "failed"])
    for flag in ("--evidence", "--artifacts"):
        option(leaf, flag, required=True)
    leaf = command("context index", "inventory local documentation; optionally save a factual baseline")
    option(leaf, "--write", action="store_true")
    command("context check", "check local references and drift against the saved baseline")
    leaf = command("context select", "select task context without dropping required dependencies")
    option(leaf, "--task", required=True)
    option(leaf, "--intent", default="")
    option(leaf, "--files", default="")
    option(leaf, "--budget", default="2500")
    for name in ("build", "check"):
        leaf = command(
            "instructions " + name, "generate or check managed blocks from shared project instructions"
        )
        option(leaf, "--agent", default="all", choices=["all", "codex", "claude", "opencode"])
        option(leaf, "--source", default=".aifw/project-instructions.md")
    leaf = command(
        "gates check", "inspect gate configuration and static GitHub CI references without running them"
    )
    option(leaf, "--level", required=True, choices=LEVELS)
    command("doctor", "check Python, Git, Windows and WSL")
    leaf = command("eval", "evaluate agent behavioral conformance")
    option(leaf, "--cases")
    option(leaf, "--traces")
    leaf = command("validate", "run quality gates selected by impact, or for a spec change")
    option(leaf, "--level", choices=LEVELS)
    option(leaf, "--change")
    option(leaf, "--write", action="store_true")
    parser.command_parsers = leaves
    return parser


def comma_list(value):
    return [item.strip() for item in value.split(",") if item.strip()]


APPROVALS = {
    "intake approve",
    "adopt approve",
    "decision approve",
    "spec approve",
    "route activate",
    "impasse decide",
    "waiver add",
    "break-glass grant",
}


def confirm_human(by, project):
    """Approvals need the approving person at their own terminal; an agent shell has no console window."""
    present = os.environ.get("CLAUDECODE") != "1" and sys.stdin.isatty()
    if present and os.name == "nt":
        import ctypes

        present = bool(ctypes.windll.kernel32.GetConsoleWindow())
    elif present:
        try:
            open("/dev/tty").close()
        except OSError:
            present = False
    require(
        present,
        "Approvals must be run by the approving person in their own terminal, not by an agent.",
        "APPROVAL_REQUIRED",
    )
    sys.stderr.write(f"Approve as {by}? Type the project id ({project}) to confirm: ")
    sys.stderr.flush()
    require(
        sys.stdin.readline().strip() == project,
        "Confirmation did not match; nothing was approved.",
        "APPROVAL_REQUIRED",
    )


def execute(args, root):
    from . import brownfield, catalogs, conformance, gates, intake, policy, routing, specs, workspace

    action = args.action
    at = getattr(args, "at", None) or now()
    if action in APPROVALS:
        confirm_human(args.by, workspace.load_manifest(root)["metadata"]["id"])
    if action.startswith("context "):
        from . import context

        if action == "context index":
            value = context.build_index(root, write=args.write)
        elif action == "context check":
            value = context.check_context(root)
        else:
            try:
                budget = int(args.budget)
            except ValueError as error:
                raise AifwError("MANIFEST_INVALID", "Context budget must be a positive integer.") from error
            value = context.select_context(root, args.task, args.intent, comma_list(args.files), budget)
        return value, 0 if value["status"] == "pass" else 2
    if action.startswith("instructions "):
        from .instructions import sync_instructions

        value = sync_instructions(root, args.agent, args.source, write=action.endswith("build"))
        return value, 0 if value["status"] == "pass" else 2
    if action == "gates check":
        value = gates.inspect_gate_wiring(root, args.level)
        return value, 0 if value["status"] == "pass" else 2
    if action == "init":
        profiles = [
            profile
            for flag, profile in (("flutter", "flutter-mobile"), ("web", "web-ts"), ("python", "python"))
            if getattr(args, flag)
        ]
        require(len(profiles) <= 1, "Choose only one primary stack flag during init.", "POLICY_CONFLICT")
        value = workspace.initialize_project(
            root,
            dict(
                id=args.id,
                name=args.name,
                projectType="existing" if args.existing else "new",
                locale=args.locale,
                primaryEnvironment=args.primary,
                validationTargets=comma_list(args.targets),
                profiles=profiles,
            ),
        )
        return dict(status="initialized", **value), 0
    if action == "audit":
        from .discovery import discover_project

        mapped = workspace.build_workspace_map(root)
        return dict(
            status="pass" if mapped["current"] else "warning",
            manifest=workspace.load_manifest(root),
            discovery=discover_project(root),
            projectMap={k: mapped[k] for k in ("current", "digest")},
        ), 0
    if action == "intake status":
        value = intake.assess_intake(root)
        return value, 0 if value["complete"] else 2
    if action == "intake set":
        return intake.set_charter_field(root, args.field, parse_yaml(args.value, "--value")), 0
    if action == "intake approve":
        return dict(status="approved", **intake.approve_workspace(root, args.by, at)), 0
    if action in {"map build", "map check"}:
        value = workspace.build_workspace_map(root, write=action.endswith("build"))
        return dict(current=value["current"], digest=value["digest"], path="PROJECT_MAP.md"), 0 if value[
            "current"
        ] else 2
    if action == "adopt analyze":
        if args.write:
            value = brownfield.write_analysis(root, at)
            report = value["report"]
            return dict(
                persisted=True,
                path=value["reportPath"],
                digest=report["digest"],
                candidates=len(report["candidates"]["entities"]),
                unknowns=report["unknowns"],
            ), 0
        return dict(persisted=False, report=brownfield.analyze_brownfield(root, at)), 0
    if action == "adopt apply":
        value = brownfield.apply_mapping(root, at)
        return dict(
            status=value["state"]["status"],
            entities=value["appliedEntityIds"],
            architecture=value["architecturePath"],
            projectMap={k: value["projectMap"][k] for k in ("current", "digest")},
        ), 0
    if action == "adopt approve":
        value = brownfield.approve_mapping(root, args.by, at)
        return dict(
            status=value["state"]["status"],
            approval=value["state"]["approval"],
            projectMap={k: value["projectMap"][k] for k in ("current", "digest")},
        ), 0
    if action == "adopt status":
        value = brownfield.assess_adoption(root)
        return value, 0 if value["status"] == "current" else 2
    if action == "spec new":
        return dict(
            status="created",
            **specs.create_change(
                root, dict(id=args.id, title=args.title, summary=args.summary, level=args.level, createdAt=at)
            ),
        ), 0
    if action == "spec list":
        return specs.list_changes(root), 0
    if action in {"spec show", "spec status"}:
        if action == "spec status" and args.set:
            value = specs.update_status(root, args.id, args.set)
            return dict(status=value["status"], change=value), 0
        value = next((e for e in specs.list_changes(root) if e["id"] == args.id), None)
        require(value is not None, f"Spec change not found: {args.id}", "NOT_READY")
        return value, 0
    if action in {"spec validate", "spec analyze", "spec sync"}:
        function = {
            "spec validate": specs.validate_change,
            "spec analyze": specs.analyze_change,
            "spec sync": specs.preview_sync,
        }[action]
        value = function(root, args.id)
        if action == "spec sync":
            value["dryRun"] = True
        return value, 0 if value["pass"] else 2
    if action == "spec approve":
        return dict(
            status="approved",
            change=specs.approve_change(
                root, args.id, dict(approvedBy=args.by, approvedAt=at, record=args.record)
            ),
        ), 0
    if action == "spec archive":
        return dict(status="archived", **specs.archive_change(root, args.id, at)), 0
    if action == "decision list":
        values = []
        for catalog in catalogs.load_decision_catalogs(root):
            if args.category and catalog["metadata"]["category"] != args.category:
                continue
            values.append(
                dict(
                    **{k: catalog["metadata"][k] for k in ("id", "category", "scope", "impact")},
                    title=catalog["spec"]["title"],
                    drivers=catalog["spec"]["drivers"],
                    options=[
                        {k: option[k] for k in ("id", "name", "status", "maturity", "summary")}
                        for option in catalog["spec"]["options"]
                    ],
                )
            )
        return values, 0
    if action == "decision recommend":
        return catalogs.recommend_workspace(
            root, args.category, comma_list(args.signals), comma_list(args.selected), args.write
        ), 0
    if action == "decision approve":
        value = catalogs.approve_decision(root, args.category, args.option, args.by, at, args.adr)
        return dict(status=value["status"], record=value), 0
    if action == "principle list":
        return [
            p
            for c in catalogs.load_principles()
            for p in c["spec"]["principles"]
            if not args.family or p["family"] == args.family
        ], 0
    if action in {"resolve build", "resolve check"}:
        value = policy.resolve_workspace(root, action.endswith("build"), args.personal)
        result = dict(
            current=value["current"],
            rules=len(value["resolution"]["rules"]),
            profileDigest=value["resolution"]["profileLock"]["digest"],
        )
        if action.endswith("build"):
            result["outputs"] = [".aifw/effective-policy.json", ".aifw/framework.lock.yaml"]
        return result, 0 if value["current"] else 2
    if action == "change classify":
        signals = {}
        for flag in SIGNALS:
            parts = flag.split("-")
            signals[parts[0] + "".join(p.title() for p in parts[1:])] = getattr(args, flag.replace("-", "_"))
        if args.complexity:
            signals["semanticComplexity"] = args.complexity
        if not args.diff:
            return routing.classify_change(signals), 0
        derived = routing.derive_signals(root, args.base)
        signals.update({k: True for k in derived["signals"]})
        return dict(routing.classify_change(signals), derived=derived), 0
    if action == "route explain":
        try:
            failures = int(args.failed_attempts)
        except ValueError as error:
            raise AifwError("MANIFEST_INVALID", "failed-attempts must be an integer.") from error
        require(failures >= 0, "failed-attempts must not be negative.")
        return routing.route_task(
            dict(
                impact=args.impact,
                operation=args.operation,
                uncertainty=args.uncertainty,
                failedAttempts=failures,
                crossDomain=args.cross_domain,
            )
        ), 0
    if action == "route status":
        return routing.load_routing(root), 0
    if action == "route activate":
        report = read_json(args.report)
        if isinstance(report.get("cases"), list):
            report["cases"] = len(report["cases"])
        return routing.activate_routing(
            root, {k: report[k] for k in ("cases", "passRate", "criticalFailures")}, args.by, args.record
        ), 0
    if action == "route eval":
        value = conformance.evaluate_routing_cases(args.cases or assets() / "evals/routing/cases.yaml")
        if args.output:
            write_json(args.output, value)
        return dict(
            value,
            activationReady=value["cases"] >= 30
            and value["passRate"] >= 0.95
            and value["criticalFailures"] == 0,
        ), 2 if value["failures"] else 0
    if action.startswith(("waiver ", "break-glass ")):
        from . import permissions, waiver

        if action == "waiver list":
            return waiver.load_waivers(root), 0
        if action == "break-glass list":
            return permissions.list_break_glass(root), 0
        scope = comma_list(args.scope)
        if action == "waiver add":
            data = dict(ruleId=args.rule, scope=scope, reason=args.reason, requestedBy=args.requested_by)
            data.update(approvedBy=args.by, approvedAt=at, expiresAt=args.expires)
            return waiver.add_waiver(root, data), 0
        try:
            hours = float(args.hours)
        except ValueError as error:
            raise AifwError("MANIFEST_INVALID", "--hours must be a number.") from error
        require(0 < hours <= 72, "Break-glass grants last at most 72 hours.")
        expires = (timestamp(at) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
        grant = dict(incidentId=args.incident, scope=scope, reason=args.reason, approvedBy=args.by)
        grant.update(approvedAt=at, expiresAt=expires)
        return permissions.grant_break_glass(root, grant), 0
    if action.startswith("template "):
        if action == "template list":
            return specs.list_templates(), 0
        return specs.copy_template(root, args.name, args.change, args.output), 0
    if action == "runs show":
        from .hooks import summarize_runs

        value = summarize_runs(root, args.session)
        return value, 2 if any(s["status"] != "pass" for s in value) else 0
    if action.startswith("claude "):
        from . import claude

        if action == "claude check":
            value = claude.check_project(root)
            return value, 0 if value["status"] == "pass" else 2
        return (claude.install_command() if action == "claude install" else claude.enable_project(root)), 0
    if action.startswith("impasse "):
        from . import impasse

        if action == "impasse status":
            cases = [impasse.load_case(root, args.id)] if args.id else impasse.load_cases(root)
            frozen = sorted(c["id"] for c in cases if c["state"] in {"OPEN", "HUMAN_REVIEW"})
            return dict(cases=cases, frozen=frozen), 2 if frozen else 0
        if action == "impasse open":
            case = impasse.create_impasse_case(impasse.impasse_id(args.id), args.impact)
            return impasse.save_case(root, case, exclusive=True), 0
        case = impasse.load_case(root, args.id)
        if action == "impasse attempt":
            case = impasse.record_attempt(
                case,
                dict(
                    id=f"attempt-{len(case['attempts']) + 1}",
                    hypothesis=args.hypothesis,
                    intervention=args.intervention,
                    evidence=comma_list(args.evidence),
                    outcome=args.outcome,
                    occurredAt=at,
                ),
            )
        elif action == "impasse review":
            case = impasse.request_human_review(
                case,
                dict(suspectedRuleId=args.rule, explanation=args.explanation, proposedChange=args.proposal),
            )
        elif action == "impasse decide":
            record = project_path(root, args.record, file=True).relative_to(root.resolve()).as_posix()
            case = impasse.apply_human_decision(
                case, dict(approved=True, decisionRecord=record, decidedBy=args.by, decidedAt=at)
            )
        else:
            case = impasse.record_revalidation(
                case,
                dict(
                    passed=args.result == "passed",
                    evidence=comma_list(args.evidence),
                    updatedArtifacts=comma_list(args.artifacts),
                ),
            )
        impasse.save_case(root, case)
        return case, 2 if case["state"] in {"OPEN", "HUMAN_REVIEW"} else 0
    if action == "doctor":
        value = gates.run_doctor()
        if (root / "aifw.yaml").is_file():
            from .claude import check_project

            # Informational: CI has no Claude Code, so this never changes the exit code.
            value["claude"] = check_project(root)
        return value, 0 if value["healthy"] else 2
    if action == "eval":
        value = conformance.run_conformance(
            args.cases or assets() / "evals/cases", args.traces or assets() / "evals/traces"
        )
        return dict(
            value,
            activationReady=len(value["cases"]) >= 30
            and value["passRate"] >= 0.95
            and value["criticalFailures"] == 0,
        ), 0 if value["pass"] else 2
    if action == "validate":
        require(bool(args.level) != bool(args.change), "Use either --level or --change.")
        require(not args.write or args.change, "--write records evidence for a --change.")
        if args.change:
            value = gates.validate_change_workspace(root, args.change, args.write)
        else:
            value = gates.validate_workspace(root, args.level)
        return value, 2 if value["status"] == "blocked" else 0
    raise AifwError("MANIFEST_INVALID", f"Unknown command: {action}")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    try:
        parser = create_parser()
        args = parser.parse_args(argv)
        if not hasattr(args, "action"):
            parser.print_help()
            return 0
        value, status = execute(args, Path.cwd())
        print(value if isinstance(value, str) else json_text(value))
        return status
    except AifwError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        for detail in error.details:
            print(f"- {detail}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1
