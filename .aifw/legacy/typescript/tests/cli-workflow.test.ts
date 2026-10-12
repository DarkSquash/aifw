import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("..", import.meta.url));
const cliPath = path.join(projectRoot, "src", "cli.ts");

function runCli(cwd: string, ...args: string[]) {
  return spawnSync(process.execPath, [cliPath, ...args], {
    cwd,
    encoding: "utf8",
    env: { ...process.env, NO_COLOR: "1" },
  });
}

describe("end-to-end CLI workflow", () => {
  it("initializes Flutter through the short --flutter flag", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-init-flutter-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "app",
      "--name",
      "Projeto",
      "--flutter",
      "--existing",
      "--json",
    );

    assert.equal(init.status, 0, init.stderr);
    const result = JSON.parse(init.stdout) as {
      manifest: { spec: { projectType: string; profiles: string[] } };
    };
    assert.equal(result.manifest.spec.projectType, "existing");
    assert.deepEqual(result.manifest.spec.profiles, ["flutter-mobile"]);
  });

  it("maps every short stack flag to an installable profile", async () => {
    const cases = [
      { flag: "--web", profile: "web-ts" },
      { flag: "--python", profile: "python" },
    ] as const;

    for (const testCase of cases) {
      const root = await mkdtemp(path.join(tmpdir(), `aifw-init-${testCase.profile}-`));
      const init = runCli(
        root,
        "init",
        "--id",
        "app",
        "--name",
        "Projeto",
        testCase.flag,
        "--json",
      );
      assert.equal(init.status, 0, `${testCase.flag}: ${init.stderr}`);
      const result = JSON.parse(init.stdout) as {
        manifest: { spec: { profiles: string[] } };
      };
      assert.deepEqual(result.manifest.spec.profiles, [testCase.profile]);

      const resolve = runCli(root, "resolve", "build", "--json");
      assert.equal(resolve.status, 0, `${testCase.flag}: ${resolve.stderr}`);
    }
  });

  it("rejects multiple primary stack flags before writing project files", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-init-stack-conflict-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "app",
      "--name",
      "Projeto",
      "--flutter",
      "--web",
      "--json",
    );

    assert.equal(init.status, 1);
    assert.match(init.stderr, /POLICY_CONFLICT.*one.*stack/isu);
    await assert.rejects(() => readFile(path.join(root, "aifw.yaml"), "utf8"), /ENOENT/u);
  });

  it("initializes, audits, checks the map and explains a safe route", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-cli-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "northstar",
      "--name",
      "Northstar",
      "--existing",
      "--primary",
      "windows",
      "--targets",
      "windows,wsl,linux-ci",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);
    const initialized = JSON.parse(init.stdout) as { status: string; createdFiles: string[] };
    assert.equal(initialized.status, "initialized");
    assert.ok(initialized.createdFiles.includes("PROJECT_MAP.md"));

    const audit = runCli(root, "audit", "--json");
    assert.equal(audit.status, 0, audit.stderr);
    const auditResult = JSON.parse(audit.stdout) as {
      status: string;
      manifest: { metadata: { id: string } };
      projectMap: { current: boolean };
    };
    assert.equal(auditResult.status, "pass");
    assert.equal(auditResult.manifest.metadata.id, "northstar");
    assert.equal(auditResult.projectMap.current, true);

    const mapCheck = runCli(root, "map", "check", "--json");
    assert.equal(mapCheck.status, 0, mapCheck.stderr);
    assert.equal((JSON.parse(mapCheck.stdout) as { current: boolean }).current, true);

    const route = runCli(
      root,
      "route",
      "explain",
      "--impact",
      "L3",
      "--operation",
      "architecture-decision",
      "--uncertainty",
      "low",
      "--json",
    );
    assert.equal(route.status, 0, route.stderr);
    const routeResult = JSON.parse(route.stdout) as {
      route: string;
      executionMode: string;
      suggestedModel: string;
    };
    assert.deepEqual(routeResult, {
      route: "BRAIN",
      suggestedModel: "Sol",
      executionMode: "recommendation-only",
      reasons: ["impact:L3"],
    });

    const routingFile = await readFile(path.join(root, ".aifw", "routing.yaml"), "utf8");
    assert.match(routingFile, /enabled: false/);
  });

  it("classifies a framework change as L3 with required artifacts", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-classify-"));
    const result = runCli(
      root,
      "change",
      "classify",
      "--framework-core",
      "--json",
    );

    assert.equal(result.status, 0, result.stderr);
    const classification = JSON.parse(result.stdout) as {
      level: string;
      humanApproval: string;
      requiredArtifacts: string[];
    };
    assert.equal(classification.level, "L3");
    assert.equal(classification.humanApproval, "required");
    assert.ok(classification.requiredArtifacts.includes("adr"));
  });

  it("builds and checks the effective policy lock", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-resolve-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "northstar",
      "--name",
      "Northstar",
      "--primary",
      "windows",
      "--targets",
      "windows",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);

    const build = runCli(root, "resolve", "build", "--json");
    assert.equal(build.status, 0, build.stderr);
    const buildResult = JSON.parse(build.stdout) as {
      current: boolean;
      rules: number;
      profileDigest: string;
    };
    assert.equal(buildResult.current, true);
    assert.ok(buildResult.rules >= 8);
    assert.match(buildResult.profileDigest, /^[a-f0-9]{64}$/);

    const check = runCli(root, "resolve", "check", "--json");
    assert.equal(check.status, 0, check.stderr);
    assert.equal((JSON.parse(check.stdout) as { current: boolean }).current, true);
  });

  it("reports the human decisions still missing from Project Intake", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-intake-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "northstar",
      "--name",
      "Northstar",
      "--primary",
      "windows",
      "--targets",
      "windows",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);

    const status = runCli(root, "intake", "status", "--json");
    assert.equal(status.status, 2, status.stderr);
    const result = JSON.parse(status.stdout) as {
      ready: boolean;
      complete: boolean;
      questions: Array<{ field: string }>;
      agentAssessments: Array<{ id: string; owner: string; status: string }>;
    };
    assert.equal(result.ready, false);
    assert.equal(result.complete, false);
    assert.ok(result.questions.some((question) => question.field === "problem"));
    assert.ok(result.questions.every((question) => question.field !== "stack"));
    assert.equal(result.agentAssessments.length, 1);
    const [agentAssessment] = result.agentAssessments;
    assert.ok(agentAssessment);
    assert.equal(agentAssessment.id, "engineering-principles");
    assert.equal(agentAssessment.owner, "agent");
    assert.equal(agentAssessment.status, "pending");
  });

  it("runs progressive validation and blocks a required gate that has no evidence", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-validate-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "northstar",
      "--name",
      "Northstar",
      "--primary",
      "windows",
      "--targets",
      "windows",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);

    const l0 = runCli(root, "validate", "--level", "L0", "--json");
    assert.equal(l0.status, 0, l0.stderr);
    assert.equal((JSON.parse(l0.stdout) as { status: string }).status, "pass");

    const l1 = runCli(root, "validate", "--level", "L1", "--json");
    assert.equal(l1.status, 2, l1.stderr);
    const result = JSON.parse(l1.stdout) as {
      status: string;
      blockers: Array<{ gateId: string }>;
    };
    assert.equal(result.status, "blocked");
    assert.ok(result.blockers.some((blocker) => blocker.gateId === "tests"));
  });

  it("runs the bundled agent conformance smoke suite without enabling routing", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-eval-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "northstar",
      "--name",
      "Northstar",
      "--primary",
      "windows",
      "--targets",
      "windows",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);

    const evaluation = runCli(root, "eval", "--json");
    assert.equal(evaluation.status, 0, evaluation.stderr);
    const report = JSON.parse(evaluation.stdout) as {
      pass: boolean;
      cases: unknown[];
      activationReady: boolean;
    };
    assert.equal(report.pass, true);
    assert.equal(report.cases.length, 3);
    assert.equal(report.activationReady, false);

    const status = runCli(root, "route", "status", "--json");
    assert.equal(status.status, 0, status.stderr);
    assert.equal((JSON.parse(status.stdout) as { enabled: boolean }).enabled, false);
  });

  it("recommends, explains and records a human-approved architecture decision", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-decision-cli-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "northstar",
      "--name",
      "Northstar",
      "--primary",
      "windows",
      "--targets",
      "windows",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);

    const recommendation = runCli(
      root,
      "decision",
      "recommend",
      "--category",
      "application-architecture",
      "--signals",
      "domain:complex,integrations:many,testability:high",
      "--write",
      "--json",
    );
    assert.equal(recommendation.status, 0, recommendation.stderr);
    const recommendationResult = JSON.parse(recommendation.stdout) as {
      rankings: Array<{ optionId: string; eligible: boolean }>;
      requiresHumanApproval: boolean;
    };
    assert.equal(recommendationResult.rankings[0]?.optionId, "ports-and-adapters");
    assert.equal(recommendationResult.requiresHumanApproval, true);

    await mkdir(path.join(root, "docs", "adr"), { recursive: true });
    await writeFile(
      path.join(root, "docs", "adr", "ADR-0001-architecture.md"),
      "# ADR-0001\n\nAccepted: ports-and-adapters\n",
    );
    const approval = runCli(
      root,
      "decision",
      "approve",
      "--category",
      "application-architecture",
      "--option",
      "ports-and-adapters",
      "--by",
      "human:owner",
      "--at",
      "2026-08-22T18:00:00.000Z",
      "--adr",
      "docs/adr/ADR-0001-architecture.md",
      "--json",
    );
    assert.equal(approval.status, 0, approval.stderr);
    assert.equal((JSON.parse(approval.stdout) as { status: string }).status, "accepted");
    assert.match(
      await readFile(
        path.join(root, ".aifw", "decisions", "application-architecture.yaml"),
        "utf8",
      ),
      /approvedBy: human:owner/u,
    );
  });

  it("writes a contextual Clean Code and SOLID review without treating principles as dogma", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-principle-cli-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "app",
      "--name",
      "App",
      "--existing",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);

    const result = runCli(
      root,
      "principle",
      "review",
      "--signals",
      "design:object-oriented,duplication:stable",
      "--write",
      "--json",
    );
    assert.equal(result.status, 0, result.stderr);
    const review = JSON.parse(result.stdout) as {
      checks: Array<{ principleId: string; applicability: string; misuseRisks: string[] }>;
    };
    assert.equal(
      review.checks.find((check) => check.principleId === "solid-srp")?.applicability,
      "applicable",
    );
    assert.ok(
      review.checks
        .find((check) => check.principleId === "dry-stable-knowledge")
        ?.misuseRisks.some((risk) => /premature/iu.test(risk)),
    );
    assert.match(
      await readFile(
        path.join(root, ".aifw", "reviews", "engineering-principles.json"),
        "utf8",
      ),
      /"digest": "[a-f0-9]{64}"/u,
    );
  });

  it("rejects invalid lifecycle and routing enum values instead of silently downgrading risk", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-invalid-input-"));

    const validation = runCli(root, "validate", "--level", "L9", "--json");
    assert.equal(validation.status, 1);
    assert.match(validation.stderr, /MANIFEST_INVALID.*L9/isu);

    const route = runCli(
      root,
      "route",
      "explain",
      "--impact",
      "L9",
      "--operation",
      "architecture-decision",
      "--uncertainty",
      "low",
      "--json",
    );
    assert.equal(route.status, 1);
    assert.match(route.stderr, /MANIFEST_INVALID.*L9/isu);
  });
});
