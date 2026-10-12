import { randomUUID } from "node:crypto";
import { access, cp, mkdir, readFile, realpath, rename, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";

import fg from "fast-glob";
import { parseDocument, stringify } from "yaml";

import type { ChangeLevel } from "./change.ts";
import { AifwError } from "./errors.ts";

export type SpecChangeStatus = "draft" | "active" | "ready" | "archived";

export interface SpecChangeRecord {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "SpecChange";
  metadata: {
    id: string;
    title: string;
    level: ChangeLevel;
    createdAt: string;
  };
  summary: string;
  status: SpecChangeStatus;
  approval?: {
    approvedBy: string;
    approvedAt: string;
    record: string;
  };
  archivedAt?: string;
}

export interface CreateSpecChangeInput {
  id: string;
  title: string;
  summary: string;
  level: ChangeLevel;
  createdAt: string;
}

export interface CreateSpecChangeResult {
  change: SpecChangeRecord;
  createdFiles: string[];
}

export interface SpecChangeListEntry {
  id: string;
  title: string;
  level: ChangeLevel;
  status: SpecChangeStatus;
  location: "active" | "archive";
  relativePath: string;
}

export interface RequirementScenario {
  id: string;
  given: string[];
  when: string[];
  then: string[];
}

export interface CapabilityRequirement {
  id: string;
  strength: "MUST" | "SHALL" | "SHOULD" | "MAY";
  statement: string;
  scenarios: RequirementScenario[];
}

export interface CapabilityDelta {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "CapabilityDelta";
  changeId: string;
  capability: string;
  title: string;
  purpose?: string;
  operations: {
    added: CapabilityRequirement[];
    modified: CapabilityRequirement[];
    removed: Array<{ id: string; reason: string }>;
  };
}

export interface CapabilitySpec {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "CapabilitySpec";
  capability: string;
  title: string;
  purpose: string;
  requirements: CapabilityRequirement[];
}

export interface ChangeTask {
  id: string;
  title: string;
  status: "pending" | "in-progress" | "blocked" | "done";
  dependsOn: string[];
  requirementIds: string[];
  paths: string[];
}

export interface ChangeTasks {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "ChangeTasks";
  changeId: string;
  tasks: ChangeTask[];
}

export type TraceArtifactType = "test" | "gate" | "evidence" | "adr" | "design";

export interface TraceArtifact {
  id: string;
  type: TraceArtifactType;
  path?: string;
  status: "planned" | "passed" | "failed" | "waived";
}

export interface TraceLink {
  from: string;
  relation: "verifiedBy" | "provedBy" | "designedBy" | "governedBy" | "checkedBy";
  to: string;
}

export interface ChangeTraceability {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "ChangeTraceability";
  changeId: string;
  artifacts: TraceArtifact[];
  links: TraceLink[];
}

export interface SpecFinding {
  code: string;
  severity: "error" | "warning";
  message: string;
  relatedIds: string[];
  locations: string[];
}

export interface SpecAnalysis {
  change: SpecChangeRecord;
  pass: boolean;
  findings: SpecFinding[];
  coverage: {
    requirements: { total: number; linkedToTask: number };
    scenarios: { total: number; verified: number };
    tasks: { total: number; completed: number };
  };
  graph: {
    nodes: Array<{ id: string; type: string; path?: string }>;
    links: Array<{ from: string; relation: string; to: string }>;
  };
}

export interface SpecValidation {
  change: SpecChangeRecord;
  pass: boolean;
  findings: SpecFinding[];
  capabilities: string[];
}

export interface SpecSyncPlan {
  changeId: string;
  pass: boolean;
  findings: SpecFinding[];
  changes: Array<{
    capability: string;
    action: "create" | "update";
    added: string[];
    modified: string[];
    removed: string[];
    outputPath: string;
  }>;
  outputs: Array<{ relativePath: string; spec: CapabilitySpec }>;
}

export interface ArchiveSpecChangeResult {
  changeId: string;
  archivePath: string;
  currentSpecs: string[];
  cleanupPending?: { path: string; reason: string };
}

function yaml(value: unknown): string {
  return stringify(value, { lineWidth: 0, sortMapEntries: false });
}

async function exists(filePath: string): Promise<boolean> {
  try {
    await access(filePath);
    return true;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

function assertChangeId(id: string): void {
  if (!/^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$/u.test(id)) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `Invalid change id: ${id}. Use a lowercase, project-safe slug.`,
      [id],
    );
  }
}

function outsideRoot(root: string, target: string): boolean {
  const relative = path.relative(root, target);
  return relative === "" || relative === ".." ||
    relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative);
}

async function inspectProjectFile(
  root: string,
  file: string,
): Promise<"valid" | "outside" | "missing"> {
  if (file.trim() === "") return "missing";
  const absolute = path.resolve(root, file);
  if (outsideRoot(root, absolute)) return "outside";
  try {
    const [realRoot, realFile] = await Promise.all([realpath(root), realpath(absolute)]);
    if (outsideRoot(realRoot, realFile)) return "outside";
    return (await stat(realFile)).isFile() ? "valid" : "missing";
  } catch (error) {
    if (["ENOENT", "ENOTDIR"].includes((error as NodeJS.ErrnoException).code ?? "")) return "missing";
    throw error;
  }
}

async function assertSpecApproval(root: string, change: SpecChangeRecord): Promise<void> {
  if (change.metadata.level !== "L3") return;
  const approval = change.approval;
  if (
    approval === undefined ||
    !/^human:\S+$/u.test(approval.approvedBy) ||
    Number.isNaN(new Date(approval.approvedAt).valueOf()) ||
    await inspectProjectFile(root, approval.record) !== "valid"
  ) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      `L3 spec change ${change.metadata.id} requires persisted human approval and an existing in-project approval record.`,
      [change.metadata.id],
    );
  }
}

function objectRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function enumString(value: unknown, allowed: readonly string[]): value is string {
  return typeof value === "string" && allowed.includes(value);
}

function parseChange(source: string, label: string): SpecChangeRecord {
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
  const value: unknown = document.toJS();
  const metadata = objectRecord(value) ? value["metadata"] : undefined;
  const approval = objectRecord(value) ? value["approval"] : undefined;
  const valid =
    objectRecord(value) &&
    value["apiVersion"] === "aifw.dev/v1alpha1" &&
    value["kind"] === "SpecChange" &&
    objectRecord(metadata) &&
    typeof metadata["id"] === "string" &&
    typeof metadata["title"] === "string" &&
    enumString(metadata["level"], ["L0", "L1", "L2", "L3"]) &&
    typeof metadata["createdAt"] === "string" &&
    typeof value["summary"] === "string" &&
    enumString(value["status"], ["draft", "active", "ready", "archived"]) &&
    (approval === undefined ||
      (objectRecord(approval) &&
        typeof approval["approvedBy"] === "string" &&
        typeof approval["approvedAt"] === "string" &&
        typeof approval["record"] === "string")) &&
    (value["archivedAt"] === undefined || typeof value["archivedAt"] === "string");
  if (!valid || !objectRecord(metadata) || typeof metadata["id"] !== "string") {
    throw new AifwError(
      "MANIFEST_INVALID",
      `${label} does not match the SpecChange contract.`,
    );
  }
  assertChangeId(metadata["id"]);
  return structuredClone(value) as unknown as SpecChangeRecord;
}

function parseYamlObject(source: string, label: string): Record<string, unknown> {
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
  const value: unknown = document.toJS();
  if (!objectRecord(value)) {
    throw new AifwError("MANIFEST_INVALID", `${label} must be a YAML object.`);
  }
  return value;
}

async function loadActiveChange(root: string, id: string): Promise<SpecChangeRecord> {
  assertChangeId(id);
  const relativePath = `.aifw/changes/active/${id}/change.yaml`;
  try {
    return parseChange(
      await readFile(path.join(root, ...relativePath.split("/")), "utf8"),
      relativePath,
    );
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      throw new AifwError("NOT_READY", `Active spec change not found: ${id}`, [id]);
    }
    throw error;
  }
}

function stringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((entry) => typeof entry === "string");
}

function validRequirement(value: unknown): value is CapabilityRequirement {
  if (!objectRecord(value)) return false;
  const scenarios = value["scenarios"];
  return (
    typeof value["id"] === "string" &&
    /^REQ-[A-Z0-9-]+$/u.test(value["id"]) &&
    enumString(value["strength"], ["MUST", "SHALL", "SHOULD", "MAY"]) &&
    typeof value["statement"] === "string" &&
    value["statement"].trim() !== "" &&
    Array.isArray(scenarios) &&
    scenarios.length > 0 &&
    scenarios.every((scenario: unknown) =>
      objectRecord(scenario) &&
      typeof scenario["id"] === "string" &&
      /^SCN-[A-Z0-9-]+$/u.test(scenario["id"]) &&
      stringArray(scenario["given"]) &&
      scenario["given"].length > 0 &&
      stringArray(scenario["when"]) &&
      scenario["when"].length > 0 &&
      stringArray(scenario["then"]) &&
      scenario["then"].length > 0
    )
  );
}

function parseDelta(source: string, label: string): CapabilityDelta {
  const value = parseYamlObject(source, label);
  const operations = value["operations"];
  const valid =
    value["apiVersion"] === "aifw.dev/v1alpha1" &&
    value["kind"] === "CapabilityDelta" &&
    typeof value["changeId"] === "string" &&
    typeof value["capability"] === "string" &&
    /^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$/u.test(value["capability"]) &&
    typeof value["title"] === "string" &&
    value["title"].trim() !== "" &&
    (value["purpose"] === undefined || typeof value["purpose"] === "string") &&
    objectRecord(operations) &&
    Array.isArray(operations["added"]) &&
    operations["added"].every(validRequirement) &&
    Array.isArray(operations["modified"]) &&
    operations["modified"].every(validRequirement) &&
    Array.isArray(operations["removed"]) &&
    operations["removed"].every(
      (removed: unknown) =>
        objectRecord(removed) &&
        typeof removed["id"] === "string" &&
        /^REQ-[A-Z0-9-]+$/u.test(removed["id"]) &&
        typeof removed["reason"] === "string" &&
        removed["reason"].trim() !== "",
    );
  if (!valid) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `${label} does not match the CapabilityDelta contract.`,
    );
  }
  return structuredClone(value) as unknown as CapabilityDelta;
}

function parseCapabilitySpec(source: string, label: string): CapabilitySpec {
  const value = parseYamlObject(source, label);
  const valid =
    value["apiVersion"] === "aifw.dev/v1alpha1" &&
    value["kind"] === "CapabilitySpec" &&
    typeof value["capability"] === "string" &&
    /^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$/u.test(value["capability"]) &&
    typeof value["title"] === "string" &&
    value["title"].trim() !== "" &&
    typeof value["purpose"] === "string" &&
    value["purpose"].trim() !== "" &&
    Array.isArray(value["requirements"]) &&
    value["requirements"].every(validRequirement);
  if (!valid) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `${label} does not match the CapabilitySpec contract.`,
    );
  }
  return structuredClone(value) as unknown as CapabilitySpec;
}

async function loadCurrentCapability(
  root: string,
  capability: string,
): Promise<CapabilitySpec | undefined> {
  const relativePath = `.aifw/specs/current/${capability}.yaml`;
  try {
    return parseCapabilitySpec(
      await readFile(path.join(root, ...relativePath.split("/")), "utf8"),
      relativePath,
    );
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
}

function parseTasks(source: string, label: string): ChangeTasks {
  const value = parseYamlObject(source, label);
  const valid =
    value["apiVersion"] === "aifw.dev/v1alpha1" &&
    value["kind"] === "ChangeTasks" &&
    typeof value["changeId"] === "string" &&
    Array.isArray(value["tasks"]) &&
    value["tasks"].every(
      (task: unknown) =>
        objectRecord(task) &&
        typeof task["id"] === "string" &&
        /^TASK-[A-Z0-9-]+$/u.test(task["id"]) &&
        typeof task["title"] === "string" &&
        enumString(task["status"], ["pending", "in-progress", "blocked", "done"]) &&
        stringArray(task["dependsOn"]) &&
        stringArray(task["requirementIds"]) &&
        stringArray(task["paths"]),
    );
  if (!valid) {
    throw new AifwError("MANIFEST_INVALID", `${label} does not match the ChangeTasks contract.`);
  }
  return structuredClone(value) as unknown as ChangeTasks;
}

function parseTraceability(source: string, label: string): ChangeTraceability {
  const value = parseYamlObject(source, label);
  const valid =
    value["apiVersion"] === "aifw.dev/v1alpha1" &&
    value["kind"] === "ChangeTraceability" &&
    typeof value["changeId"] === "string" &&
    Array.isArray(value["artifacts"]) &&
    value["artifacts"].every(
      (artifact: unknown) =>
        objectRecord(artifact) &&
        typeof artifact["id"] === "string" &&
        enumString(artifact["type"], ["test", "gate", "evidence", "adr", "design"]) &&
        (artifact["path"] === undefined || typeof artifact["path"] === "string") &&
        enumString(artifact["status"], ["planned", "passed", "failed", "waived"]),
    ) &&
    Array.isArray(value["links"]) &&
    value["links"].every(
      (link: unknown) =>
        objectRecord(link) &&
        typeof link["from"] === "string" &&
        enumString(link["relation"], ["verifiedBy", "provedBy", "designedBy", "governedBy", "checkedBy"]) &&
        typeof link["to"] === "string",
    );
  if (!valid) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `${label} does not match the ChangeTraceability contract.`,
    );
  }
  return structuredClone(value) as unknown as ChangeTraceability;
}

async function loadChangeArtifacts(root: string, id: string): Promise<{
  change: SpecChangeRecord;
  deltas: CapabilityDelta[];
  tasks: ChangeTasks;
  traceability: ChangeTraceability;
}> {
  const change = await loadActiveChange(root, id);
  const base = `.aifw/changes/active/${id}`;
  const deltaFiles = await fg(`${base}/specs/*.delta.yaml`, {
    cwd: root,
    onlyFiles: true,
    dot: true,
    followSymbolicLinks: false,
  });
  const deltas = await Promise.all(
    deltaFiles.sort().map(async (relativeFile) =>
      parseDelta(await readFile(path.join(root, relativeFile), "utf8"), relativeFile),
    ),
  );
  const tasksPath = `${base}/tasks.yaml`;
  const traceabilityPath = `${base}/traceability.yaml`;
  const [tasks, traceability] = await Promise.all([
    readFile(path.join(root, ...tasksPath.split("/")), "utf8").then((source) =>
      parseTasks(source, tasksPath),
    ),
    readFile(path.join(root, ...traceabilityPath.split("/")), "utf8").then((source) =>
      parseTraceability(source, traceabilityPath),
    ),
  ]);
  if (
    deltas.some((delta) => delta.changeId !== id) ||
    tasks.changeId !== id ||
    traceability.changeId !== id
  ) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `Change artifact ids must match ${id}.`,
      [id],
    );
  }
  return { change, deltas, tasks, traceability };
}

export async function createSpecChange(
  root: string,
  input: CreateSpecChangeInput,
): Promise<CreateSpecChangeResult> {
  assertChangeId(input.id);
  if (input.title.trim() === "" || input.summary.trim() === "") {
    throw new AifwError(
      "MANIFEST_INVALID",
      "A spec change requires a non-empty title and summary.",
      ["title", "summary"],
    );
  }
  if (Number.isNaN(new Date(input.createdAt).valueOf())) {
    throw new AifwError(
      "MANIFEST_INVALID",
      "A spec change requires a valid createdAt timestamp.",
      [input.createdAt],
    );
  }

  const change: SpecChangeRecord = {
    apiVersion: "aifw.dev/v1alpha1",
    kind: "SpecChange",
    metadata: {
      id: input.id,
      title: input.title.trim(),
      level: input.level,
      createdAt: input.createdAt,
    },
    summary: input.summary.trim(),
    status: "draft",
  };
  const base = `.aifw/changes/active/${input.id}`;
  const absoluteBase = path.join(root, ...base.split("/"));
  if (await exists(absoluteBase)) {
    throw new AifwError(
      "POLICY_CONFLICT",
      `Spec change already exists: ${input.id}`,
      [base],
    );
  }

  const files: Record<string, string> = {
    [`${base}/change.yaml`]: yaml(change),
    [`${base}/design.md`]: `# Design — ${change.metadata.title}\n\n## Context\n\n## Approach\n\n## Decisions\n\n## Risks and rollback\n`,
    [`${base}/evidence/README.md`]: "# Evidence\n\nStore reproducible gate and verification evidence for this change here.\n",
    [`${base}/proposal.md`]: `# Proposal — ${change.metadata.title}\n\n## Intent\n\n${change.summary}\n\n## Scope\n\n## Non-goals\n\n## Acceptance\n`,
    [`${base}/specs/README.md`]: "# Capability deltas\n\nAdd one `<capability>.delta.yaml` file per affected capability.\n",
    [`${base}/tasks.yaml`]: yaml({
      apiVersion: "aifw.dev/v1alpha1",
      kind: "ChangeTasks",
      changeId: input.id,
      tasks: [],
    }),
    [`${base}/traceability.yaml`]: yaml({
      apiVersion: "aifw.dev/v1alpha1",
      kind: "ChangeTraceability",
      changeId: input.id,
      artifacts: [],
      links: [],
    }),
  };

  for (const [relativePath, content] of Object.entries(files)) {
    const absolutePath = path.join(root, ...relativePath.split("/"));
    await mkdir(path.dirname(absolutePath), { recursive: true });
    await writeFile(absolutePath, content, { encoding: "utf8", flag: "wx" });
  }

  return { change, createdFiles: Object.keys(files).sort() };
}

export async function listSpecChanges(root: string): Promise<SpecChangeListEntry[]> {
  const relativeFiles = await fg(
    [".aifw/changes/active/*/change.yaml", ".aifw/changes/archive/*/change.yaml"],
    {
      cwd: root,
      onlyFiles: true,
      dot: true,
      followSymbolicLinks: false,
    },
  );
  const entries = await Promise.all(
    relativeFiles.map(async (relativeFile) => {
      const normalized = relativeFile.replaceAll("\\", "/");
      const change = parseChange(
        await readFile(path.join(root, relativeFile), "utf8"),
        normalized,
      );
      return {
        id: change.metadata.id,
        title: change.metadata.title,
        level: change.metadata.level,
        status: change.status,
        location: normalized.includes("/archive/") ? "archive" as const : "active" as const,
        relativePath: normalized,
      };
    }),
  );
  return entries.sort(
    (left, right) => left.location.localeCompare(right.location) || left.id.localeCompare(right.id),
  );
}

export async function analyzeSpecChange(root: string, id: string): Promise<SpecAnalysis> {
  const { change, deltas, tasks, traceability } = await loadChangeArtifacts(root, id);
  const requirements = deltas.flatMap((delta) => [
    ...delta.operations.added,
    ...delta.operations.modified,
    ...delta.operations.removed.map((removed) => ({
      id: removed.id,
      strength: "MUST" as const,
      statement: `Remove requirement: ${removed.reason}`,
      scenarios: [],
    })),
  ]);
  const scenarios = requirements.flatMap((requirement) => requirement.scenarios);
  const requirementIds = new Set(requirements.map((requirement) => requirement.id));
  const scenarioIds = new Set(scenarios.map((scenario) => scenario.id));
  const linkedRequirementIds = new Set(
    tasks.tasks.flatMap((task) => task.requirementIds.filter((requirementId) => requirementIds.has(requirementId))),
  );
  const findings: SpecFinding[] = [];
  const knownTraceIds = new Set([
    ...requirements.map((requirement) => requirement.id),
    ...scenarios.map((scenario) => scenario.id),
    ...tasks.tasks.map((task) => task.id),
    ...traceability.artifacts.map((artifact) => artifact.id),
  ]);
  for (const link of traceability.links) {
    const missing = [link.from, link.to].filter((nodeId) => !knownTraceIds.has(nodeId));
    if (missing.length > 0) {
      findings.push({
        code: "DANGLING_TRACE_LINK",
        severity: "error",
        message: `Trace link ${link.from} ${link.relation} ${link.to} references an unknown node.`,
        relatedIds: missing,
        locations: [`.aifw/changes/active/${id}/traceability.yaml`],
      });
    }
    const target = traceability.artifacts.find((artifact) => artifact.id === link.to);
    if (link.relation === "checkedBy" && target?.type === "gate" && target.status !== "passed") {
      findings.push({
        code: "TRACE_GATE_NOT_PASSED",
        severity: "error",
        message: `Required trace gate ${target.id} is ${target.status}; checkedBy requires passed verification.`,
        relatedIds: [link.from, target.id],
        locations: [`.aifw/changes/active/${id}/traceability.yaml`],
      });
    }
  }
  for (const task of tasks.tasks) {
    const unknownRequirementIds = task.requirementIds.filter(
      (requirementId) => !requirementIds.has(requirementId),
    );
    if (unknownRequirementIds.length > 0) {
      findings.push({
        code: "TASK_UNKNOWN_REQUIREMENT",
        severity: "error",
        message: `Task ${task.id} references requirements that are not declared by this change.`,
        relatedIds: [task.id, ...unknownRequirementIds],
        locations: [`.aifw/changes/active/${id}/tasks.yaml`],
      });
    }
  }
  const validPassedArtifacts = new Set<string>();
  for (const artifact of traceability.artifacts) {
    if (artifact.status !== "passed") continue;
    const fileStatus = await inspectProjectFile(root, artifact.path ?? "");
    if (fileStatus === "outside") {
      findings.push({
        code: "TRACE_ARTIFACT_OUTSIDE_PROJECT",
        severity: "error",
        message: `Trace artifact ${artifact.id} points outside the project.`,
        relatedIds: [artifact.id],
        locations: [`.aifw/changes/active/${id}/traceability.yaml`],
      });
    } else if (fileStatus === "missing") {
      findings.push({
        code: "TRACE_ARTIFACT_MISSING",
        severity: "error",
        message: `Passed trace artifact ${artifact.id} requires an existing file path inside the project.`,
        relatedIds: [artifact.id],
        locations: [artifact.path ?? `.aifw/changes/active/${id}/traceability.yaml`],
      });
    } else {
      validPassedArtifacts.add(artifact.id);
    }
  }
  const verifiedScenarioIds = new Set(
    traceability.links.filter((link) =>
      link.relation === "verifiedBy" && scenarioIds.has(link.from) &&
      validPassedArtifacts.has(link.to) &&
      traceability.artifacts.some((artifact) => artifact.id === link.to && artifact.type === "test")
    ).map((link) => link.from),
  );
  for (const requirement of requirements) {
    if (!linkedRequirementIds.has(requirement.id)) {
      findings.push({
        code: "ORPHAN_REQUIREMENT",
        severity: change.metadata.level === "L0" || change.metadata.level === "L1" ? "warning" : "error",
        message: `Requirement ${requirement.id} is not linked to an implementation task.`,
        relatedIds: [requirement.id],
        locations: [`.aifw/changes/active/${id}/specs`],
      });
    }
  }
  for (const scenario of scenarios) {
    if (!verifiedScenarioIds.has(scenario.id)) {
      findings.push({
        code: "SCENARIO_WITHOUT_VERIFICATION",
        severity: change.metadata.level === "L0" || change.metadata.level === "L1" ? "warning" : "error",
        message: `Scenario ${scenario.id} has no passed test verification.`,
        relatedIds: [scenario.id],
        locations: [`.aifw/changes/active/${id}/traceability.yaml`],
      });
    }
  }

  const nodes = [
    ...requirements.map((requirement) => ({ id: requirement.id, type: "requirement" })),
    ...scenarios.map((scenario) => ({ id: scenario.id, type: "scenario" })),
    ...tasks.tasks.map((task) => ({ id: task.id, type: "task" })),
    ...tasks.tasks.flatMap((task) => task.paths.map((filePath) => ({
      id: `FILE:${filePath}`,
      type: "code",
      path: filePath,
    }))),
    ...traceability.artifacts.map((artifact) => ({
      id: artifact.id,
      type: artifact.type,
      ...(artifact.path === undefined ? {} : { path: artifact.path }),
    })),
  ].sort((left, right) => left.id.localeCompare(right.id));
  const links = [
    ...requirements.flatMap((requirement) => requirement.scenarios.map((scenario) => ({
      from: requirement.id,
      relation: "hasScenario",
      to: scenario.id,
    }))),
    ...tasks.tasks.flatMap((task) => [
      ...task.requirementIds.map((requirementId) => ({
        from: requirementId,
        relation: "implementedBy",
        to: task.id,
      })),
      ...task.paths.map((filePath) => ({
        from: task.id,
        relation: "changes",
        to: `FILE:${filePath}`,
      })),
    ]),
    ...traceability.links,
  ].sort(
    (left, right) =>
      left.from.localeCompare(right.from) ||
      left.relation.localeCompare(right.relation) ||
      left.to.localeCompare(right.to),
  );

  return {
    change,
    pass: findings.every((finding) => finding.severity !== "error"),
    findings: findings.sort(
      (left, right) => left.code.localeCompare(right.code) || left.relatedIds.join().localeCompare(right.relatedIds.join()),
    ),
    coverage: {
      requirements: { total: requirements.length, linkedToTask: linkedRequirementIds.size },
      scenarios: { total: scenarios.length, verified: verifiedScenarioIds.size },
      tasks: {
        total: tasks.tasks.length,
        completed: tasks.tasks.filter((task) => task.status === "done").length,
      },
    },
    graph: { nodes, links },
  };
}

export async function validateSpecChange(root: string, id: string): Promise<SpecValidation> {
  const { change, deltas } = await loadChangeArtifacts(root, id);
  const findings: SpecFinding[] = [];
  if (
    deltas.length === 0 &&
    (change.metadata.level === "L2" || change.metadata.level === "L3")
  ) {
    findings.push({
      code: "CHANGE_REQUIRES_DELTA",
      severity: "error",
      message: `${change.metadata.level} change ${id} requires at least one capability delta.`,
      relatedIds: [id],
      locations: [`.aifw/changes/active/${id}/specs`],
    });
  }
  const requirementOccurrences = new Map<string, number>();
  const scenarioOccurrences = new Map<string, number>();
  const capabilities = new Set<string>();
  for (const delta of deltas) {
    if (capabilities.has(delta.capability)) {
      findings.push({
        code: "DUPLICATE_CAPABILITY_DELTA",
        severity: "error",
        message: `Change ${id} must contain only one delta for capability ${delta.capability}.`,
        relatedIds: [delta.capability],
        locations: [`.aifw/changes/active/${id}/specs`],
      });
    }
    capabilities.add(delta.capability);
    for (const requirement of [
      ...delta.operations.added,
      ...delta.operations.modified,
      ...delta.operations.removed.map((removed) => ({ ...removed, scenarios: [] as RequirementScenario[] })),
    ]) {
      requirementOccurrences.set(
        requirement.id,
        (requirementOccurrences.get(requirement.id) ?? 0) + 1,
      );
      for (const scenario of requirement.scenarios) {
        scenarioOccurrences.set(
          scenario.id,
          (scenarioOccurrences.get(scenario.id) ?? 0) + 1,
        );
      }
    }
  }
  for (const [requirementId, count] of requirementOccurrences) {
    if (count > 1) {
      findings.push({
        code: "DUPLICATE_REQUIREMENT_ID",
        severity: "error",
        message: `Requirement id ${requirementId} appears ${String(count)} times in change ${id}.`,
        relatedIds: [requirementId],
        locations: [`.aifw/changes/active/${id}/specs`],
      });
    }
  }
  for (const [scenarioId, count] of scenarioOccurrences) {
    if (count > 1) {
      findings.push({
        code: "DUPLICATE_SCENARIO_ID",
        severity: "error",
        message: `Scenario id ${scenarioId} appears ${String(count)} times in change ${id}.`,
        relatedIds: [scenarioId],
        locations: [`.aifw/changes/active/${id}/specs`],
      });
    }
  }
  for (const delta of deltas) {
    const current = await loadCurrentCapability(root, delta.capability);
    if (current === undefined && (delta.purpose === undefined || delta.purpose.trim() === "")) {
      findings.push({
        code: "NEW_CAPABILITY_REQUIRES_PURPOSE",
        severity: "error",
        message: `New capability ${delta.capability} requires an explicit purpose.`,
        relatedIds: [delta.capability],
        locations: [`.aifw/changes/active/${id}/specs/${delta.capability}.delta.yaml`],
      });
    }
    const currentRequirementIds = new Set(
      current?.requirements.map((requirement) => requirement.id) ?? [],
    );
    for (const requirement of delta.operations.added) {
      if (currentRequirementIds.has(requirement.id)) {
        findings.push({
          code: "DELTA_ADDS_EXISTING_REQUIREMENT",
          severity: "error",
          message: `Delta for ${delta.capability} adds existing requirement ${requirement.id}.`,
          relatedIds: [delta.capability, requirement.id],
          locations: [`.aifw/changes/active/${id}/specs/${delta.capability}.delta.yaml`],
        });
      }
    }
    for (const requirement of delta.operations.modified) {
      if (!currentRequirementIds.has(requirement.id)) {
        findings.push({
          code: "DELTA_MODIFIES_UNKNOWN_REQUIREMENT",
          severity: "error",
          message: `Delta for ${delta.capability} modifies unknown requirement ${requirement.id}.`,
          relatedIds: [delta.capability, requirement.id],
          locations: [`.aifw/changes/active/${id}/specs/${delta.capability}.delta.yaml`],
        });
      }
    }
    for (const removed of delta.operations.removed) {
      if (!currentRequirementIds.has(removed.id)) {
        findings.push({
          code: "DELTA_REMOVES_UNKNOWN_REQUIREMENT",
          severity: "error",
          message: `Delta for ${delta.capability} removes unknown requirement ${removed.id}.`,
          relatedIds: [delta.capability, removed.id],
          locations: [`.aifw/changes/active/${id}/specs/${delta.capability}.delta.yaml`],
        });
      }
    }
  }
  return {
    change,
    pass: findings.every((finding) => finding.severity !== "error"),
    findings: findings.sort(
      (left, right) => left.code.localeCompare(right.code) || left.relatedIds.join().localeCompare(right.relatedIds.join()),
    ),
    capabilities: deltas.map((delta) => delta.capability).sort(),
  };
}

function applyCapabilityDelta(
  current: CapabilitySpec | undefined,
  delta: CapabilityDelta,
): CapabilitySpec {
  const requirements = new Map(
    (current?.requirements ?? []).map((requirement) => [requirement.id, structuredClone(requirement)]),
  );
  for (const requirement of delta.operations.added) {
    requirements.set(requirement.id, structuredClone(requirement));
  }
  for (const requirement of delta.operations.modified) {
    requirements.set(requirement.id, structuredClone(requirement));
  }
  for (const removed of delta.operations.removed) requirements.delete(removed.id);

  return {
    apiVersion: "aifw.dev/v1alpha1",
    kind: "CapabilitySpec",
    capability: delta.capability,
    title: delta.title.trim(),
    purpose: (current?.purpose ?? delta.purpose ?? "").trim(),
    requirements: [...requirements.values()]
      .map((requirement) => ({
        ...requirement,
        scenarios: [...requirement.scenarios].sort((left, right) => left.id.localeCompare(right.id)),
      }))
      .sort((left, right) => left.id.localeCompare(right.id)),
  };
}

export async function previewSpecSync(root: string, id: string): Promise<SpecSyncPlan> {
  const validation = await validateSpecChange(root, id);
  if (!validation.pass) {
    return {
      changeId: id,
      pass: false,
      findings: validation.findings,
      changes: [],
      outputs: [],
    };
  }
  const { deltas } = await loadChangeArtifacts(root, id);
  const planned = await Promise.all(
    deltas.map(async (delta) => {
      const current = await loadCurrentCapability(root, delta.capability);
      const relativePath = `.aifw/specs/current/${delta.capability}.yaml`;
      return {
        change: {
          capability: delta.capability,
          action: current === undefined ? "create" as const : "update" as const,
          added: delta.operations.added.map((requirement) => requirement.id).sort(),
          modified: delta.operations.modified.map((requirement) => requirement.id).sort(),
          removed: delta.operations.removed.map((requirement) => requirement.id).sort(),
          outputPath: relativePath,
        },
        output: {
          relativePath,
          spec: parseCapabilitySpec(yaml(applyCapabilityDelta(current, delta)), relativePath),
        },
      };
    }),
  );
  return {
    changeId: id,
    pass: true,
    findings: [],
    changes: planned.map((entry) => entry.change).sort((left, right) => left.capability.localeCompare(right.capability)),
    outputs: planned.map((entry) => entry.output).sort((left, right) => left.relativePath.localeCompare(right.relativePath)),
  };
}

export async function archiveSpecChange(
  root: string,
  id: string,
  options: { archivedAt: string },
): Promise<ArchiveSpecChangeResult> {
  const change = await loadActiveChange(root, id);
  if (change.status !== "ready") {
    throw new AifwError(
      "NOT_READY",
      `Spec change ${id} must be ready before archive.`,
      [change.status],
    );
  }
  await assertSpecApproval(root, change);
  if (Number.isNaN(new Date(options.archivedAt).valueOf())) {
    throw new AifwError(
      "MANIFEST_INVALID",
      "Archive requires a valid archivedAt timestamp.",
      [options.archivedAt],
    );
  }
  const [validation, analysis, plan, artifacts] = await Promise.all([
    validateSpecChange(root, id),
    analyzeSpecChange(root, id),
    previewSpecSync(root, id),
    loadChangeArtifacts(root, id),
  ]);
  const blockers = [...validation.findings, ...analysis.findings].filter(
    (finding) => finding.severity === "error",
  );
  if (!plan.pass || blockers.length > 0) {
    throw new AifwError(
      "NOT_READY",
      `Spec change ${id} changed after readiness and now has blockers: ${blockers.map((finding) => finding.code).join(", ")}.`,
      blockers.map((finding) => finding.code),
    );
  }
  const incompleteTasks = artifacts.tasks.tasks.filter((task) => task.status !== "done");
  if (incompleteTasks.length > 0) {
    throw new AifwError(
      "NOT_READY",
      `Spec change ${id} still has incomplete tasks.`,
      incompleteTasks.map((task) => task.id),
    );
  }

  const archiveDate = options.archivedAt.slice(0, 10);
  const archiveRelativePath = `.aifw/changes/archive/${archiveDate}-${id}`;
  const activeDirectory = path.join(root, ".aifw", "changes", "active", id);
  const archiveDirectory = path.join(root, ...archiveRelativePath.split("/"));
  if (await exists(archiveDirectory)) {
    throw new AifwError(
      "POLICY_CONFLICT",
      `Archive target already exists for ${id}.`,
      [archiveRelativePath],
    );
  }

  const transactionDirectory = path.join(
    root,
    ".aifw",
    "transactions",
    `${id}-${randomUUID()}`,
  );
  const nextCurrentDirectory = path.join(transactionDirectory, "next-current");
  const previousCurrentDirectory = path.join(transactionDirectory, "previous-current");
  const nextArchiveDirectory = path.join(transactionDirectory, "next-archive");
  const previousActiveDirectory = path.join(transactionDirectory, "previous-active");
  const currentDirectory = path.join(root, ".aifw", "specs", "current");
  const currentExisted = await exists(currentDirectory);
  let currentSwapped = false;
  let activeMoved = false;

  await mkdir(transactionDirectory, { recursive: true });
  if (currentExisted) {
    await cp(currentDirectory, nextCurrentDirectory, { recursive: true, force: false });
  } else {
    await mkdir(nextCurrentDirectory, { recursive: true });
  }
  for (const output of plan.outputs) {
    const target = path.join(nextCurrentDirectory, `${output.spec.capability}.yaml`);
    await writeFile(target, yaml(output.spec), "utf8");
  }
  await cp(activeDirectory, nextArchiveDirectory, { recursive: true, force: false });
  const archivedChange: SpecChangeRecord = {
    ...change,
    status: "archived",
    archivedAt: options.archivedAt,
  };
  await writeFile(path.join(nextArchiveDirectory, "change.yaml"), yaml(archivedChange), "utf8");
  const archivedTracePath = path.join(nextArchiveDirectory, "traceability.yaml");
  const archivedTraceSource = await readFile(archivedTracePath, "utf8");
  const activePrefix = `.aifw/changes/active/${id}/`;
  const archivePrefix = `${archiveRelativePath}/`;
  if (archivedTraceSource.includes(activePrefix)) {
    await writeFile(
      archivedTracePath,
      archivedTraceSource.replaceAll(activePrefix, archivePrefix),
      "utf8",
    );
  }

  try {
    await mkdir(path.dirname(currentDirectory), { recursive: true });
    await mkdir(path.dirname(archiveDirectory), { recursive: true });
    if (currentExisted) await rename(currentDirectory, previousCurrentDirectory);
    await rename(nextCurrentDirectory, currentDirectory);
    currentSwapped = true;
    await rename(activeDirectory, previousActiveDirectory);
    activeMoved = true;
    await rename(nextArchiveDirectory, archiveDirectory);
  } catch (error) {
    try {
      if (activeMoved && await exists(previousActiveDirectory) && !(await exists(activeDirectory))) {
        await mkdir(path.dirname(activeDirectory), { recursive: true });
        await rename(previousActiveDirectory, activeDirectory);
      }
      if (currentSwapped && await exists(currentDirectory)) {
        await rm(currentDirectory, { recursive: true, force: true });
      }
      if (currentExisted && await exists(previousCurrentDirectory)) {
        await rename(previousCurrentDirectory, currentDirectory);
      }
      await rm(transactionDirectory, { recursive: true, force: true });
    } catch (rollbackError) {
      throw new AifwError(
        "COMMAND_FAILED",
        `Archive failed and rollback also failed for ${id}.`,
        [String(error), String(rollbackError), transactionDirectory],
      );
    }
    throw new AifwError(
      "COMMAND_FAILED",
      `Archive transaction failed and was rolled back for ${id}.`,
      [String(error)],
    );
  }

  const result: ArchiveSpecChangeResult = {
    changeId: id,
    archivePath: archiveRelativePath,
    currentSpecs: plan.outputs.map((output) => output.relativePath).sort(),
  };
  // Commit is complete. Cleanup may remove backups, so it cannot trigger rollback.
  try {
    await rm(transactionDirectory, { recursive: true, force: true });
  } catch (error) {
    result.cleanupPending = {
      path: path.relative(root, transactionDirectory).replaceAll("\\", "/"),
      reason: String(error),
    };
  }
  return result;
}

export async function updateSpecChangeStatus(
  root: string,
  id: string,
  status: "active" | "ready",
): Promise<SpecChangeRecord> {
  const change = await loadActiveChange(root, id);
  if (status === "ready") {
    const [validation, analysis] = await Promise.all([
      validateSpecChange(root, id),
      analyzeSpecChange(root, id),
    ]);
    const blockers = [...validation.findings, ...analysis.findings].filter(
      (finding) => finding.severity === "error",
    );
    if (blockers.length > 0) {
      throw new AifwError(
        "NOT_READY",
        `Spec change ${id} cannot become ready while validation or traceability has blockers: ${blockers.map((finding) => finding.code).join(", ")}.`,
        blockers.map((finding) => finding.code),
      );
    }
    await assertSpecApproval(root, change);
  }
  const updated: SpecChangeRecord = { ...change, status };
  const changePath = path.join(root, ".aifw", "changes", "active", id, "change.yaml");
  await writeFile(changePath, yaml(updated), "utf8");
  return updated;
}

export async function approveSpecChange(
  root: string,
  id: string,
  approval: { approvedBy: string; approvedAt: string; record: string },
): Promise<SpecChangeRecord> {
  const change = await loadActiveChange(root, id);
  if (
    !/^human:\S+$/u.test(approval.approvedBy) ||
    Number.isNaN(new Date(approval.approvedAt).valueOf())
  ) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "Spec change approval requires a human identity and valid timestamp.",
      [approval.approvedBy, approval.approvedAt],
    );
  }
  const absoluteRecordPath = path.resolve(root, approval.record);
  const relativeRecordPath = path.relative(root, absoluteRecordPath);
  if (await inspectProjectFile(root, approval.record) !== "valid") {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "Spec change approval record must be an existing file inside the project.",
      [approval.record],
    );
  }
  const updated: SpecChangeRecord = {
    ...change,
    approval: {
      approvedBy: approval.approvedBy,
      approvedAt: approval.approvedAt,
      record: relativeRecordPath.replaceAll("\\", "/"),
    },
  };
  await writeFile(
    path.join(root, ".aifw", "changes", "active", id, "change.yaml"),
    yaml(updated),
    "utf8",
  );
  return updated;
}
