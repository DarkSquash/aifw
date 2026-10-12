import assert from "node:assert/strict";
import { describe, it } from "node:test";

type IntakeModule = typeof import("../src/core/intake.ts");

async function loadIntake(): Promise<IntakeModule> {
  try {
    return await import("../src/core/intake.ts");
  } catch (error) {
    assert.fail(`intake module must be implemented: ${String(error)}`);
  }
}

describe("adaptive project intake", () => {
  it("asks only for missing human decisions and never requires a stack", async () => {
    const { assessCharter, createCharterDraft } = await loadIntake();
    const draft = createCharterDraft({
      id: "project:northstar",
      projectType: "new",
      problem: "Centralize customer operations",
    });

    const assessment = assessCharter(draft);

    assert.equal(assessment.ready, false);
    assert.deepEqual(
      assessment.questions.map((question) => question.field),
      [
        "audiences",
        "outcomes",
        "scope.in",
        "scope.out",
        "dataClassification",
        "autonomy",
      ],
    );
    assert.equal(
      assessment.questions.some((question) =>
        /stack|framework|database/i.test(question.field),
      ),
      false,
    );
  });

  it("treats agent recommendation as a valid technical preference", async () => {
    const { assessCharter, createCharterDraft } = await loadIntake();
    const draft = createCharterDraft({
      id: "project:northstar",
      projectType: "new",
      problem: "Centralize customer operations",
      audiences: ["sales operators"],
      outcomes: ["Operators can find a customer in under 10 seconds"],
      scope: { in: ["customer search"], out: ["billing"] },
      constraints: [],
      dataClassification: "internal",
      autonomy: {
        localGit: true,
        remoteGit: "approval-required",
        previewDeploy: true,
        productionDeploy: "approval-required",
      },
      technicalPreference: { mode: "agent-recommend" },
    });

    const assessment = assessCharter(draft);

    assert.equal(assessment.ready, true);
    assert.deepEqual(assessment.questions, []);
  });

  it("blocks approval while a required decision or blocking unknown remains", async () => {
    const { approveCharter, createCharterDraft } = await loadIntake();
    const draft = createCharterDraft({
      id: "project:northstar",
      projectType: "new",
      problem: "Centralize customer operations",
      unknowns: [
        { id: "unknown:legal", description: "Retention period", blocking: true },
      ],
    });

    assert.throws(
      () =>
        approveCharter(draft, {
          approvedBy: "human:owner",
          approvedAt: "2026-08-22T10:00:00.000Z",
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "NOT_READY");
        assert.match(String(error), /audiences|unknown:legal/);
        return true;
      },
    );
  });

  it("approves a ready charter with a deterministic content digest", async () => {
    const { approveCharter, createCharterDraft } = await loadIntake();
    const input = {
      id: "project:northstar",
      projectType: "existing" as const,
      problem: "Reduce customer search latency",
      audiences: ["sales operators"],
      outcomes: ["p95 search latency below 300ms"],
      scope: { in: ["search API"], out: ["billing"] },
      constraints: ["preserve public API"],
      dataClassification: "internal" as const,
      autonomy: {
        localGit: true,
        remoteGit: "approval-required" as const,
        previewDeploy: true,
        productionDeploy: "approval-required" as const,
      },
      technicalPreference: { mode: "agent-recommend" as const },
    };

    const first = approveCharter(createCharterDraft(input), {
      approvedBy: "human:owner",
      approvedAt: "2026-08-22T10:00:00.000Z",
    });
    const second = approveCharter(createCharterDraft(input), {
      approvedBy: "human:owner",
      approvedAt: "2026-08-22T10:00:00.000Z",
    });

    assert.equal(first.state, "approved");
    assert.equal(first.approval?.contentDigest, second.approval?.contentDigest);
    assert.match(first.approval?.contentDigest ?? "", /^[a-f0-9]{64}$/);
  });

  it("rejects an agent identity as the human approver", async () => {
    const { approveCharter, createCharterDraft } = await loadIntake();
    const charter = createCharterDraft({
      id: "project:northstar",
      projectType: "new",
      problem: "Centralize customer operations",
      audiences: ["support team"],
      outcomes: ["faster resolution"],
      scope: { in: ["customer records"], out: ["billing"] },
      dataClassification: "internal",
      autonomy: {
        localGit: true,
        remoteGit: "approval-required",
        previewDeploy: true,
        productionDeploy: "approval-required",
      },
    });

    assert.throws(
      () =>
        approveCharter(charter, {
          approvedBy: "agent:orchestrator",
          approvedAt: "2026-08-22T10:00:00.000Z",
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "APPROVAL_REQUIRED");
        return true;
      },
    );
  });
});
