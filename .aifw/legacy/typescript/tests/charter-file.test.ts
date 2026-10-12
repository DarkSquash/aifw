import { readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

type CharterFileModule = typeof import("../src/core/charter-file.ts");
type WorkspaceModule = typeof import("../src/core/workspace.ts");

async function modules(): Promise<{
  charter: CharterFileModule;
  workspace: WorkspaceModule;
}> {
  try {
    return {
      charter: await import("../src/core/charter-file.ts"),
      workspace: await import("../src/core/workspace.ts"),
    };
  } catch (error) {
    assert.fail(`charter persistence must be implemented: ${String(error)}`);
  }
}

async function project(): Promise<string> {
  const { mkdtemp } = await import("node:fs/promises");
  return mkdtemp(path.join(tmpdir(), "aifw-charter-"));
}

describe("persisted Project Charter workflow", () => {
  it("turns missing human decisions into adaptive questions without asking for a stack", async () => {
    const { charter, workspace } = await modules();
    const root = await project();
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "new",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });

    const status = await charter.assessWorkspaceCharter(root);

    assert.equal(status.ready, false);
    assert.deepEqual(
      status.questions.map((question) => question.field),
      ["problem", "audiences", "outcomes", "scope.in", "scope.out", "dataClassification", "autonomy"],
    );
    assert.ok(status.questions.every((question) => !question.prompt.toLocaleLowerCase().includes("stack")));
  });

  it("includes the agent-owned engineering principles review in intake status", async () => {
    const { charter, workspace } = await modules();
    const root = await project();
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "existing",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });

    const status = await charter.assessWorkspaceIntake(root);
    const [principles] = status.agentAssessments;

    assert.equal(status.complete, false);
    assert.ok(principles);
    assert.equal(principles.owner, "agent");
    assert.equal(principles.blockingHumanApproval, false);
    assert.equal(principles.status, "pending");
    assert.equal(principles.artifact, ".aifw/reviews/engineering-principles.json");
    assert.match(principles.nextAction ?? "", /principle review.*--write/u);
  });

  it("includes brownfield discovery and mapping in intake status for an existing project", async () => {
    const { charter, workspace } = await modules();
    const root = await project();
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "existing",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });

    const status = await charter.assessWorkspaceIntake(root);
    const brownfield = status.agentAssessments.find(
      (assessment) => assessment.id === "brownfield-mapping",
    );

    assert.ok(brownfield);
    assert.equal(brownfield.owner, "agent");
    assert.equal(brownfield.status, "pending");
    assert.equal(brownfield.blockingHumanApproval, false);
    assert.match(brownfield.nextAction ?? "", /adopt analyze.*--write/u);
    assert.equal(status.complete, false);
  });

  it("marks the agent principles assessment current after a reproducible review", async () => {
    const { charter, workspace } = await modules();
    const principles = await import("../src/core/principle-catalog.ts");
    const root = await project();
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "existing",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });
    await principles.reviewWorkspacePrinciples(root, {
      signals: ["change:behavior", "design:object-oriented"],
      write: true,
    });

    const status = await charter.assessWorkspaceIntake(root);
    const [assessment] = status.agentAssessments;

    assert.ok(assessment);
    assert.equal(assessment.status, "current");
    assert.equal(assessment.nextAction, undefined);
  });

  it("persists approval, updates the catalog purpose and recompiles PROJECT_MAP", async () => {
    const { charter, workspace } = await modules();
    const root = await project();
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "new",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });
    await writeFile(
      path.join(root, ".aifw", "charter.yaml"),
      `id: northstar
version: 0.1.0
projectType: new
problem: Centralize customer operations safely.
audiences: [support-team]
outcomes: [faster-resolution]
scope:
  in: [customer-records]
  out: [billing]
constraints: [windows-primary]
dataClassification: confidential
autonomy:
  localGit: true
  remoteGit: approval-required
  previewDeploy: true
  productionDeploy: approval-required
technicalPreference:
  mode: agent-recommend
unknowns: []
state: draft
`,
      "utf8",
    );

    const approved = await charter.approveWorkspaceCharter(root, {
      approvedBy: "human:owner",
      approvedAt: "2026-08-22T10:00:00.000Z",
    });

    assert.equal(approved.charter.state, "approved");
    assert.match(approved.charter.approval?.contentDigest ?? "", /^[a-f0-9]{64}$/);
    assert.match(
      await readFile(path.join(root, ".aifw", "charter.yaml"), "utf8"),
      /contentDigest:/,
    );
    assert.match(
      await readFile(path.join(root, ".aifw", "catalog.yaml"), "utf8"),
      /Centralize customer operations safely\./,
    );
    assert.match(
      await readFile(path.join(root, "PROJECT_MAP.md"), "utf8"),
      /Centralize customer operations safely\./,
    );
  });
});
