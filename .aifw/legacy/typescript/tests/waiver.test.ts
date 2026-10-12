import assert from "node:assert/strict";
import { describe, it } from "node:test";

type WaiverModule = typeof import("../src/core/waiver.ts");

async function loadWaiver(): Promise<WaiverModule> {
  try {
    return await import("../src/core/waiver.ts");
  } catch (error) {
    assert.fail(`waiver module must be implemented: ${String(error)}`);
  }
}

describe("controlled waivers", () => {
  it("expires automatically at the declared instant", async () => {
    const { createWaiver, isWaiverActive } = await loadWaiver();
    const waiver = createWaiver({
      id: "waiver:compact-button",
      ruleId: "design.button-radius",
      scope: ["component:data-table"],
      reason: "Dense table controls overlap",
      requestedBy: "agent:worker",
      approvedBy: "human:owner",
      approvedAt: "2026-08-22T10:00:00.000Z",
      expiresAt: "2026-08-23T10:00:00.000Z",
      checkpoint: "git:abc123",
    });

    assert.equal(
      isWaiverActive(waiver, new Date("2026-08-23T09:59:59.000Z")),
      true,
    );
    assert.equal(
      isWaiverActive(waiver, new Date("2026-08-23T10:00:00.000Z")),
      false,
    );
  });

  it("rejects waivers for irrenunciable rules", async () => {
    const { createWaiver } = await loadWaiver();

    assert.throws(
      () =>
        createWaiver(
          {
            id: "waiver:secret",
            ruleId: "security.no-secret-output",
            scope: ["project"],
            reason: "Debugging",
            requestedBy: "agent:worker",
            approvedBy: "human:owner",
            approvedAt: "2026-08-22T10:00:00.000Z",
            expiresAt: "2026-08-23T10:00:00.000Z",
            checkpoint: "git:abc123",
          },
          { nonWaivableRuleIds: ["security.no-secret-output"] },
        ),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "POLICY_CONFLICT");
        return true;
      },
    );
  });

  it("rejects an already expired waiver", async () => {
    const { createWaiver } = await loadWaiver();

    assert.throws(() =>
      createWaiver({
        id: "waiver:expired",
        ruleId: "design.button-radius",
        scope: ["component:data-table"],
        reason: "Expired request",
        requestedBy: "agent:worker",
        approvedBy: "human:owner",
        approvedAt: "2026-08-23T10:00:00.000Z",
        expiresAt: "2026-08-22T10:00:00.000Z",
        checkpoint: "git:abc123",
      }),
    );
  });

  it("rejects an agent identity as waiver approver", async () => {
    const { createWaiver } = await loadWaiver();

    assert.throws(
      () =>
        createWaiver({
          id: "waiver:agent-approved",
          ruleId: "design.button-radius",
          scope: ["component:data-table"],
          reason: "Temporary density exception",
          requestedBy: "agent:worker",
          approvedBy: "agent:orchestrator",
          approvedAt: "2026-08-22T10:00:00.000Z",
          expiresAt: "2026-08-23T10:00:00.000Z",
          checkpoint: "git:abc123",
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "APPROVAL_REQUIRED");
        return true;
      },
    );
  });
});
