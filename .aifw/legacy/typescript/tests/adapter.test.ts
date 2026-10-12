import assert from "node:assert/strict";
import { describe, it } from "node:test";

type PiAdapterModule = typeof import("../src/adapters/pi.ts");

async function loadPiAdapter(): Promise<PiAdapterModule> {
  try {
    return await import("../src/adapters/pi.ts");
  } catch (error) {
    assert.fail(`Pi adapter must be implemented: ${String(error)}`);
  }
}

describe("agent-independent adapter boundary", () => {
  it("renders a Pi plan while routing remains recommendation-only", async () => {
    const { createPiAdapter } = await loadPiAdapter();
    const adapter = createPiAdapter();
    const plan = adapter.plan({
      id: "task:review-map",
      role: "auditor",
      route: "WORK",
      impact: "L1",
      capabilities: ["filesystem:read", "test:run"],
      instructions: "Verify PROJECT_MAP freshness.",
    });

    assert.equal(adapter.id, "pi");
    assert.equal(plan.routing.enabled, false);
    assert.equal(plan.routing.mode, "recommendation-only");
    assert.equal(plan.routing.suggestedModel, "Terra");
    assert.deepEqual(plan.permissions, ["filesystem:read", "test:run"]);
  });

  it("defines bounded Pi roles without granting capabilities implicitly", async () => {
    const { PI_ROLES } = await loadPiAdapter();

    assert.deepEqual(
      PI_ROLES.map((role) => role.id),
      ["orchestrator", "researcher", "architect", "implementer", "reviewer", "auditor"],
    );
    assert.ok(PI_ROLES.every((role) => role.defaultCapabilities.length === 0));
  });

  it("can opt into executable routing only with an activated policy", async () => {
    const { createPiAdapter } = await loadPiAdapter();
    const adapter = createPiAdapter({ routingEnabled: true });
    const plan = adapter.plan({
      id: "task:architecture",
      role: "architect",
      route: "BRAIN",
      impact: "L3",
      capabilities: ["filesystem:read"],
      instructions: "Evaluate a framework policy change.",
    });

    assert.equal(plan.routing.enabled, true);
    assert.equal(plan.routing.selectedModel, "Sol");
  });
});
