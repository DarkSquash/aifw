import assert from "node:assert/strict";
import { describe, it } from "node:test";

type RoutingModule = typeof import("../src/core/routing.ts");

async function loadRouting(): Promise<RoutingModule> {
  try {
    return await import("../src/core/routing.ts");
  } catch (error) {
    assert.fail(`routing module must be implemented: ${String(error)}`);
  }
}

describe("deterministic cognitive routing", () => {
  it("uses FAST only for bounded low-risk work", async () => {
    const { routeTask } = await loadRouting();

    const decision = routeTask({
      impact: "L0",
      operation: "single-read",
      uncertainty: "low",
    });

    assert.equal(decision.route, "FAST");
    assert.equal(decision.suggestedModel, "Luna");
    assert.equal(decision.executionMode, "recommendation-only");
  });

  it("routes an architectural or L3 decision to BRAIN regardless of hint", async () => {
    const { routeTask } = await loadRouting();

    const decision = routeTask({
      impact: "L3",
      operation: "architecture-decision",
      uncertainty: "low",
      requestedRoute: "FAST",
    });

    assert.equal(decision.route, "BRAIN");
    assert.equal(decision.suggestedModel, "Sol");
    assert.ok(decision.reasons.includes("impact:L3"));
  });

  it("defaults ordinary implementation and review work to WORK", async () => {
    const { routeTask } = await loadRouting();

    const decision = routeTask({
      impact: "L1",
      operation: "implementation",
      uncertainty: "medium",
    });

    assert.equal(decision.route, "WORK");
    assert.equal(decision.suggestedModel, "Terra");
  });

  it("keeps model routing disabled until eval thresholds and approval pass", async () => {
    const { evaluateRoutingActivation } = await loadRouting();

    const notReady = evaluateRoutingActivation({
      humanApproved: true,
      report: { cases: 29, passRate: 1, criticalFailures: 0 },
    });
    assert.equal(notReady.enabled, false);
    assert.ok(notReady.blockers.includes("minimum-cases:30"));

    const ready = evaluateRoutingActivation({
      humanApproved: true,
      report: { cases: 30, passRate: 0.97, criticalFailures: 0 },
    });
    assert.equal(ready.enabled, true);
    assert.deepEqual(ready.blockers, []);
  });

  it("never activates routing without an explicit human approval", async () => {
    const { evaluateRoutingActivation } = await loadRouting();

    const result = evaluateRoutingActivation({
      humanApproved: false,
      report: { cases: 100, passRate: 1, criticalFailures: 0 },
    });

    assert.equal(result.enabled, false);
    assert.ok(result.blockers.includes("human-approval"));
  });
});
