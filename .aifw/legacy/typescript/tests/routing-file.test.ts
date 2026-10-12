import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

type RoutingFileModule = typeof import("../src/core/routing-file.ts");
type WorkspaceModule = typeof import("../src/core/workspace.ts");

async function modules(): Promise<{
  routing: RoutingFileModule;
  workspace: WorkspaceModule;
}> {
  try {
    return {
      routing: await import("../src/core/routing-file.ts"),
      workspace: await import("../src/core/workspace.ts"),
    };
  } catch (error) {
    assert.fail(`routing persistence must be implemented: ${String(error)}`);
  }
}

async function initializedProject() {
  const { routing, workspace } = await modules();
  const { mkdtemp } = await import("node:fs/promises");
  const root = await mkdtemp(path.join(tmpdir(), "aifw-routing-"));
  await workspace.initializeProject(root, {
    id: "northstar",
    name: "Northstar",
    projectType: "new",
    locale: "pt-BR",
    primaryEnvironment: "windows",
    validationTargets: ["windows"],
  });
  return { root, routing };
}

describe("routing activation persistence", () => {
  it("keeps routing disabled when the conformance report has too few cases", async () => {
    const { root, routing } = await initializedProject();

    await assert.rejects(() =>
      routing.activateWorkspaceRouting(root, {
        humanApproved: true,
        approvedBy: "human:owner",
        approvalRecord: "ADR-0050",
        report: { cases: 3, passRate: 1, criticalFailures: 0 },
      }),
    );
    assert.equal((await routing.loadWorkspaceRouting(root)).enabled, false);
  });

  it("records approval and enables automatic routing only after thresholds pass", async () => {
    const { root, routing } = await initializedProject();

    const policy = await routing.activateWorkspaceRouting(root, {
      humanApproved: true,
      approvedBy: "human:owner",
      approvalRecord: "ADR-0050",
      report: { cases: 30, passRate: 0.97, criticalFailures: 0 },
    });

    assert.equal(policy.enabled, true);
    assert.equal(policy.mode, "automatic");
    assert.equal(policy.approval?.record, "ADR-0050");
    assert.deepEqual(policy.targets.BRAIN, {
      provider: "openai-codex",
      model: "gpt-5.6-sol",
    });
    assert.match(
      await readFile(path.join(root, ".aifw", "routing.yaml"), "utf8"),
      /enabled: true/,
    );
  });

  it("rejects malformed evaluation metrics instead of treating NaN as passing", async () => {
    const { root, routing } = await initializedProject();

    await assert.rejects(
      () =>
        routing.activateWorkspaceRouting(root, {
          humanApproved: true,
          approvedBy: "human:owner",
          approvalRecord: "ADR-0050",
          report: { cases: Number.NaN, passRate: 2, criticalFailures: -1 },
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "MANIFEST_INVALID");
        return true;
      },
    );
    assert.equal((await routing.loadWorkspaceRouting(root)).enabled, false);
  });

  it("rejects an agent identity as the routing approver", async () => {
    const { root, routing } = await initializedProject();

    await assert.rejects(
      () =>
        routing.activateWorkspaceRouting(root, {
          humanApproved: true,
          approvedBy: "agent:orchestrator",
          approvalRecord: "ADR-0050",
          report: { cases: 30, passRate: 1, criticalFailures: 0 },
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "APPROVAL_REQUIRED");
        return true;
      },
    );
  });
});
