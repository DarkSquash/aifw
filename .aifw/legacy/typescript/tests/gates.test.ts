import assert from "node:assert/strict";
import { describe, it } from "node:test";

type GatesModule = typeof import("../src/core/gates.ts");

async function loadGates(): Promise<GatesModule> {
  try {
    return await import("../src/core/gates.ts");
  } catch (error) {
    assert.fail(`gates module must be implemented: ${String(error)}`);
  }
}

describe("progressive quality gates", () => {
  it("blocks a deterministic hard-gate failure", async () => {
    const { evaluateQualityGates } = await loadGates();

    const evaluation = evaluateQualityGates({
      change: { level: "L1", humanApproval: "none" },
      requiredGateIds: ["typecheck", "tests"],
      results: [
        {
          gateId: "typecheck",
          enforcement: "hard",
          status: "fail",
          summary: "Type error in src/index.ts",
          evidence: ["tsc exit 2"],
        },
        {
          gateId: "tests",
          enforcement: "hard",
          status: "pass",
          summary: "22 tests passed",
          evidence: ["node --test exit 0"],
        },
      ],
    });

    assert.equal(evaluation.status, "blocked");
    assert.deepEqual(evaluation.blockers.map((item) => item.gateId), [
      "typecheck",
    ]);
  });

  it("reports an audit finding without pretending it is deterministic", async () => {
    const { evaluateQualityGates } = await loadGates();

    const evaluation = evaluateQualityGates({
      change: { level: "L1", humanApproval: "none" },
      requiredGateIds: ["ux-review"],
      results: [
        {
          gateId: "ux-review",
          enforcement: "audit",
          status: "fail",
          summary: "Hierarchy may be unclear",
          evidence: ["auditor finding UX-12"],
        },
      ],
    });

    assert.equal(evaluation.status, "warning");
    assert.deepEqual(evaluation.blockers, []);
    assert.equal(evaluation.warnings[0]?.gateId, "ux-review");
  });

  it("blocks a required approval that has no approval evidence", async () => {
    const { evaluateQualityGates } = await loadGates();

    const evaluation = evaluateQualityGates({
      change: { level: "L3", humanApproval: "required" },
      requiredGateIds: [],
      results: [],
    });

    assert.equal(evaluation.status, "blocked");
    assert.equal(evaluation.blockers[0]?.gateId, "human-approval");
  });

  it("does not accept an agent identity as human approval evidence", async () => {
    const { evaluateQualityGates } = await loadGates();

    const evaluation = evaluateQualityGates({
      change: { level: "L3", humanApproval: "required" },
      requiredGateIds: [],
      results: [],
      approval: {
        approvedBy: "agent:orchestrator",
        approvalDigest: "a".repeat(64),
      },
    });

    assert.equal(evaluation.status, "blocked");
    assert.equal(evaluation.blockers[0]?.gateId, "human-approval");
  });

  it("blocks a missing required gate instead of treating it as a pass", async () => {
    const { evaluateQualityGates } = await loadGates();

    const evaluation = evaluateQualityGates({
      change: { level: "L1", humanApproval: "none" },
      requiredGateIds: ["tests"],
      results: [],
    });

    assert.equal(evaluation.status, "blocked");
    assert.equal(evaluation.blockers[0]?.summary, "Required gate did not run");
  });
});
