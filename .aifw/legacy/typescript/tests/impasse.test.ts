import assert from "node:assert/strict";
import { describe, it } from "node:test";

type ImpasseModule = typeof import("../src/core/impasse.ts");

async function loadImpasse(): Promise<ImpasseModule> {
  try {
    return await import("../src/core/impasse.ts");
  } catch (error) {
    assert.fail(`impasse module must be implemented: ${String(error)}`);
  }
}

describe("impasse prevention state machine", () => {
  it("opens a safe L1 case after five genuinely distinct failed attempts", async () => {
    const { createImpasseCase, recordAttempt } = await loadImpasse();
    let impasse = createImpasseCase("impasse:layout", "L1");

    for (let index = 1; index <= 5; index += 1) {
      impasse = recordAttempt(impasse, {
        id: `attempt:${index}`,
        hypothesis: `layout hypothesis ${index}`,
        intervention: `layout intervention ${index}`,
        evidence: [`screenshot:${index}`, `test:layout-${index}`],
        outcome: "failure",
        occurredAt: `2026-08-22T10:0${index}:00.000Z`,
      });
    }

    assert.equal(impasse.state, "OPEN");
    assert.equal(impasse.attempts.length, 5);
    assert.equal(impasse.stopDestructiveChanges, true);
    assert.equal(impasse.openReason, "distinct-attempt-limit");
  });

  it("opens a risky L2 case after two distinct failures", async () => {
    const { createImpasseCase, recordAttempt } = await loadImpasse();
    let impasse = createImpasseCase("impasse:contract", "L2");

    impasse = recordAttempt(impasse, {
      id: "attempt:1",
      hypothesis: "consumer still uses contract v1",
      intervention: "run compatibility adapter",
      evidence: ["contract-test:failed"],
      outcome: "failure",
      occurredAt: "2026-08-22T10:01:00.000Z",
    });
    impasse = recordAttempt(impasse, {
      id: "attempt:2",
      hypothesis: "schema generator emitted stale output",
      intervention: "regenerate contract and rerun consumers",
      evidence: ["consumer-test:failed"],
      outcome: "failure",
      occurredAt: "2026-08-22T10:02:00.000Z",
    });

    assert.equal(impasse.state, "OPEN");
  });

  it("detects an identical strategy instead of counting it as distinct work", async () => {
    const { createImpasseCase, recordAttempt } = await loadImpasse();
    let impasse = createImpasseCase("impasse:loop", "L1");
    const attempt = {
      id: "attempt:1",
      hypothesis: "rounded button padding causes overlap",
      intervention: "reduce horizontal padding to 8px",
      evidence: ["screenshot:overlap"],
      outcome: "failure" as const,
      occurredAt: "2026-08-22T10:01:00.000Z",
    };

    impasse = recordAttempt(impasse, attempt);
    impasse = recordAttempt(impasse, {
      ...attempt,
      id: "attempt:2",
      occurredAt: "2026-08-22T10:02:00.000Z",
    });

    assert.equal(impasse.state, "OPEN");
    assert.equal(impasse.openReason, "repeated-strategy");
    assert.equal(impasse.attempts.length, 1);
  });

  it("requires evidence and a concrete framework proposal before human review", async () => {
    const { createImpasseCase, requestHumanReview } = await loadImpasse();
    const impasse = createImpasseCase("impasse:empty", "L1");

    assert.throws(
      () =>
        requestHumanReview(impasse, {
          suspectedRuleId: "design.button-radius",
          explanation: "The global radius conflicts with dense controls.",
          proposedChange: "Allow compact controls to use a smaller radius.",
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "NOT_READY");
        return true;
      },
    );
  });

  it("enters half-open only after explicit human approval and revalidates", async () => {
    const {
      applyHumanDecision,
      createImpasseCase,
      recordAttempt,
      recordRevalidation,
      requestHumanReview,
    } = await loadImpasse();
    let impasse = createImpasseCase("impasse:design-rule", "L3");
    impasse = recordAttempt(impasse, {
      id: "attempt:1",
      hypothesis: "component implementation ignores container width",
      intervention: "add container-aware sizing",
      evidence: ["visual-test:failed"],
      outcome: "failure",
      occurredAt: "2026-08-22T10:01:00.000Z",
    });
    impasse = recordAttempt(impasse, {
      id: "attempt:2",
      hypothesis: "framework radius rule is incompatible with compact controls",
      intervention: "test a scoped radius override in an isolated fixture",
      evidence: ["fixture:passes-with-override", "baseline:still-fails"],
      outcome: "failure",
      occurredAt: "2026-08-22T10:02:00.000Z",
    });
    impasse = requestHumanReview(impasse, {
      suspectedRuleId: "design.button-radius",
      explanation: "Two distinct fixes failed; isolated evidence implicates the rule.",
      proposedChange: "Introduce a documented compact-control exception.",
    });

    assert.equal(impasse.state, "HUMAN_REVIEW");
    assert.throws(
      () =>
        applyHumanDecision(impasse, {
          approved: true,
          decidedBy: "agent:orchestrator",
          decidedAt: "2026-08-22T10:03:00.000Z",
          decisionRecord: "ADR-0042",
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "APPROVAL_REQUIRED");
        return true;
      },
    );
    assert.throws(() =>
      applyHumanDecision(impasse, {
        approved: false,
        decidedBy: "human:owner",
        decidedAt: "2026-08-22T10:03:00.000Z",
      }),
    );

    impasse = applyHumanDecision(impasse, {
      approved: true,
      decidedBy: "human:owner",
      decidedAt: "2026-08-22T10:03:00.000Z",
      decisionRecord: "ADR-0042",
    });
    assert.equal(impasse.state, "HALF_OPEN");

    impasse = recordRevalidation(impasse, {
      passed: true,
      evidence: ["visual-regression:pass", "design-system:pass"],
      occurredAt: "2026-08-22T10:04:00.000Z",
      updatedArtifacts: ["ADR-0042", "policy:design", "PROJECT_MAP.md"],
    });
    assert.equal(impasse.state, "RESOLVED");
  });
});
