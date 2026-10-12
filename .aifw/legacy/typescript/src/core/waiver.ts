import { AifwError } from "./errors.ts";

export interface WaiverInput {
  id: string;
  ruleId: string;
  scope: string[];
  reason: string;
  requestedBy: string;
  approvedBy: string;
  approvedAt: string;
  expiresAt: string;
  checkpoint: string;
}

export interface Waiver extends WaiverInput {
  status: "active";
}

export function createWaiver(
  input: WaiverInput,
  options: { nonWaivableRuleIds?: readonly string[] } = {},
): Waiver {
  if (!input.approvedBy.startsWith("human:")) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "A waiver requires an explicit human approver.",
      [input.approvedBy],
    );
  }
  if (options.nonWaivableRuleIds?.includes(input.ruleId) === true) {
    throw new AifwError(
      "POLICY_CONFLICT",
      `Rule ${input.ruleId} is non-waivable`,
      [input.ruleId],
    );
  }

  const approvedAt = new Date(input.approvedAt);
  const expiresAt = new Date(input.expiresAt);
  if (
    Number.isNaN(approvedAt.getTime()) ||
    Number.isNaN(expiresAt.getTime()) ||
    expiresAt.getTime() <= approvedAt.getTime()
  ) {
    throw new AifwError(
      "MANIFEST_INVALID",
      "Waiver expiry must be later than its approval",
      [input.approvedAt, input.expiresAt],
    );
  }
  if (input.scope.length === 0 || input.reason.trim() === "") {
    throw new AifwError(
      "MANIFEST_INVALID",
      "Waiver requires a non-empty scope and reason",
    );
  }

  return { ...structuredClone(input), status: "active" };
}

export function isWaiverActive(waiver: Waiver, now: Date): boolean {
  return now.getTime() < new Date(waiver.expiresAt).getTime();
}
