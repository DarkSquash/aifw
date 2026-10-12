#!/usr/bin/env node

import { Command } from "commander";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

import { classifyChange, type ChangeSignals } from "./core/change.ts";
import {
  analyzeBrownfieldProject,
  applyBrownfieldMapping,
  approveBrownfieldMapping,
  assessBrownfieldAdoption,
  writeBrownfieldAnalysis,
} from "./core/brownfield.ts";
import {
  writeCodexHandoff,
  type CodexHandoffInput,
} from "./core/codex-handoff.ts";
import {
  approveWorkspaceCharter,
  assessWorkspaceIntake,
} from "./core/charter-file.ts";
import { discoverProject } from "./core/discovery.ts";
import {
  approveWorkspaceDecision,
  loadWorkspaceDecisionCatalogs,
  recommendWorkspaceDecision,
} from "./core/decision-catalog.ts";
import { runSystemDoctor } from "./core/doctor.ts";
import { AifwError } from "./core/errors.ts";
import { runConformanceSuite } from "./core/conformance.ts";
import { validateWorkspace } from "./core/gate-runner.ts";
import { resolveWorkspace } from "./core/policy-loader.ts";
import {
  loadPrincipleCatalogs,
  reviewWorkspacePrinciples,
} from "./core/principle-catalog.ts";
import {
  activateWorkspaceRouting,
  loadWorkspaceRouting,
} from "./core/routing-file.ts";
import { evaluateRoutingCases } from "./core/routing-evaluation.ts";
import { routeTask } from "./core/routing.ts";
import {
  analyzeSpecChange,
  approveSpecChange,
  archiveSpecChange,
  createSpecChange,
  listSpecChanges,
  previewSpecSync,
  updateSpecChangeStatus,
  validateSpecChange,
} from "./core/spec-lifecycle.ts";
import {
  buildWorkspaceMap,
  initializeProject,
  loadWorkspaceManifest,
} from "./core/workspace.ts";

export const VERSION = "0.2.0";

function output(value: unknown, json: boolean): void {
  if (json) {
    process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
    return;
  }
  if (typeof value === "string") {
    process.stdout.write(`${value}\n`);
    return;
  }
  process.stdout.write(`${JSON.stringify(value, null, 2)}\n`);
}

function commaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function enumValue<T extends string>(
  value: string,
  allowed: readonly T[],
  field: string,
): T {
  if (!allowed.some((candidate) => candidate === value)) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `Invalid ${field}: ${value}. Expected one of ${allowed.join(", ")}.`,
      [value],
    );
  }
  return value as T;
}

function addJsonOption(command: Command): Command {
  return command.option("--json", "emit stable machine-readable JSON");
}

function selectedStackProfiles(options: {
  flutter?: boolean;
  web?: boolean;
  python?: boolean;
}): string[] {
  const selections = [
    { selected: options.flutter === true, profile: "flutter-mobile", flag: "--flutter" },
    { selected: options.web === true, profile: "web-ts", flag: "--web" },
    { selected: options.python === true, profile: "python", flag: "--python" },
  ].filter((selection) => selection.selected);
  if (selections.length > 1) {
    throw new AifwError(
      "POLICY_CONFLICT",
      "Choose only one primary stack flag during init.",
      selections.map((selection) => selection.flag),
    );
  }
  return selections.map((selection) => selection.profile);
}

export function createProgram(): Command {
  const program = new Command()
    .name("aifw")
    .description("AI Software Engineering Framework control plane")
    .version(VERSION);

  addJsonOption(
    program
      .command("init")
      .description("initialize the framework control plane in a project")
      .requiredOption("--id <id>", "stable project id")
      .requiredOption("--name <name>", "human-readable project name")
      .option("--existing", "initialize an existing codebase")
      .option("--flutter", "use the Flutter mobile profile")
      .option("--web", "use the Web profile for React, JavaScript, TypeScript and related stacks")
      .option("--python", "use the Python profile")
      .option("--locale <locale>", "project language", "pt-BR")
      .option("--primary <environment>", "primary environment", "windows")
      .option(
        "--targets <environments>",
        "comma-separated validation targets",
        "windows,wsl,linux-ci",
      ),
  ).action(async (options: {
    id: string;
    name: string;
    existing?: boolean;
    flutter?: boolean;
    web?: boolean;
    python?: boolean;
    locale: string;
    primary: "windows" | "wsl" | "linux";
    targets: string;
    json?: boolean;
  }) => {
    const result = await initializeProject(process.cwd(), {
      id: options.id,
      name: options.name,
      projectType: options.existing === true ? "existing" : "new",
      locale: options.locale,
      primaryEnvironment: options.primary,
      validationTargets: commaList(options.targets) as Array<
        "windows" | "wsl" | "linux" | "linux-ci"
      >,
      profiles: selectedStackProfiles(options),
    });
    output(
      { status: "initialized", createdFiles: result.createdFiles, manifest: result.manifest },
      options.json === true,
    );
  });

  addJsonOption(
    program.command("audit").description("inspect a project without changing it"),
  ).action(async (options: { json?: boolean }) => {
    const [manifest, discovery, projectMap] = await Promise.all([
      loadWorkspaceManifest(process.cwd()),
      discoverProject(process.cwd()),
      buildWorkspaceMap(process.cwd(), { write: false }),
    ]);
    const status = projectMap.current ? "pass" : "warning";
    output(
      {
        status,
        manifest,
        discovery,
        projectMap: { current: projectMap.current, digest: projectMap.digest },
      },
      options.json === true,
    );
  });

  const intake = program
    .command("intake")
    .description("assess and approve the human Project Charter decisions");
  addJsonOption(
    intake
      .command("status")
      .description("show missing human decisions and agent-owned technical assessments"),
  ).action(async (options: { json?: boolean }) => {
    const assessment = await assessWorkspaceIntake(process.cwd());
    output(assessment, options.json === true);
    if (!assessment.complete) process.exitCode = 2;
  });
  addJsonOption(
    intake
      .command("approve")
      .description("persist explicit human approval of a ready charter")
      .requiredOption("--by <identity>", "human approver identity")
      .option("--at <timestamp>", "ISO-8601 approval timestamp"),
  ).action(async (options: { by: string; at?: string; json?: boolean }) => {
    const result = await approveWorkspaceCharter(process.cwd(), {
      approvedBy: options.by,
      approvedAt: options.at ?? new Date().toISOString(),
    });
    output(
      {
        status: "approved",
        charter: result.charter,
        projectMapDigest: result.projectMapDigest,
      },
      options.json === true,
    );
  });

  const map = program.command("map").description("compile and verify PROJECT_MAP.md");
  addJsonOption(map.command("build").description("regenerate PROJECT_MAP.md")).action(
    async (options: { json?: boolean }) => {
      const result = await buildWorkspaceMap(process.cwd(), { write: true });
      output(
        { current: result.current, digest: result.digest, path: "PROJECT_MAP.md" },
        options.json === true,
      );
    },
  );
  addJsonOption(map.command("check").description("check PROJECT_MAP.md freshness")).action(
    async (options: { json?: boolean }) => {
      const result = await buildWorkspaceMap(process.cwd(), { write: false });
      output(
        { current: result.current, digest: result.digest, path: "PROJECT_MAP.md" },
        options.json === true,
      );
      if (!result.current) process.exitCode = 2;
    },
  );

  const adopt = program
    .command("adopt")
    .description("analyze and map an existing project through a reviewable workflow");
  addJsonOption(
    adopt
      .command("analyze")
      .description("discover factual brownfield references without changing application code")
      .option("--write", "persist the discovery report under .aifw/adoption")
      .option("--at <timestamp>", "ISO-8601 analysis timestamp"),
  ).action(async (options: { write?: boolean; at?: string; json?: boolean }) => {
    const generatedAt = options.at ?? new Date().toISOString();
    if (options.write === true) {
      const result = await writeBrownfieldAnalysis(process.cwd(), { generatedAt });
      output(
        {
          persisted: true,
          path: result.reportPath,
          digest: result.report.digest,
          candidates: result.report.candidates.entities.length,
          unknowns: result.report.unknowns,
        },
        options.json === true,
      );
      return;
    }
    const report = await analyzeBrownfieldProject(process.cwd(), { generatedAt });
    output({ persisted: false, report }, options.json === true);
  });
  addJsonOption(
    adopt
      .command("apply")
      .description("write factual discovery candidates to catalog and generated architecture")
      .option("--at <timestamp>", "ISO-8601 application timestamp"),
  ).action(async (options: { at?: string; json?: boolean }) => {
    const result = await applyBrownfieldMapping(process.cwd(), {
      appliedAt: options.at ?? new Date().toISOString(),
    });
    output(
      {
        status: result.state.status,
        entities: result.appliedEntityIds,
        architecture: result.architecturePath,
        projectMap: { current: result.projectMap.current, digest: result.projectMap.digest },
      },
      options.json === true,
    );
  });
  addJsonOption(adopt.command("status").description("show brownfield mapping review state")).action(
    async (options: { json?: boolean }) => {
      const assessment = await assessBrownfieldAdoption(process.cwd());
      output(assessment, options.json === true);
      if (assessment.status !== "current") process.exitCode = 2;
    },
  );
  addJsonOption(
    adopt
      .command("approve")
      .description("confirm the generated mapping after human review")
      .requiredOption("--by <identity>", "human approver identity")
      .option("--at <timestamp>", "ISO-8601 approval timestamp"),
  ).action(async (options: { by: string; at?: string; json?: boolean }) => {
    const result = await approveBrownfieldMapping(process.cwd(), {
      approvedBy: options.by,
      approvedAt: options.at ?? new Date().toISOString(),
    });
    output(
      {
        status: result.state.status,
        approval: result.state.approval,
        projectMap: { current: result.projectMap.current, digest: result.projectMap.digest },
      },
      options.json === true,
    );
  });

  const spec = program
    .command("spec")
    .description("manage current capability specs and active change deltas");
  addJsonOption(
    spec
      .command("new <id>")
      .description("create a self-contained active spec change")
      .requiredOption("--title <title>", "human-readable change title")
      .requiredOption("--summary <summary>", "intent and expected outcome")
      .requiredOption("--level <level>", "L0, L1, L2 or L3")
      .option("--at <timestamp>", "ISO-8601 creation timestamp"),
  ).action(async (id: string, options: {
    title: string;
    summary: string;
    level: string;
    at?: string;
    json?: boolean;
  }) => {
    const result = await createSpecChange(process.cwd(), {
      id,
      title: options.title,
      summary: options.summary,
      level: enumValue(options.level, ["L0", "L1", "L2", "L3"] as const, "level"),
      createdAt: options.at ?? new Date().toISOString(),
    });
    output(
      { status: "created", change: result.change, createdFiles: result.createdFiles },
      options.json === true,
    );
  });
  addJsonOption(spec.command("list").description("list active and archived spec changes")).action(
    async (options: { json?: boolean }) => {
      output(await listSpecChanges(process.cwd()), options.json === true);
    },
  );
  addJsonOption(
    spec.command("show <id>").description("show a spec change summary and its location"),
  ).action(async (id: string, options: { json?: boolean }) => {
    const entry = (await listSpecChanges(process.cwd())).find((candidate) => candidate.id === id);
    if (entry === undefined) {
      throw new AifwError("NOT_READY", `Spec change not found: ${id}`, [id]);
    }
    output(entry, options.json === true);
  });
  addJsonOption(
    spec
      .command("status <id>")
      .description("show or advance an active spec change status")
      .option("--set <status>", "set active or ready after required checks"),
  ).action(async (id: string, options: { set?: string; json?: boolean }) => {
    if (options.set !== undefined) {
      const change = await updateSpecChangeStatus(
        process.cwd(),
        id,
        enumValue(options.set, ["active", "ready"] as const, "status"),
      );
      output({ status: change.status, change }, options.json === true);
      return;
    }
    const entry = (await listSpecChanges(process.cwd())).find((candidate) => candidate.id === id);
    if (entry === undefined) {
      throw new AifwError("NOT_READY", `Spec change not found: ${id}`, [id]);
    }
    output(entry, options.json === true);
  });
  addJsonOption(
    spec
      .command("validate <id>")
      .description("validate delta preconditions against current capability truth"),
  ).action(async (id: string, options: { json?: boolean }) => {
    const result = await validateSpecChange(process.cwd(), id);
    output(result, options.json === true);
    if (!result.pass) process.exitCode = 2;
  });
  addJsonOption(
    spec
      .command("analyze <id>")
      .description("run the read-only requirement-to-evidence traceability analyzer"),
  ).action(async (id: string, options: { json?: boolean }) => {
    const result = await analyzeSpecChange(process.cwd(), id);
    output(result, options.json === true);
    if (!result.pass) process.exitCode = 2;
  });
  addJsonOption(
    spec
      .command("sync <id>")
      .description("preview how validated deltas would update current capability truth")
      .option("--dry-run", "explicitly confirm that no current spec will be mutated"),
  ).action(async (id: string, options: { dryRun?: boolean; json?: boolean }) => {
    const result = await previewSpecSync(process.cwd(), id);
    output({ ...result, dryRun: true }, options.json === true);
    if (!result.pass) process.exitCode = 2;
  });
  addJsonOption(
    spec
      .command("approve <id>")
      .description("persist human approval for a critical spec change")
      .requiredOption("--by <identity>", "human approver identity")
      .requiredOption("--record <path>", "existing ADR or approval record inside the project")
      .option("--at <timestamp>", "ISO-8601 approval timestamp"),
  ).action(async (id: string, options: {
    by: string;
    record: string;
    at?: string;
    json?: boolean;
  }) => {
    const change = await approveSpecChange(process.cwd(), id, {
      approvedBy: options.by,
      approvedAt: options.at ?? new Date().toISOString(),
      record: options.record,
    });
    output({ status: "approved", change }, options.json === true);
  });
  addJsonOption(
    spec
      .command("archive <id>")
      .description("atomically merge deltas into current truth and archive the change")
      .option("--at <timestamp>", "ISO-8601 archive timestamp"),
  ).action(async (id: string, options: { at?: string; json?: boolean }) => {
    const result = await archiveSpecChange(process.cwd(), id, {
      archivedAt: options.at ?? new Date().toISOString(),
    });
    output({ status: "archived", ...result }, options.json === true);
  });

  const decision = program
    .command("decision")
    .description("compare and record project-wide architecture decisions");
  addJsonOption(
    decision
      .command("list")
      .description("list available decision categories and alternatives")
      .option("--category <id>", "filter by decision category"),
  ).action(async (options: { category?: string; json?: boolean }) => {
    const catalogs = (await loadWorkspaceDecisionCatalogs(process.cwd())).filter(
      (catalog) => options.category === undefined || catalog.metadata.category === options.category,
    );
    output(
      catalogs.map((catalog) => ({
        id: catalog.metadata.id,
        category: catalog.metadata.category,
        title: catalog.spec.title,
        scope: catalog.metadata.scope,
        impact: catalog.metadata.impact,
        drivers: catalog.spec.drivers,
        options: catalog.spec.options.map((option) => ({
          id: option.id,
          name: option.name,
          status: option.status,
          maturity: option.maturity,
          summary: option.summary,
        })),
      })),
      options.json === true,
    );
  });
  addJsonOption(
    decision
      .command("recommend")
      .description("rank alternatives from explicit project signals")
      .requiredOption("--category <id>", "decision category")
      .requiredOption("--signals <signals>", "comma-separated project signals")
      .option("--selected <ids>", "comma-separated decisions already selected", "")
      .option("--write", "persist the reviewable decision case"),
  ).action(async (options: {
    category: string;
    signals: string;
    selected: string;
    write?: boolean;
    json?: boolean;
  }) => {
    const result = await recommendWorkspaceDecision(process.cwd(), {
      category: options.category,
      signals: commaList(options.signals),
      selectedOptionIds: commaList(options.selected),
      write: options.write === true,
    });
    output(result, options.json === true);
  });
  addJsonOption(
    decision
      .command("approve")
      .description("accept an eligible alternative using human approval and an ADR")
      .requiredOption("--category <id>", "decision category")
      .requiredOption("--option <id>", "selected alternative")
      .requiredOption("--by <identity>", "human approver identity, prefixed human:")
      .requiredOption("--adr <path>", "existing ADR path inside the project")
      .option("--at <timestamp>", "ISO-8601 approval timestamp"),
  ).action(async (options: {
    category: string;
    option: string;
    by: string;
    adr: string;
    at?: string;
    json?: boolean;
  }) => {
    const record = await approveWorkspaceDecision(process.cwd(), {
      category: options.category,
      optionId: options.option,
      approvedBy: options.by,
      approvedAt: options.at ?? new Date().toISOString(),
      adrPath: options.adr,
    });
    output({ status: record.status, record }, options.json === true);
  });

  const principle = program
    .command("principle")
    .description("review Clean Code, SOLID and foundational principles contextually");
  addJsonOption(
    principle
      .command("list")
      .description("list engineering principles and their applicability signals")
      .option("--family <family>", "clean-code, solid or foundational"),
  ).action(async (options: { family?: string; json?: boolean }) => {
    const catalogs = await loadPrincipleCatalogs();
    const principles = catalogs
      .flatMap((catalog) => catalog.spec.principles)
      .filter((entry) => options.family === undefined || entry.family === options.family);
    output(principles, options.json === true);
  });
  addJsonOption(
    principle
      .command("review")
      .description("build a contextual engineering-principle checklist")
      .requiredOption("--signals <signals>", "comma-separated project or change signals")
      .option("--write", "persist the review under .aifw/reviews"),
  ).action(async (options: { signals: string; write?: boolean; json?: boolean }) => {
    const review = await reviewWorkspacePrinciples(process.cwd(), {
      signals: commaList(options.signals),
      write: options.write === true,
    });
    output(review, options.json === true);
  });

  const resolve = program
    .command("resolve")
    .description("resolve authority layers into a pinned effective policy");
  addJsonOption(
    resolve
      .command("build")
      .description("write the effective policy and framework lock")
      .option("--personal <path>", "optional personal defaults PolicySet"),
  ).action(async (options: { personal?: string; json?: boolean }) => {
    const result = await resolveWorkspace(process.cwd(), {
      ...(options.personal === undefined ? {} : { personalPolicyPath: options.personal }),
      write: true,
    });
    output(
      {
        current: result.current,
        rules: result.resolution.rules.length,
        profileDigest: result.resolution.profileLock.digest,
        outputs: [".aifw/effective-policy.json", ".aifw/framework.lock.yaml"],
      },
      options.json === true,
    );
  });
  addJsonOption(
    resolve
      .command("check")
      .description("verify the committed effective policy and lock")
      .option("--personal <path>", "optional personal defaults PolicySet"),
  ).action(async (options: { personal?: string; json?: boolean }) => {
    const result = await resolveWorkspace(process.cwd(), {
      ...(options.personal === undefined ? {} : { personalPolicyPath: options.personal }),
      write: false,
    });
    output(
      {
        current: result.current,
        rules: result.resolution.rules.length,
        profileDigest: result.resolution.profileLock.digest,
      },
      options.json === true,
    );
    if (!result.current) process.exitCode = 2;
  });

  const change = program.command("change").description("classify change impact");
  addJsonOption(
    change
      .command("classify")
      .option("--read-only")
      .option("--docs-only")
      .option("--behavior-change")
      .option("--local-only")
      .option("--reversible")
      .option("--cross-module")
      .option("--shared-contract")
      .option("--sensitive-data")
      .option("--global-design-system")
      .option("--external-cost")
      .option("--production")
      .option("--touches-auth")
      .option("--framework-core")
      .option("--constitution")
      .option("--security-boundary")
      .option("--destructive-migration")
      .option("--breaking-contract")
      .option("--irreversible-production")
      .option("--complexity <route>", "fast, work or brain"),
  ).action((options: Record<string, boolean | string | undefined>) => {
    const signals: ChangeSignals = {
      readOnly: options["readOnly"] === true,
      docsOnly: options["docsOnly"] === true,
      behaviorChange: options["behaviorChange"] === true,
      localOnly: options["localOnly"] === true,
      reversible: options["reversible"] === true,
      crossModule: options["crossModule"] === true,
      sharedContract: options["sharedContract"] === true,
      sensitiveData: options["sensitiveData"] === true,
      globalDesignSystem: options["globalDesignSystem"] === true,
      externalCost: options["externalCost"] === true,
      production: options["production"] === true,
      touchesAuth: options["touchesAuth"] === true,
      frameworkCore: options["frameworkCore"] === true,
      constitution: options["constitution"] === true,
      securityBoundary: options["securityBoundary"] === true,
      destructiveMigration: options["destructiveMigration"] === true,
      breakingContract: options["breakingContract"] === true,
      irreversibleProduction: options["irreversibleProduction"] === true,
      ...(typeof options["complexity"] === "string"
        ? {
            semanticComplexity: enumValue(
              options["complexity"],
              ["fast", "work", "brain"] as const,
              "complexity",
            ),
          }
        : {}),
    };
    output(classifyChange(signals), options["json"] === true);
  });

  const route = program.command("route").description("explain cognitive routing");
  addJsonOption(
    route
      .command("explain")
      .requiredOption("--impact <level>", "L0, L1, L2 or L3")
      .requiredOption("--operation <operation>")
      .requiredOption("--uncertainty <level>", "low, medium or high")
      .option("--failed-attempts <count>", "number of previous failures", "0")
      .option("--cross-domain"),
  ).action((options: {
    impact: string;
    operation: string;
    uncertainty: string;
    failedAttempts: string;
    crossDomain?: boolean;
    json?: boolean;
  }) => {
    const result = routeTask({
      impact: enumValue(options.impact, ["L0", "L1", "L2", "L3"] as const, "impact"),
      operation: enumValue(
        options.operation,
        [
          "single-read",
          "discovery",
          "documentation",
          "implementation",
          "review",
          "research",
          "architecture-decision",
          "incident-response",
        ] as const,
        "operation",
      ),
      uncertainty: enumValue(
        options.uncertainty,
        ["low", "medium", "high"] as const,
        "uncertainty",
      ),
      failedAttempts: Number.parseInt(options.failedAttempts, 10),
      crossDomain: options.crossDomain === true,
    });
    output(result, options.json === true);
  });
  addJsonOption(route.command("status").description("show persisted routing state")).action(
    async (options: { json?: boolean }) => {
      output(await loadWorkspaceRouting(process.cwd()), options.json === true);
    },
  );
  addJsonOption(
    route
      .command("eval")
      .description("evaluate deterministic routing against reviewable cases")
      .option("--cases <path>", "routing case fixture")
      .option("--output <path>", "write the JSON activation report"),
  ).action(async (options: { cases?: string; output?: string; json?: boolean }) => {
    const casesPath =
      options.cases ?? fileURLToPath(new URL("../evals/routing/cases.yaml", import.meta.url));
    const report = await evaluateRoutingCases(casesPath);
    if (options.output !== undefined) {
      await writeFile(options.output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
    }
    output(
      { ...report, activationReady: report.cases >= 30 && report.passRate >= 0.95 && report.criticalFailures === 0 },
      options.json === true,
    );
    if (report.failures.length > 0) process.exitCode = 2;
  });
  addJsonOption(
    route
      .command("activate")
      .description("activate routing after passing evals and human approval")
      .requiredOption("--report <path>", "JSON conformance report")
      .requiredOption("--by <identity>", "human approver identity")
      .requiredOption("--record <reference>", "persisted ADR or approval record"),
  ).action(async (options: { report: string; by: string; record: string; json?: boolean }) => {
    const reportValue = JSON.parse(await readFile(options.report, "utf8")) as {
      cases: number | unknown[];
      passRate: number;
      criticalFailures: number;
    };
    const policy = await activateWorkspaceRouting(process.cwd(), {
      humanApproved: true,
      approvedBy: options.by,
      approvalRecord: options.record,
      report: {
        cases: Array.isArray(reportValue.cases) ? reportValue.cases.length : reportValue.cases,
        passRate: reportValue.passRate,
        criticalFailures: reportValue.criticalFailures,
      },
    });
    output(policy, options.json === true);
  });

  const handoff = program
    .command("handoff")
    .description("create structured manual handoffs for another executor");
  addJsonOption(
    handoff
      .command("codex")
      .description("write a redacted Markdown handoff for manual transfer to Codex")
      .requiredOption("--input <path>", "structured handoff JSON")
      .option("--output <path>", "project-relative Markdown output path"),
  ).action(async (options: { input: string; output?: string; json?: boolean }) => {
    const input = JSON.parse(await readFile(options.input, "utf8")) as CodexHandoffInput;
    const result = await writeCodexHandoff(process.cwd(), input, options.output);
    output(
      { status: "created", path: result.relativePath, transfer: "manual" },
      options.json === true,
    );
  });

  addJsonOption(
    program.command("doctor").description("check Node, Git, Windows and WSL"),
  ).action(async (options: { json?: boolean }) => {
    const result = await runSystemDoctor();
    output(result, options.json === true);
    if (!result.healthy) process.exitCode = 2;
  });

  addJsonOption(
    program
      .command("eval")
      .description("run agent behavioral conformance fixtures")
      .option("--cases <path>", "case directory")
      .option("--traces <path>", "trace directory"),
  ).action(async (options: { cases?: string; traces?: string; json?: boolean }) => {
    const casesDirectory =
      options.cases ?? fileURLToPath(new URL("../evals/cases/", import.meta.url));
    const tracesDirectory =
      options.traces ?? fileURLToPath(new URL("../evals/traces/", import.meta.url));
    const result = await runConformanceSuite(casesDirectory, tracesDirectory);
    output(
      {
        ...result,
        activationReady:
          result.cases.length >= 30 && result.passRate >= 0.95 && result.criticalFailures === 0,
      },
      options.json === true,
    );
    if (!result.pass) process.exitCode = 2;
  });

  addJsonOption(
    program
      .command("validate")
      .description("run quality gates selected by L0-L3 impact")
      .requiredOption("--level <level>", "L0, L1, L2 or L3"),
  ).action(async (options: { level: string; json?: boolean }) => {
    const level = enumValue(options.level, ["L0", "L1", "L2", "L3"] as const, "level");
    const result = await validateWorkspace(process.cwd(), level);
    output(result, options.json === true);
    if (result.status === "blocked") process.exitCode = 2;
  });

  return program;
}

try {
  await createProgram().parseAsync();
} catch (error) {
  if (error instanceof AifwError) {
    process.stderr.write(`${error.code}: ${error.message}\n`);
    for (const detail of error.details) process.stderr.write(`- ${detail}\n`);
  } else {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  }
  process.exitCode = 1;
}
