import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { parseDocument, stringify } from "yaml";

import { AifwError } from "./errors.ts";
import {
  assessBrownfieldAdoption,
  type BrownfieldAdoptionAssessment,
} from "./brownfield.ts";
import {
  approveCharter,
  assessCharter,
  type CharterAssessment,
  type ProjectCharter,
} from "./intake.ts";
import { assessWorkspacePrincipleReview } from "./principle-catalog.ts";
import { buildWorkspaceMap, updateWorkspacePurpose } from "./workspace.ts";

export interface EngineeringPrincipleIntakeAssessment {
  id: "engineering-principles";
  owner: "agent";
  blockingHumanApproval: false;
  status: "pending" | "current" | "stale" | "invalid";
  artifact: ".aifw/reviews/engineering-principles.json";
  reason: string;
  nextAction?: string;
}

export type AgentIntakeAssessment =
  | EngineeringPrincipleIntakeAssessment
  | BrownfieldAdoptionAssessment;

export interface WorkspaceIntakeAssessment extends CharterAssessment {
  complete: boolean;
  agentAssessments: AgentIntakeAssessment[];
}

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

export function parseCharter(source: string, label = ".aifw/charter.yaml"): ProjectCharter {
  const document = parseDocument(source, {
    schema: "core",
    strict: true,
    uniqueKeys: true,
  });
  if (document.errors.length > 0) {
    throw new AifwError(
      "YAML_INVALID",
      `${label} is invalid: ${document.errors.map((error) => error.message).join("; ")}`,
    );
  }
  const value = document.toJS() as Partial<ProjectCharter> | null;
  const valid =
    value !== null &&
    typeof value.id === "string" &&
    value.version === "0.1.0" &&
    (value.projectType === "new" || value.projectType === "existing") &&
    typeof value.problem === "string" &&
    strings(value.audiences) &&
    strings(value.outcomes) &&
    strings(value.scope?.in) &&
    strings(value.scope?.out) &&
    strings(value.constraints) &&
    (value.technicalPreference?.mode === "agent-recommend" ||
      value.technicalPreference?.mode === "specified") &&
    Array.isArray(value.unknowns) &&
    (value.state === "draft" || value.state === "approved");

  if (!valid) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `${label} does not match the ProjectCharter contract.`,
    );
  }
  return structuredClone(value) as ProjectCharter;
}

export async function loadWorkspaceCharter(root: string): Promise<ProjectCharter> {
  return parseCharter(
    await readFile(path.join(root, ".aifw", "charter.yaml"), "utf8"),
  );
}

export async function assessWorkspaceCharter(root: string): Promise<CharterAssessment> {
  return assessCharter(await loadWorkspaceCharter(root));
}

export async function assessWorkspaceIntake(root: string): Promise<WorkspaceIntakeAssessment> {
  const [workspaceCharter, principleReview] = await Promise.all([
    loadWorkspaceCharter(root),
    assessWorkspacePrincipleReview(root),
  ]);
  const charter = assessCharter(workspaceCharter);
  const principleAssessment: EngineeringPrincipleIntakeAssessment = {
    id: "engineering-principles",
    owner: "agent",
    blockingHumanApproval: false,
    status: principleReview.status,
    artifact: ".aifw/reviews/engineering-principles.json",
    reason: principleReview.reason,
    ...(principleReview.status === "current"
      ? {}
      : {
          nextAction:
            "aifw principle review --signals <signals-derived-by-agent> --write",
        }),
  };
  const agentAssessments: AgentIntakeAssessment[] = [principleAssessment];
  if (workspaceCharter.projectType === "existing") {
    agentAssessments.push(await assessBrownfieldAdoption(root));
  }
  return {
    ...charter,
    complete:
      charter.ready &&
      agentAssessments.every((assessment) => assessment.status === "current"),
    agentAssessments,
  };
}

export async function approveWorkspaceCharter(
  root: string,
  approval: { approvedBy: string; approvedAt: string },
): Promise<{ charter: ProjectCharter; projectMapDigest: string }> {
  const charterPath = path.join(root, ".aifw", "charter.yaml");
  const charter = approveCharter(await loadWorkspaceCharter(root), approval);
  const charterSource = stringify(charter, { lineWidth: 0, sortMapEntries: false });

  await writeFile(charterPath, charterSource, "utf8");
  await updateWorkspacePurpose(root, charter.problem);
  const projectMap = await buildWorkspaceMap(root, { write: true });

  return { charter, projectMapDigest: projectMap.digest };
}
