import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

type HandoffModule = typeof import("../src/core/codex-handoff.ts");

async function loadHandoff(): Promise<HandoffModule> {
  try {
    return await import("../src/core/codex-handoff.ts");
  } catch (error) {
    assert.fail(`Codex handoff module must be implemented: ${String(error)}`);
  }
}

function input() {
  return {
    project: { id: "northstar", name: "Northstar" },
    objective: "Corrigir o fluxo de pagamentos sem enfraquecer o framework.",
    reason: "Pi exhausted the distinct-attempt budget.",
    impact: "L3" as const,
    suggestedRoute: "BRAIN" as const,
    blocker: {
      summary: "O contrato atual conflita com o requisito aprovado.",
      exactError: "Authorization failed with token sk-test-secret-value",
      suspectedCause: "framework-constraint-conflict",
    },
    attempts: [
      {
        hypothesis: "The adapter maps the wrong contract.",
        intervention: "Changed only the adapter mapping.",
        result: "The contract test still failed.",
        evidence: ["tests/payment-contract.test.ts"],
      },
    ],
    relevantFiles: ["src/payments/adapter.ts"],
    authoritativeArtifacts: ["CONSTITUTION.md", "docs/adr/ADR-0042.md"],
    constraints: ["Do not weaken a core invariant."],
    verification: ["npm test", "aifw validate --level L3"],
    requestedOutcome: "Diagnose the conflict and propose the smallest compliant correction.",
    generatedAt: "2026-08-23T12:00:00.000Z",
  };
}

describe("Codex fallback handoff", () => {
  it("renders a self-contained, evidence-oriented handoff and redacts secrets", async () => {
    const { buildCodexHandoff } = await loadHandoff();
    const document = buildCodexHandoff(input());

    assert.match(document, /# AIFW Codex Handoff/u);
    assert.match(document, /## Objective/u);
    assert.match(document, /## Exact blocker/u);
    assert.match(document, /## Distinct attempts/u);
    assert.match(document, /## Sources of truth/u);
    assert.match(document, /## Definition of done/u);
    assert.match(document, /docs\/adr\/ADR-0042\.md/u);
    assert.doesNotMatch(document, /sk-test-secret-value/u);
    assert.match(document, /\[REDACTED\]/u);
  });

  it("writes only inside the project and returns a portable relative path", async () => {
    const { writeCodexHandoff } = await loadHandoff();
    const root = await mkdtemp(path.join(tmpdir(), "aifw-handoff-"));

    const result = await writeCodexHandoff(root, input());

    assert.match(result.relativePath, /^\.aifw\/handoffs\/codex-/u);
    assert.equal(path.isAbsolute(result.relativePath), false);
    assert.match(await readFile(result.absolutePath, "utf8"), /Northstar/u);
  });

  it("rejects an output path that escapes the project", async () => {
    const { writeCodexHandoff } = await loadHandoff();
    const root = await mkdtemp(path.join(tmpdir(), "aifw-handoff-boundary-"));

    await assert.rejects(
      () => writeCodexHandoff(root, input(), "../outside.md"),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "PERMISSION_DENIED");
        return true;
      },
    );
  });
});
