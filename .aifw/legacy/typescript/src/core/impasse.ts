import { createHash } from "node:crypto";
import type { ChangeLevel } from "./change.ts";
import { AifwError } from "./errors.ts";

export type ImpasseState =
  | "NORMAL"
  | "SUSPECTED"
  | "OPEN"
  | "HUMAN_REVIEW"
  | "HALF_OPEN"
  | "RESOLVED";

export type AttemptOutcome = "success" | "failure" | "inconclusive";

export interface CorrectionAttempt {
  id: string;
  hypothesis: string;
  intervention: string;
  evidence: string[];
  outcome: AttemptOutcome;
  occurredAt: string;
}

export interface FrameworkChangeProposal {
  suspectedRuleId: string;
  explanation: string;
  proposedChange: string;
}

export interface HumanDecision {
  approved: boolean;
  decidedBy: string;
  decidedAt: string;
  decisionRecord?: string;
}

export interface RevalidationResult {
  passed: boolean;
  evidence: string[];
  occurredAt: string;
  updatedArtifacts: string[];
}

export interface ImpasseCase {
  id: string;
  impact: ChangeLevel;
  state: ImpasseState;
  attempts: CorrectionAttempt[];
  attemptFingerprints: string[];
  stopDestructiveChanges: boolean;
  openReason?: "distinct-attempt-limit" | "repeated-strategy";
  proposal?: FrameworkChangeProposal;
  humanDecision?: HumanDecision;
  revalidation?: RevalidationResult;
}

function textIsPresent(value: string): boolean {
  return value.trim().length > 0;
}

function normalize(value: string): string {
  return value.trim().toLocaleLowerCase("en-US").replace(/\s+/gu, " ");
}

function attemptFingerprint(attempt: CorrectionAttempt): string {
  return createHash("sha256")
    .update(`${normalize(attempt.hypothesis)}\n${normalize(attempt.intervention)}`)
    .digest("hex");
}

function distinctFailureLimit(level: ChangeLevel): number {
  return level === "L0" || level === "L1" ? 5 : 2;
}

function assertAttempt(attempt: CorrectionAttempt): void {
  const missing = [
    ["id", attempt.id],
    ["hypothesis", attempt.hypothesis],
    ["intervention", attempt.intervention],
    ["occurredAt", attempt.occurredAt],
  ]
    .filter(([, value]) => !textIsPresent(value ?? ""))
    .map(([field]) => field ?? "unknown");

  if (missing.length > 0 || attempt.evidence.length === 0) {
    throw new AifwError(
      "NOT_READY",
      "A correction attempt needs a hypothesis, intervention and evidence.",
      [...missing, ...(attempt.evidence.length === 0 ? ["evidence"] : [])],
    );
  }
}

export function createImpasseCase(
  id: string,
  impact: ChangeLevel,
): ImpasseCase {
  if (!textIsPresent(id)) {
    throw new AifwError("NOT_READY", "An impasse case needs a stable id.");
  }

  return {
    id,
    impact,
    state: "NORMAL",
    attempts: [],
    attemptFingerprints: [],
    stopDestructiveChanges: false,
  };
}

export function recordAttempt(
  impasse: ImpasseCase,
  attempt: CorrectionAttempt,
): ImpasseCase {
  if (impasse.state !== "NORMAL" && impasse.state !== "SUSPECTED") {
    throw new AifwError(
      "IMPASSE_OPEN",
      `Attempts are frozen while the impasse is ${impasse.state}.`,
    );
  }
  assertAttempt(attempt);

  const fingerprint = attemptFingerprint(attempt);
  if (impasse.attemptFingerprints.includes(fingerprint)) {
    return {
      ...impasse,
      state: "OPEN",
      openReason: "repeated-strategy",
      stopDestructiveChanges: true,
    };
  }

  const attempts = [...impasse.attempts, structuredClone(attempt)];
  const attemptFingerprints = [...impasse.attemptFingerprints, fingerprint];

  if (attempt.outcome === "success") {
    return {
      ...impasse,
      attempts,
      attemptFingerprints,
      state: "RESOLVED",
      stopDestructiveChanges: false,
    };
  }

  const failures = attempts.filter((item) => item.outcome === "failure").length;
  const exhausted = failures >= distinctFailureLimit(impasse.impact);

  return {
    ...impasse,
    attempts,
    attemptFingerprints,
    state: exhausted ? "OPEN" : "SUSPECTED",
    ...(exhausted ? { openReason: "distinct-attempt-limit" as const } : {}),
    stopDestructiveChanges: true,
  };
}

export function requestHumanReview(
  impasse: ImpasseCase,
  proposal: FrameworkChangeProposal,
): ImpasseCase {
  const proposalReady =
    textIsPresent(proposal.suspectedRuleId) &&
    textIsPresent(proposal.explanation) &&
    textIsPresent(proposal.proposedChange);
  const hasEvidence = impasse.attempts.some((attempt) => attempt.evidence.length > 0);

  if (impasse.state !== "OPEN" || !proposalReady || !hasEvidence) {
    throw new AifwError(
      "NOT_READY",
      "Human review requires an open impasse, evidence and a concrete framework proposal.",
      [
        ...(impasse.state !== "OPEN" ? ["impasse-not-open"] : []),
        ...(!hasEvidence ? ["evidence"] : []),
        ...(!proposalReady ? ["proposal"] : []),
      ],
    );
  }

  return {
    ...impasse,
    state: "HUMAN_REVIEW",
    proposal: structuredClone(proposal),
    stopDestructiveChanges: true,
  };
}

export function applyHumanDecision(
  impasse: ImpasseCase,
  decision: HumanDecision,
): ImpasseCase {
  if (impasse.state !== "HUMAN_REVIEW") {
    throw new AifwError(
      "NOT_READY",
      "A human decision can only be applied during HUMAN_REVIEW.",
    );
  }
  if (!decision.approved) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "The proposed framework change was not approved; the impasse remains open.",
    );
  }
  if (
    !decision.decidedBy.startsWith("human:") ||
    Number.isNaN(new Date(decision.decidedAt).valueOf()) ||
    !textIsPresent(decision.decisionRecord ?? "")
  ) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "Approval must identify the human, timestamp and persisted decision record.",
    );
  }

  return {
    ...impasse,
    state: "HALF_OPEN",
    humanDecision: structuredClone(decision),
    stopDestructiveChanges: true,
  };
}

export function recordRevalidation(
  impasse: ImpasseCase,
  result: RevalidationResult,
): ImpasseCase {
  if (impasse.state !== "HALF_OPEN") {
    throw new AifwError(
      "NOT_READY",
      "Revalidation is only valid after an approved framework change.",
    );
  }
  if (result.evidence.length === 0 || result.updatedArtifacts.length === 0) {
    throw new AifwError(
      "NOT_READY",
      "Revalidation requires test evidence and updated persisted artifacts.",
    );
  }

  const updated = structuredClone(impasse);
  if (result.passed) delete updated.openReason;

  return {
    ...updated,
    state: result.passed ? "RESOLVED" : "OPEN",
    revalidation: structuredClone(result),
    stopDestructiveChanges: !result.passed,
  };
}

export function mutationAllowed(
  impasse: ImpasseCase,
  destructive: boolean,
): boolean {
  if (impasse.state === "OPEN" || impasse.state === "HUMAN_REVIEW") return false;
  if (destructive && impasse.stopDestructiveChanges) return false;
  return impasse.state !== "RESOLVED" || !destructive || !impasse.stopDestructiveChanges;
}
