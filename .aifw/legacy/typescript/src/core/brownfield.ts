import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { parseDocument, stringify } from "yaml";

import { discoverProject, type ProjectDiscovery } from "./discovery.ts";
import { AifwError } from "./errors.ts";
import type { CatalogEntity } from "./project-map.ts";
import {
  buildWorkspaceMap,
  loadWorkspaceCatalog,
  loadWorkspaceManifest,
  writeWorkspaceCatalog,
  type WorkspaceMapResult,
} from "./workspace.ts";

export interface BrownfieldDiscoveryReport {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "BrownfieldDiscovery";
  projectId: string;
  generatedAt: string;
  digest: string;
  discovery: ProjectDiscovery;
  candidates: {
    sourcesOfTruth: Array<{ topic: string; source: string }>;
    entities: CatalogEntity[];
  };
  unknowns: string[];
}

export interface BrownfieldAdoptionState {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "BrownfieldAdoption";
  projectId: string;
  status: "analyzed" | "review-required" | "approved";
  reportDigest: string;
  analyzedAt: string;
  appliedAt?: string;
  approval?: {
    approvedBy: string;
    approvedAt: string;
    contentDigest: string;
  };
}

export interface WriteBrownfieldAnalysisResult {
  reportPath: ".aifw/adoption/discovery.json";
  statePath: ".aifw/adoption/status.yaml";
  report: BrownfieldDiscoveryReport;
  state: BrownfieldAdoptionState;
}

export interface ApplyBrownfieldMappingResult {
  state: BrownfieldAdoptionState;
  appliedEntityIds: string[];
  architecturePath: "docs/architecture/discovered.md";
  projectMap: WorkspaceMapResult;
}

export interface BrownfieldAdoptionAssessment {
  id: "brownfield-mapping";
  owner: "agent";
  blockingHumanApproval: boolean;
  status: "pending" | "review-required" | "current" | "invalid";
  artifact: ".aifw/adoption/status.yaml";
  reason: string;
  nextAction?: string;
}

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

function digest(value: unknown): string {
  return createHash("sha256")
    .update(JSON.stringify(stableValue(value)))
    .digest("hex");
}

function objectRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
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
    throw new AifwError("MANIFEST_INVALID", `${label} must be an object.`);
  }
  return value;
}

function validatePersistedReport(report: unknown): BrownfieldDiscoveryReport {
  if (!objectRecord(report)) {
    throw new AifwError(
      "MANIFEST_INVALID",
      ".aifw/adoption/discovery.json must be an object.",
    );
  }
  const persistedDigest = report["digest"];
  const candidates = report["candidates"];
  const payload = Object.fromEntries(
    Object.entries(report).filter(([key]) => key !== "digest" && key !== "generatedAt"),
  );
  if (
    report["apiVersion"] !== "aifw.dev/v1alpha1" ||
    report["kind"] !== "BrownfieldDiscovery" ||
    typeof report["projectId"] !== "string" ||
    typeof report["generatedAt"] !== "string" ||
    typeof persistedDigest !== "string" ||
    persistedDigest !== digest(payload) ||
    !objectRecord(candidates) ||
    !Array.isArray(candidates["entities"]) ||
    !Array.isArray(candidates["sourcesOfTruth"]) ||
    !Array.isArray(report["unknowns"])
  ) {
    throw new AifwError(
      "MANIFEST_INVALID",
      ".aifw/adoption/discovery.json is invalid or its digest does not match its content.",
    );
  }
  return structuredClone(report) as unknown as BrownfieldDiscoveryReport;
}

async function loadBrownfieldFiles(root: string): Promise<{
  report: BrownfieldDiscoveryReport;
  state: BrownfieldAdoptionState;
}> {
  const reportPath = path.join(root, ".aifw", "adoption", "discovery.json");
  const statePath = path.join(root, ".aifw", "adoption", "status.yaml");
  try {
    const [reportSource, stateSource] = await Promise.all([
      readFile(reportPath, "utf8"),
      readFile(statePath, "utf8"),
    ]);
    const report = validatePersistedReport(JSON.parse(reportSource) as unknown);
    const stateValue = parseYamlObject(
      stateSource,
      ".aifw/adoption/status.yaml",
    );
    if (
      stateValue["apiVersion"] !== "aifw.dev/v1alpha1" ||
      stateValue["kind"] !== "BrownfieldAdoption" ||
      stateValue["projectId"] !== report.projectId ||
      stateValue["reportDigest"] !== report.digest ||
      typeof stateValue["status"] !== "string" ||
      !["analyzed", "review-required", "approved"].includes(stateValue["status"])
    ) {
      throw new AifwError(
        "MANIFEST_INVALID",
        "Brownfield adoption state does not match the persisted discovery report.",
      );
    }
    const state = structuredClone(stateValue) as unknown as BrownfieldAdoptionState;
    return { report, state };
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      throw new AifwError(
        "NOT_READY",
        "Run brownfield analysis with persistence before applying the map.",
        ["aifw adopt analyze --write"],
      );
    }
    throw error;
  }
}

function renderDiscoveredArchitecture(report: BrownfieldDiscoveryReport): string {
  const section = (title: string, values: string[]): string[] => [
    `## ${title}`,
    "",
    ...(values.length === 0 ? ["_None discovered._"] : values.map((value) => `- \`${value}\``)),
    "",
  ];
  return [
    "# Discovered architecture inventory",
    "",
    `> Generated from factual repository discovery (${report.digest}). This is not an approved semantic architecture. This mapping requires human review of candidate responsibilities, owners and relations.`,
    "",
    ...section("Module manifests", report.discovery.moduleManifests),
    ...section("Entrypoints", report.discovery.entrypoints),
    ...section("Source roots", report.discovery.sourceRoots),
    ...section("Contracts", report.discovery.contracts),
    ...section("CI", report.discovery.ciFiles),
    ...section("ADRs", report.discovery.adrFiles),
    ...section("Configuration", report.discovery.configurationFiles),
    ...section("Documentation", report.discovery.documentationFiles),
    "## Review questions",
    "",
    ...report.unknowns.map((unknown) => `- ${unknown}`),
    "",
  ].join("\n");
}

function slug(value: string): string {
  return value
    .toLocaleLowerCase("en-US")
    .replaceAll("\\", "/")
    .replace(/[^a-z0-9]+/gu, "-")
    .replace(/^-+|-+$/gu, "");
}

function moduleEntity(
  projectId: string,
  manifest: string,
  verifiedAt: string,
): CatalogEntity {
  const directory = path.posix.dirname(manifest);
  const rootModule = directory === ".";
  const moduleId = rootModule ? `${projectId}-root` : slug(directory);
  return {
    id: `component:${moduleId}`,
    kind: "Component",
    name: rootModule ? `${projectId} root module` : directory,
    description: `Discovered module manifest at ${manifest}; responsibility requires review.`,
    owner: "human:unassigned",
    source: manifest,
    visibility: "internal",
    origin: "discovered",
    confidence: "candidate",
    lastVerifiedAt: verifiedAt,
    relations: [{ type: "partOf", target: `system:${projectId}` }],
  };
}

function referencedEntity(
  projectId: string,
  source: string,
  kind: "Contract" | "Decision" | "Resource",
  prefix: "contract" | "decision" | "resource",
  description: string,
  verifiedAt: string,
): CatalogEntity {
  return {
    id: `${prefix}:${slug(source)}`,
    kind,
    name: source,
    description,
    owner: "human:unassigned",
    source,
    visibility: "internal",
    origin: "discovered",
    confidence: "candidate",
    lastVerifiedAt: verifiedAt,
    relations: [{ type: "partOf", target: `system:${projectId}` }],
  };
}

export async function analyzeBrownfieldProject(
  root: string,
  options: { generatedAt: string },
): Promise<BrownfieldDiscoveryReport> {
  if (Number.isNaN(new Date(options.generatedAt).valueOf())) {
    throw new AifwError(
      "MANIFEST_INVALID",
      "Brownfield analysis requires a valid generatedAt timestamp.",
      [options.generatedAt],
    );
  }
  const [manifest, discovery] = await Promise.all([
    loadWorkspaceManifest(root),
    discoverProject(root),
  ]);
  if (manifest.spec.projectType !== "existing") {
    throw new AifwError(
      "POLICY_CONFLICT",
      "Brownfield adoption is available only for projects initialized with --existing.",
    );
  }

  const entities = [
    ...discovery.moduleManifests.map((manifestPath) =>
      moduleEntity(manifest.metadata.id, manifestPath, options.generatedAt),
    ),
    ...discovery.contracts.map((source) =>
      referencedEntity(
        manifest.metadata.id,
        source,
        "Contract",
        "contract",
        `Discovered machine-readable contract at ${source}.`,
        options.generatedAt,
      ),
    ),
    ...discovery.adrFiles.map((source) =>
      referencedEntity(
        manifest.metadata.id,
        source,
        "Decision",
        "decision",
        `Discovered architecture decision reference at ${source}.`,
        options.generatedAt,
      ),
    ),
    ...discovery.ciFiles.map((source) =>
      referencedEntity(
        manifest.metadata.id,
        source,
        "Resource",
        "resource",
        `Discovered continuous-integration configuration at ${source}.`,
        options.generatedAt,
      ),
    ),
  ].sort((left, right) => left.id.localeCompare(right.id));
  const sourcesOfTruth = [
    { topic: "Brownfield discovery", source: ".aifw/adoption/discovery.json" },
    ...discovery.contracts.map((source) => ({ topic: `Contract ${source}`, source })),
    ...discovery.adrFiles.map((source) => ({ topic: `Decision ${source}`, source })),
  ].sort(
    (left, right) => left.topic.localeCompare(right.topic) || left.source.localeCompare(right.source),
  );
  const payload = {
    apiVersion: "aifw.dev/v1alpha1" as const,
    kind: "BrownfieldDiscovery" as const,
    projectId: manifest.metadata.id,
    discovery,
    candidates: { sourcesOfTruth, entities },
    unknowns: [
      "Confirm module responsibilities and boundaries from code evidence.",
      "Confirm owners, runtime relationships, data flows and deployment topology.",
      "Resolve conflicting or stale documentation before marking the mapping current.",
    ],
  };
  return {
    ...payload,
    generatedAt: options.generatedAt,
    digest: digest(payload),
  };
}

export async function writeBrownfieldAnalysis(
  root: string,
  options: { generatedAt: string },
): Promise<WriteBrownfieldAnalysisResult> {
  const report = await analyzeBrownfieldProject(root, options);
  const state: BrownfieldAdoptionState = {
    apiVersion: "aifw.dev/v1alpha1",
    kind: "BrownfieldAdoption",
    projectId: report.projectId,
    status: "analyzed",
    reportDigest: report.digest,
    analyzedAt: report.generatedAt,
  };
  const adoptionDirectory = path.join(root, ".aifw", "adoption");
  await mkdir(adoptionDirectory, { recursive: true });
  await writeFile(
    path.join(adoptionDirectory, "discovery.json"),
    `${JSON.stringify(report, null, 2)}\n`,
    "utf8",
  );
  await writeFile(
    path.join(adoptionDirectory, "status.yaml"),
    stringify(state, { lineWidth: 0, sortMapEntries: false }),
    "utf8",
  );
  return {
    reportPath: ".aifw/adoption/discovery.json",
    statePath: ".aifw/adoption/status.yaml",
    report,
    state,
  };
}

export async function applyBrownfieldMapping(
  root: string,
  options: { appliedAt: string },
): Promise<ApplyBrownfieldMappingResult> {
  if (Number.isNaN(new Date(options.appliedAt).valueOf())) {
    throw new AifwError(
      "MANIFEST_INVALID",
      "Brownfield mapping requires a valid appliedAt timestamp.",
      [options.appliedAt],
    );
  }
  const [{ report, state }, catalog] = await Promise.all([
    loadBrownfieldFiles(root),
    loadWorkspaceCatalog(root),
  ]);
  const entities = new Map(catalog.entities.map((entity) => [entity.id, entity]));
  for (const candidate of report.candidates.entities) {
    const existing = entities.get(candidate.id);
    if (existing !== undefined && existing.origin !== "discovered") {
      throw new AifwError(
        "POLICY_CONFLICT",
        `Brownfield candidate ${candidate.id} conflicts with a manually governed catalog entity.`,
        [candidate.id, existing.source, candidate.source],
      );
    }
    entities.set(candidate.id, structuredClone(candidate));
  }
  const sources = new Map(
    catalog.sourcesOfTruth.map((source) => [`${source.topic}\u0000${source.source}`, source]),
  );
  for (const candidate of report.candidates.sourcesOfTruth) {
    sources.set(`${candidate.topic}\u0000${candidate.source}`, structuredClone(candidate));
  }
  catalog.entities = [...entities.values()].sort((left, right) => left.id.localeCompare(right.id));
  catalog.sourcesOfTruth = [...sources.values()].sort(
    (left, right) => left.topic.localeCompare(right.topic) || left.source.localeCompare(right.source),
  );
  catalog.project.verifiedRevision = `discovery:${report.digest.slice(0, 12)}`;

  const architecturePath = "docs/architecture/discovered.md" as const;
  await writeWorkspaceCatalog(root, catalog);
  await mkdir(path.join(root, "docs", "architecture"), { recursive: true });
  await writeFile(
    path.join(root, ...architecturePath.split("/")),
    renderDiscoveredArchitecture(report),
    "utf8",
  );
  const nextState: BrownfieldAdoptionState = {
    apiVersion: state.apiVersion,
    kind: state.kind,
    projectId: state.projectId,
    reportDigest: state.reportDigest,
    analyzedAt: state.analyzedAt,
    status: "review-required",
    appliedAt: options.appliedAt,
  };
  await writeFile(
    path.join(root, ".aifw", "adoption", "status.yaml"),
    stringify(nextState, { lineWidth: 0, sortMapEntries: false }),
    "utf8",
  );
  const projectMap = await buildWorkspaceMap(root, { write: true });
  return {
    state: nextState,
    appliedEntityIds: report.candidates.entities.map((entity) => entity.id).sort(),
    architecturePath,
    projectMap,
  };
}

export async function approveBrownfieldMapping(
  root: string,
  approval: { approvedBy: string; approvedAt: string },
): Promise<{ state: BrownfieldAdoptionState; projectMap: WorkspaceMapResult }> {
  if (
    !approval.approvedBy.startsWith("human:") ||
    Number.isNaN(new Date(approval.approvedAt).valueOf())
  ) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "Brownfield mapping approval requires a human identity and valid timestamp.",
      [approval.approvedBy, approval.approvedAt],
    );
  }
  const [{ report, state }, catalog] = await Promise.all([
    loadBrownfieldFiles(root),
    loadWorkspaceCatalog(root),
  ]);
  if (state.status !== "review-required") {
    throw new AifwError(
      "NOT_READY",
      "Apply the brownfield mapping and review its candidates before approval.",
      [state.status],
    );
  }
  const candidateIds = new Set(report.candidates.entities.map((entity) => entity.id));
  catalog.entities = catalog.entities.map((entity) =>
    candidateIds.has(entity.id) && entity.origin === "discovered"
      ? {
          ...entity,
          owner: approval.approvedBy,
          confidence: "confirmed" as const,
        }
      : entity,
  );
  const approvedEntities = catalog.entities
    .filter((entity) => candidateIds.has(entity.id))
    .sort((left, right) => left.id.localeCompare(right.id));
  if (approvedEntities.length !== candidateIds.size) {
    throw new AifwError(
      "NOT_READY",
      "The catalog no longer contains every candidate from the reviewed discovery report.",
      [...candidateIds].filter((id) => !approvedEntities.some((entity) => entity.id === id)),
    );
  }
  const contentDigest = digest({
    reportDigest: report.digest,
    entities: approvedEntities,
  });
  const nextState: BrownfieldAdoptionState = {
    ...state,
    status: "approved",
    approval: {
      approvedBy: approval.approvedBy,
      approvedAt: approval.approvedAt,
      contentDigest,
    },
  };
  await writeWorkspaceCatalog(root, catalog);
  await writeFile(
    path.join(root, ".aifw", "adoption", "status.yaml"),
    stringify(nextState, { lineWidth: 0, sortMapEntries: false }),
    "utf8",
  );
  const projectMap = await buildWorkspaceMap(root, { write: true });
  return { state: nextState, projectMap };
}

export async function assessBrownfieldAdoption(
  root: string,
): Promise<BrownfieldAdoptionAssessment> {
  const manifest = await loadWorkspaceManifest(root);
  if (manifest.spec.projectType !== "existing") {
    return {
      id: "brownfield-mapping",
      owner: "agent",
      blockingHumanApproval: false,
      status: "current",
      artifact: ".aifw/adoption/status.yaml",
      reason: "Not applicable to a new project.",
    };
  }
  try {
    const { report, state } = await loadBrownfieldFiles(root);
    if (state.status === "approved") {
      const catalog = await loadWorkspaceCatalog(root);
      const candidateIds = new Set(report.candidates.entities.map((entity) => entity.id));
      const currentEntities = catalog.entities
        .filter((entity) => candidateIds.has(entity.id))
        .sort((left, right) => left.id.localeCompare(right.id));
      const currentDigest = digest({
        reportDigest: report.digest,
        entities: currentEntities,
      });
      if (
        state.approval === undefined ||
        currentEntities.length !== candidateIds.size ||
        currentDigest !== state.approval.contentDigest
      ) {
        return {
          id: "brownfield-mapping",
          owner: "agent",
          blockingHumanApproval: true,
          status: "invalid",
          artifact: ".aifw/adoption/status.yaml",
          reason: "The approved brownfield catalog changed after its recorded content digest.",
          nextAction: "aifw adopt apply",
        };
      }
      return {
        id: "brownfield-mapping",
        owner: "agent",
        blockingHumanApproval: false,
        status: "current",
        artifact: ".aifw/adoption/status.yaml",
        reason: "The discovered mapping is applied and approved by a human.",
      };
    }
    if (state.status === "review-required") {
      return {
        id: "brownfield-mapping",
        owner: "agent",
        blockingHumanApproval: true,
        status: "review-required",
        artifact: ".aifw/adoption/status.yaml",
        reason: "Factual candidates were written and require human review.",
        nextAction: "aifw adopt approve --by human:<identity>",
      };
    }
    return {
      id: "brownfield-mapping",
      owner: "agent",
      blockingHumanApproval: false,
      status: "pending",
      artifact: ".aifw/adoption/status.yaml",
      reason: "Discovery is persisted but has not been applied to the catalog.",
      nextAction: "aifw adopt apply",
    };
  } catch (error) {
    if (error instanceof AifwError && error.code === "NOT_READY") {
      return {
        id: "brownfield-mapping",
        owner: "agent",
        blockingHumanApproval: false,
        status: "pending",
        artifact: ".aifw/adoption/status.yaml",
        reason: "No persisted brownfield discovery report exists.",
        nextAction: "aifw adopt analyze --write",
      };
    }
    return {
      id: "brownfield-mapping",
      owner: "agent",
      blockingHumanApproval: false,
      status: "invalid",
      artifact: ".aifw/adoption/status.yaml",
      reason: error instanceof Error ? error.message : String(error),
      nextAction: "aifw adopt analyze --write",
    };
  }
}
