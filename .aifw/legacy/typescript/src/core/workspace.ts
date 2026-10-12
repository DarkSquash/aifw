import { access, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { parseDocument, stringify } from "yaml";

import type {
  PrimaryEnvironment,
  ProjectManifest,
  ProjectType,
  ValidationTarget,
} from "./config.ts";
import { parseProjectManifest } from "./config.ts";
import { AifwError } from "./errors.ts";
import {
  buildProjectMap,
  checkProjectMap,
  type CatalogEntity,
} from "./project-map.ts";

export const FRAMEWORK_VERSION = "0.2.0";

export interface InitializeProjectOptions {
  id: string;
  name: string;
  projectType: ProjectType;
  locale: string;
  primaryEnvironment: PrimaryEnvironment;
  validationTargets: ValidationTarget[];
  profiles?: string[];
}

export interface InitializeProjectResult {
  createdFiles: string[];
  manifest: ProjectManifest;
}

export interface WorkspaceCatalog {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "ProjectCatalog";
  project: {
    purpose: string;
    verifiedRevision: string;
  };
  sourcesOfTruth: Array<{ topic: string; source: string }>;
  entities: CatalogEntity[];
}

export interface WorkspaceMapResult {
  current: boolean;
  digest: string;
  markdown: string;
  outputPath: string;
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

function parseYamlObject<T>(source: string, label: string): T {
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
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new AifwError("MANIFEST_INVALID", `${label} must be a YAML object.`);
  }
  return value as T;
}

function validateCatalog(value: WorkspaceCatalog): WorkspaceCatalog {
  if (
    value.apiVersion !== "aifw.dev/v1alpha1" ||
    value.kind !== "ProjectCatalog" ||
    typeof value.project?.purpose !== "string" ||
    typeof value.project?.verifiedRevision !== "string" ||
    !Array.isArray(value.sourcesOfTruth) ||
    !Array.isArray(value.entities)
  ) {
    throw new AifwError(
      "MANIFEST_INVALID",
      ".aifw/catalog.yaml does not match the ProjectCatalog contract.",
    );
  }
  return value;
}

export async function loadWorkspaceCatalog(root: string): Promise<WorkspaceCatalog> {
  return validateCatalog(
    parseYamlObject<WorkspaceCatalog>(
      await readFile(path.join(root, ".aifw", "catalog.yaml"), "utf8"),
      ".aifw/catalog.yaml",
    ),
  );
}

export async function writeWorkspaceCatalog(
  root: string,
  catalog: WorkspaceCatalog,
): Promise<void> {
  validateCatalog(catalog);
  await writeFile(
    path.join(root, ".aifw", "catalog.yaml"),
    yaml(catalog),
    "utf8",
  );
}

function createScaffoldFiles(options: InitializeProjectOptions): Record<string, string> {
  const manifest: ProjectManifest = {
    apiVersion: "aifw.dev/v1alpha1",
    kind: "Project",
    metadata: { id: options.id, name: options.name },
    spec: {
      frameworkVersion: FRAMEWORK_VERSION,
      projectType: options.projectType,
      locale: options.locale,
      primaryEnvironment: options.primaryEnvironment,
      validationTargets: [...new Set(options.validationTargets)],
      profiles: [...new Set(options.profiles ?? [])],
      dataClassification: "internal",
      externalAllowlist: [],
    },
  };

  return {
    "aifw.yaml": yaml(manifest),
    ".aifw/charter.yaml": yaml({
      id: options.id,
      version: "0.1.0",
      projectType: options.projectType,
      problem: "",
      audiences: [],
      outcomes: [],
      scope: { in: [], out: [] },
      constraints: [],
      technicalPreference: { mode: "agent-recommend" },
      unknowns: [],
      state: "draft",
    }),
    ".aifw/catalog.yaml": yaml({
      apiVersion: "aifw.dev/v1alpha1",
      kind: "ProjectCatalog",
      project: {
        purpose: "Pending Project Charter approval.",
        verifiedRevision: "working-tree",
      },
      sourcesOfTruth: [
        { topic: "Project intent", source: ".aifw/charter.yaml" },
        { topic: "Framework configuration", source: "aifw.yaml" },
        { topic: "Architecture decisions", source: "docs/adr/" },
        { topic: "Approved architecture selections", source: ".aifw/decisions/" },
        { topic: "Approved capability specs", source: ".aifw/specs/current/" },
        { topic: "Interface contracts", source: "contracts/" },
      ],
      entities: [
        {
          id: `system:${options.id}`,
          kind: "System",
          name: options.name,
          description: "Top-level system; refine during discovery.",
          owner: "human:owner",
          source: ".aifw/charter.yaml",
          visibility: "internal",
          relations: [],
        },
      ],
    } satisfies WorkspaceCatalog),
    ".aifw/routing.yaml": yaml({
      apiVersion: "aifw.dev/v1alpha1",
      kind: "RoutingPolicy",
      enabled: false,
      mode: "recommendation-only",
      aliases: { FAST: "Luna", WORK: "Terra", BRAIN: "Sol" },
      targets: {
        FAST: { provider: "openai-codex", model: "gpt-5.6-luna" },
        WORK: { provider: "openai-codex", model: "gpt-5.6-terra" },
        BRAIN: { provider: "openai-codex", model: "gpt-5.6-sol" },
      },
      activation: {
        minimumCases: 30,
        minimumPassRate: 0.95,
        criticalFailures: 0,
        humanApprovalRequired: true,
      },
    }),
    ".aifw/permissions.yaml": yaml({
      apiVersion: "aifw.dev/v1alpha1",
      kind: "PermissionPolicy",
      localGit: "autonomous",
      remoteMutation: "human-approval",
      previewDeployment: "autonomous",
      productionDeployment: "human-approval",
      destructiveChanges: "human-approval",
      childAgents: { capabilityCeiling: "parent" },
      breakGlass: {
        enabled: true,
        requiresIncidentId: true,
        requiresHumanApproval: true,
        expires: true,
      },
    }),
    ".aifw/gates.yaml": yaml({
      apiVersion: "aifw.dev/v1alpha1",
      kind: "QualityGateSet",
      philosophy: "progressive-by-risk",
      gates: [
        { id: "manifest", enforcement: "hard", levels: ["L0", "L1", "L2", "L3"] },
        { id: "project-map", enforcement: "hard", levels: ["L1", "L2", "L3"] },
        { id: "tests", enforcement: "hard", levels: ["L1", "L2", "L3"] },
        { id: "independent-review", enforcement: "audit", levels: ["L2", "L3"] },
        { id: "human-approval", enforcement: "human", levels: ["L3"] },
      ],
    }),
    ".aifw/framework.lock.yaml": yaml({
      apiVersion: "aifw.dev/v1alpha1",
      kind: "FrameworkLock",
      frameworkVersion: FRAMEWORK_VERSION,
      profiles: [],
      resolutionDigest: "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
      generatedBy: `aifw/${FRAMEWORK_VERSION}`,
    }),
    "docs/adr/README.md": "# Architecture Decision Records\n\nPersist every architectural decision here. A conversation with an AI is never a source of truth.\n",
    "docs/runbooks/README.md": "# Runbooks\n\nOperational diagnosis, mitigation, rollback and recovery procedures live here.\n",
    "contracts/README.md": "# Contracts\n\nStore versioned OpenAPI, AsyncAPI, GraphQL or other machine-readable interface contracts here.\n",
    ".aifw/specs/current/README.md": "# Current capability specs\n\nAccepted, executable capability specifications are the current product truth. Active proposals never modify this directory directly.\n",
    ".aifw/changes/active/README.md": "# Active changes\n\nEach non-trivial change owns a directory with proposal, design, tasks, capability deltas, traceability and evidence.\n",
    ".aifw/changes/archive/README.md": "# Archived changes\n\nCompleted change context is retained here after validated, atomic synchronization with current capability specs.\n",
    ".aifw/adoption/README.md": "# Existing-project adoption\n\nBrownfield discovery is factual and reviewable: analyze first, apply candidates second, then require explicit human approval.\n",
  };
}

export async function initializeProject(
  root: string,
  options: InitializeProjectOptions,
): Promise<InitializeProjectResult> {
  const files = createScaffoldFiles(options);
  const manifest = parseProjectManifest(files["aifw.yaml"] ?? "");
  const conflictPaths: string[] = [];
  for (const relativePath of Object.keys(files)) {
    if (await exists(path.join(root, relativePath))) conflictPaths.push(relativePath);
  }
  if (await exists(path.join(root, "PROJECT_MAP.md"))) {
    conflictPaths.push("PROJECT_MAP.md");
  }
  if (conflictPaths.length > 0) {
    throw new AifwError(
      "POLICY_CONFLICT",
      "Initialization would overwrite existing framework files.",
      conflictPaths.sort(),
    );
  }

  const createdFiles: string[] = [];
  for (const [relativePath, content] of Object.entries(files)) {
    const absolutePath = path.join(root, relativePath);
    await mkdir(path.dirname(absolutePath), { recursive: true });
    await writeFile(absolutePath, content, { encoding: "utf8", flag: "wx" });
    createdFiles.push(relativePath.replaceAll("\\", "/"));
  }
  const map = await buildWorkspaceMap(root, { write: true });
  createdFiles.push(path.relative(root, map.outputPath).replaceAll("\\", "/"));

  return { createdFiles: createdFiles.sort(), manifest };
}

export async function loadWorkspaceManifest(root: string): Promise<ProjectManifest> {
  return parseProjectManifest(await readFile(path.join(root, "aifw.yaml"), "utf8"));
}

export async function updateWorkspacePurpose(
  root: string,
  purpose: string,
): Promise<void> {
  const catalogPath = path.join(root, ".aifw", "catalog.yaml");
  const catalog = await loadWorkspaceCatalog(root);
  catalog.project.purpose = purpose.trim();
  await writeFile(catalogPath, yaml(catalog), "utf8");
}

export async function buildWorkspaceMap(
  root: string,
  options: { write: boolean },
): Promise<WorkspaceMapResult> {
  const [manifest, catalog] = await Promise.all([
    loadWorkspaceManifest(root),
    loadWorkspaceCatalog(root),
  ]);
  const generated = buildProjectMap({
    project: manifest.metadata,
    purpose: catalog.project.purpose,
    frameworkVersion: manifest.spec.frameworkVersion,
    verifiedRevision: catalog.project.verifiedRevision,
    entities: catalog.entities,
    sourcesOfTruth: catalog.sourcesOfTruth,
  });
  const outputPath = path.join(root, "PROJECT_MAP.md");
  let currentSource = "";
  try {
    currentSource = await readFile(outputPath, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
  }
  let current = checkProjectMap(currentSource, generated).current;
  if (options.write && !current) {
    await writeFile(outputPath, generated.markdown, "utf8");
    current = true;
  }

  return {
    current,
    digest: generated.digest,
    markdown: generated.markdown,
    outputPath,
  };
}
