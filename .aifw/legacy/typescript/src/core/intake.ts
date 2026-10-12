import { createHash } from "node:crypto";

import type { DataClassification, ProjectType } from "./config.ts";
import { AifwError } from "./errors.ts";

export type ApprovalPolicy = "approval-required" | "workflow-approved";

export interface ProjectAutonomy {
  localGit: boolean;
  remoteGit: ApprovalPolicy;
  previewDeploy: boolean;
  productionDeploy: ApprovalPolicy;
}

export interface CharterUnknown {
  id: string;
  description: string;
  blocking: boolean;
}

export interface TechnicalPreference {
  mode: "agent-recommend" | "specified";
  values?: string[];
}

export interface ProjectCharter {
  id: string;
  version: "0.1.0";
  projectType: ProjectType;
  problem: string;
  audiences: string[];
  outcomes: string[];
  scope: {
    in: string[];
    out: string[];
  };
  constraints: string[];
  dataClassification?: DataClassification;
  autonomy?: ProjectAutonomy;
  technicalPreference: TechnicalPreference;
  unknowns: CharterUnknown[];
  state: "draft" | "approved";
  approval?: {
    approvedBy: string;
    approvedAt: string;
    contentDigest: string;
  };
}

export interface CharterDraftInput {
  id: string;
  projectType: ProjectType;
  problem: string;
  audiences?: string[];
  outcomes?: string[];
  scope?: { in: string[]; out: string[] };
  constraints?: string[];
  dataClassification?: DataClassification;
  autonomy?: ProjectAutonomy;
  technicalPreference?: TechnicalPreference;
  unknowns?: CharterUnknown[];
}

export interface IntakeQuestion {
  field:
    | "problem"
    | "audiences"
    | "outcomes"
    | "scope.in"
    | "scope.out"
    | "dataClassification"
    | "autonomy";
  prompt: string;
}

export interface CharterAssessment {
  ready: boolean;
  questions: IntakeQuestion[];
  blockingUnknownIds: string[];
}

const questionPrompts: Record<IntakeQuestion["field"], string> = {
  problem: "Qual problema este projeto precisa resolver?",
  audiences: "Quem usará ou será afetado pelo resultado?",
  outcomes: "Como reconheceremos que o projeto teve sucesso?",
  "scope.in": "O que precisa fazer parte da primeira entrega?",
  "scope.out": "O que explicitamente não faz parte desta entrega?",
  dataClassification: "Que classificação possuem os dados envolvidos?",
  autonomy: "Quais ações o agente pode executar sem nova aprovação?",
};

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, stableValue(nested)]),
    );
  }
  return value;
}

function charterDigest(charter: ProjectCharter): string {
  const canonical = {
    ...charter,
    state: "approved",
    approval: undefined,
  };
  return createHash("sha256")
    .update(JSON.stringify(stableValue(canonical)))
    .digest("hex");
}

export function createCharterDraft(input: CharterDraftInput): ProjectCharter {
  return {
    id: input.id,
    version: "0.1.0",
    projectType: input.projectType,
    problem: input.problem.trim(),
    audiences: structuredClone(input.audiences ?? []),
    outcomes: structuredClone(input.outcomes ?? []),
    scope: structuredClone(input.scope ?? { in: [], out: [] }),
    constraints: structuredClone(input.constraints ?? []),
    ...(input.dataClassification === undefined
      ? {}
      : { dataClassification: input.dataClassification }),
    ...(input.autonomy === undefined
      ? {}
      : { autonomy: structuredClone(input.autonomy) }),
    technicalPreference: structuredClone(
      input.technicalPreference ?? { mode: "agent-recommend" },
    ),
    unknowns: structuredClone(input.unknowns ?? []),
    state: "draft",
  };
}

export function assessCharter(charter: ProjectCharter): CharterAssessment {
  const missing: IntakeQuestion["field"][] = [];
  if (charter.problem.trim() === "") missing.push("problem");
  if (charter.audiences.length === 0) missing.push("audiences");
  if (charter.outcomes.length === 0) missing.push("outcomes");
  if (charter.scope.in.length === 0) missing.push("scope.in");
  if (charter.scope.out.length === 0) missing.push("scope.out");
  if (charter.dataClassification === undefined) {
    missing.push("dataClassification");
  }
  if (charter.autonomy === undefined) missing.push("autonomy");

  const blockingUnknownIds = charter.unknowns
    .filter((unknown) => unknown.blocking)
    .map((unknown) => unknown.id)
    .sort();

  return {
    ready: missing.length === 0 && blockingUnknownIds.length === 0,
    questions: missing.map((field) => ({
      field,
      prompt: questionPrompts[field],
    })),
    blockingUnknownIds,
  };
}

export function approveCharter(
  charter: ProjectCharter,
  approval: { approvedBy: string; approvedAt: string },
): ProjectCharter {
  if (
    !approval.approvedBy.startsWith("human:") ||
    Number.isNaN(new Date(approval.approvedAt).valueOf())
  ) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "Project Charter approval requires a human identity and valid timestamp.",
      ["approvedBy", "approvedAt"],
    );
  }
  const assessment = assessCharter(charter);
  if (!assessment.ready) {
    const missing = assessment.questions.map((question) => question.field);
    throw new AifwError(
      "NOT_READY",
      `Project Charter is not ready: ${[
        ...missing,
        ...assessment.blockingUnknownIds,
      ].join(", ")}`,
      [...missing, ...assessment.blockingUnknownIds],
    );
  }

  return {
    ...structuredClone(charter),
    state: "approved",
    approval: {
      approvedBy: approval.approvedBy,
      approvedAt: approval.approvedAt,
      contentDigest: charterDigest(charter),
    },
  };
}
