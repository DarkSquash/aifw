import type { ChangeLevel } from "./change.ts";

export interface GateResult {
  gateId: string;
  enforcement: "hard" | "audit" | "human";
  status: "pass" | "fail" | "warning" | "not-run";
  summary: string;
  evidence: string[];
}

export interface GateEvaluationInput {
  change: {
    level: ChangeLevel;
    humanApproval: "none" | "conditional" | "required";
  };
  requiredGateIds: string[];
  results: GateResult[];
  approval?: {
    approvedBy: string;
    approvalDigest: string;
  };
}

export interface GateEvaluation {
  status: "pass" | "warning" | "blocked";
  blockers: GateResult[];
  warnings: GateResult[];
  passed: GateResult[];
}

export function evaluateQualityGates(
  input: GateEvaluationInput,
): GateEvaluation {
  const byId = new Map(input.results.map((result) => [result.gateId, result]));
  const results = [...input.results];

  for (const requiredGateId of [...input.requiredGateIds].sort()) {
    if (!byId.has(requiredGateId)) {
      results.push({
        gateId: requiredGateId,
        enforcement: "hard",
        status: "not-run",
        summary: "Required gate did not run",
        evidence: [],
      });
    }
  }

  const validApproval =
    input.approval !== undefined &&
    input.approval.approvedBy.startsWith("human:") &&
    /^[a-f0-9]{64}$/u.test(input.approval.approvalDigest);

  if (input.change.humanApproval === "required" && !validApproval) {
    results.push({
      gateId: "human-approval",
      enforcement: "human",
      status: "not-run",
      summary: `Valid human approval is required for ${input.change.level}`,
      evidence: [],
    });
  }

  const blockers = results
    .filter(
      (result) =>
        (result.enforcement === "hard" || result.enforcement === "human") &&
        (result.status === "fail" || result.status === "not-run"),
    )
    .sort((left, right) => left.gateId.localeCompare(right.gateId));
  const warnings = results
    .filter(
      (result) =>
        result.enforcement === "audit" && result.status !== "pass",
    )
    .sort((left, right) => left.gateId.localeCompare(right.gateId));
  const passed = results
    .filter((result) => result.status === "pass")
    .sort((left, right) => left.gateId.localeCompare(right.gateId));

  return {
    status:
      blockers.length > 0
        ? "blocked"
        : warnings.length > 0
          ? "warning"
          : "pass",
    blockers,
    warnings,
    passed,
  };
}
