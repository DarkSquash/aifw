import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { parseDocument, stringify } from "yaml";

import { AifwError } from "./errors.ts";
import {
  evaluateRoutingActivation,
  type ModelAliases,
  type RoutingEvaluation,
} from "./routing.ts";

export interface PersistedRoutingPolicy {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "RoutingPolicy";
  enabled: boolean;
  mode: "recommendation-only" | "automatic";
  aliases: ModelAliases;
  targets: Record<keyof ModelAliases, { provider: string; model: string }>;
  activation: {
    minimumCases: number;
    minimumPassRate: number;
    criticalFailures: 0;
    humanApprovalRequired: true;
  };
  approval?: {
    approvedBy: string;
    record: string;
    activatedAt: string;
    report: RoutingEvaluation;
  };
}

function parseRoutingPolicy(source: string): PersistedRoutingPolicy {
  const document = parseDocument(source, {
    schema: "core",
    strict: true,
    uniqueKeys: true,
  });
  if (document.errors.length > 0) {
    throw new AifwError(
      "YAML_INVALID",
      `.aifw/routing.yaml is invalid: ${document.errors.map((error) => error.message).join("; ")}`,
    );
  }
  const value = document.toJS() as Partial<PersistedRoutingPolicy> | null;
  if (
    value === null ||
    value.apiVersion !== "aifw.dev/v1alpha1" ||
    value.kind !== "RoutingPolicy" ||
    typeof value.enabled !== "boolean" ||
    (value.mode !== "recommendation-only" && value.mode !== "automatic") ||
    typeof value.aliases?.FAST !== "string" ||
    typeof value.aliases?.WORK !== "string" ||
    typeof value.aliases?.BRAIN !== "string" ||
    typeof value.targets?.FAST?.provider !== "string" ||
    typeof value.targets.FAST.model !== "string" ||
    typeof value.targets?.WORK?.provider !== "string" ||
    typeof value.targets.WORK.model !== "string" ||
    typeof value.targets?.BRAIN?.provider !== "string" ||
    typeof value.targets.BRAIN.model !== "string" ||
    typeof value.activation?.minimumCases !== "number" ||
    typeof value.activation?.minimumPassRate !== "number"
  ) {
    throw new AifwError(
      "MANIFEST_INVALID",
      ".aifw/routing.yaml does not match the RoutingPolicy contract.",
    );
  }
  return structuredClone(value) as PersistedRoutingPolicy;
}

export async function loadWorkspaceRouting(
  root: string,
): Promise<PersistedRoutingPolicy> {
  return loadRoutingPolicyFile(path.join(root, ".aifw", "routing.yaml"));
}

export async function loadRoutingPolicyFile(
  policyPath: string,
): Promise<PersistedRoutingPolicy> {
  return parseRoutingPolicy(await readFile(policyPath, "utf8"));
}

export async function activateWorkspaceRouting(
  root: string,
  input: {
    humanApproved: boolean;
    approvedBy: string;
    approvalRecord: string;
    report: RoutingEvaluation;
    activatedAt?: string;
  },
): Promise<PersistedRoutingPolicy> {
  if (
    !Number.isInteger(input.report.cases) ||
    input.report.cases < 0 ||
    !Number.isFinite(input.report.passRate) ||
    input.report.passRate < 0 ||
    input.report.passRate > 1 ||
    !Number.isInteger(input.report.criticalFailures) ||
    input.report.criticalFailures < 0
  ) {
    throw new AifwError(
      "MANIFEST_INVALID",
      "Routing evaluation metrics must be finite, non-negative and internally valid.",
      ["cases", "passRate", "criticalFailures"],
    );
  }
  const policy = await loadWorkspaceRouting(root);
  const activation = evaluateRoutingActivation({
    humanApproved: input.humanApproved,
    report: input.report,
    minimumCases: policy.activation.minimumCases,
    minimumPassRate: policy.activation.minimumPassRate,
  });
  if (
    !activation.enabled ||
    !input.approvedBy.startsWith("human:") ||
    input.approvalRecord.trim().length === 0
  ) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "Automatic routing cannot be activated until every evaluation and approval condition passes.",
      [
        ...activation.blockers,
        ...(!input.approvedBy.startsWith("human:") ? ["human-approved-by"] : []),
        ...(input.approvalRecord.trim().length === 0 ? ["approval-record"] : []),
      ],
    );
  }

  const activated: PersistedRoutingPolicy = {
    ...policy,
    enabled: true,
    mode: "automatic",
    approval: {
      approvedBy: input.approvedBy,
      record: input.approvalRecord,
      activatedAt: input.activatedAt ?? new Date().toISOString(),
      report: structuredClone(input.report),
    },
  };
  await writeFile(
    path.join(root, ".aifw", "routing.yaml"),
    stringify(activated, { lineWidth: 0, sortMapEntries: false }),
    "utf8",
  );
  return activated;
}
