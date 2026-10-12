import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import fg from "fast-glob";
import { parseDocument, stringify } from "yaml";

import { AifwError } from "./errors.ts";
import { loadWorkspaceManifest } from "./workspace.ts";

export type DecisionScope = "core" | "profile";
export type DecisionImpact = "L1" | "L2" | "L3";

export interface DecisionDriver {
  id: string;
  prompt: string;
  signals: string[];
}

export interface DecisionCriterion {
  signal: string;
  effect: "prefer" | "avoid";
  weight: number;
  reason: string;
}

export interface DecisionOption {
  id: string;
  name: string;
  summary: string;
  status: "recommended" | "supported" | "specialized" | "discouraged";
  maturity: "stable" | "evolving" | "legacy";
  criteria: DecisionCriterion[];
  tradeoffs: string[];
  requires: string[];
  conflicts: string[];
  sources: string[];
}

export interface DecisionCatalog {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "DecisionCatalog";
  metadata: {
    id: string;
    version: string;
    category: string;
    scope: DecisionScope;
    impact: DecisionImpact;
  };
  spec: {
    title: string;
    drivers: DecisionDriver[];
    options: DecisionOption[];
  };
}

export interface DecisionRecommendationInput {
  category: string;
  signals: string[];
  selectedOptionIds: string[];
}

export interface DecisionRanking {
  optionId: string;
  name: string;
  score: number;
  eligible: boolean;
  reasons: string[];
  conflicts: string[];
  tradeoffs: string[];
  sources: string[];
}

export interface DecisionRecommendation {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "DecisionCase";
  category: string;
  impact: DecisionImpact;
  signals: string[];
  selectedOptionIds: string[];
  catalogs: Array<{ id: string; version: string; scope: DecisionScope }>;
  rankings: DecisionRanking[];
  unansweredDrivers: DecisionDriver[];
  confidence: "low" | "medium" | "high";
  requiresHumanApproval: true;
  recordRequired: "ADR";
  digest: string;
}

export interface DecisionRecord {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "DecisionRecord";
  category: string;
  optionId: string;
  status: "accepted";
  recommendationDigest: string;
  approvedBy: string;
  approvedAt: string;
  adr: { path: string; digest: string };
}

const frameworkRoot = fileURLToPath(new URL("../../", import.meta.url));
const idPattern = /^[a-z][a-z0-9.-]+$/u;

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
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

function validDriver(value: unknown): value is DecisionDriver {
  return (
    record(value) &&
    typeof value.id === "string" &&
    idPattern.test(value.id) &&
    typeof value.prompt === "string" &&
    value.prompt.trim().length > 0 &&
    strings(value.signals) &&
    value.signals.length >= 2
  );
}

function validCriterion(value: unknown): value is DecisionCriterion {
  return (
    record(value) &&
    typeof value.signal === "string" &&
    (value.effect === "prefer" || value.effect === "avoid") &&
    Number.isInteger(value.weight) &&
    typeof value.weight === "number" &&
    value.weight >= 1 &&
    value.weight <= 5 &&
    typeof value.reason === "string" &&
    value.reason.trim().length > 0
  );
}

function validOption(value: unknown): value is DecisionOption {
  return (
    record(value) &&
    typeof value.id === "string" &&
    idPattern.test(value.id) &&
    typeof value.name === "string" &&
    value.name.trim().length > 0 &&
    typeof value.summary === "string" &&
    value.summary.trim().length > 0 &&
    typeof value.status === "string" &&
    ["recommended", "supported", "specialized", "discouraged"].includes(value.status) &&
    typeof value.maturity === "string" &&
    ["stable", "evolving", "legacy"].includes(value.maturity) &&
    Array.isArray(value.criteria) &&
    value.criteria.every(validCriterion) &&
    strings(value.tradeoffs) &&
    value.tradeoffs.length > 0 &&
    strings(value.requires) &&
    strings(value.conflicts) &&
    strings(value.sources) &&
    value.sources.length > 0
  );
}

function validCatalog(value: unknown): value is DecisionCatalog {
  if (!record(value) || !record(value.metadata) || !record(value.spec)) return false;
  return (
    value.apiVersion === "aifw.dev/v1alpha1" &&
    value.kind === "DecisionCatalog" &&
    typeof value.metadata.id === "string" &&
    idPattern.test(value.metadata.id) &&
    typeof value.metadata.version === "string" &&
    /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/u.test(value.metadata.version) &&
    typeof value.metadata.category === "string" &&
    idPattern.test(value.metadata.category) &&
    (value.metadata.scope === "core" || value.metadata.scope === "profile") &&
    (value.metadata.impact === "L1" ||
      value.metadata.impact === "L2" ||
      value.metadata.impact === "L3") &&
    typeof value.spec.title === "string" &&
    Array.isArray(value.spec.drivers) &&
    value.spec.drivers.every(validDriver) &&
    Array.isArray(value.spec.options) &&
    value.spec.options.length > 0 &&
    value.spec.options.every(validOption)
  );
}

export function parseDecisionCatalog(source: string, label: string): DecisionCatalog {
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
  if (!validCatalog(value)) {
    throw new AifwError("MANIFEST_INVALID", `${label} is not a valid DecisionCatalog.`);
  }
  const catalog = structuredClone(value);
  const driverIds = catalog.spec.drivers.map((driver) => driver.id);
  const optionIds = catalog.spec.options.map((option) => option.id);
  if (new Set(driverIds).size !== driverIds.length || new Set(optionIds).size !== optionIds.length) {
    throw new AifwError("POLICY_CONFLICT", `${label} repeats a driver or option id.`);
  }
  return catalog;
}

export function recommendDecision(
  catalogs: readonly DecisionCatalog[],
  input: DecisionRecommendationInput,
): DecisionRecommendation {
  const selectedCatalogs = catalogs
    .filter((catalog) => catalog.metadata.category === input.category)
    .sort((left, right) => left.metadata.id.localeCompare(right.metadata.id));
  if (selectedCatalogs.length === 0) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `No decision catalog exists for category ${input.category}.`,
    );
  }
  const options = selectedCatalogs.flatMap((catalog) => catalog.spec.options);
  const optionIds = options.map((option) => option.id);
  if (new Set(optionIds).size !== optionIds.length) {
    throw new AifwError(
      "POLICY_CONFLICT",
      `Decision category ${input.category} contains duplicate option ids.`,
    );
  }
  const signals = [...new Set(input.signals)].sort();
  const selectedOptionIds = [...new Set(input.selectedOptionIds)].sort();
  const signalSet = new Set(signals);
  const selectedSet = new Set(selectedOptionIds);
  const rankings = options
    .map((option): DecisionRanking => {
      const conflicts = option.conflicts.filter((conflict) => selectedSet.has(conflict)).sort();
      const missingRequirements = option.requires.filter(
        (requirement) => !selectedSet.has(requirement) && !signalSet.has(requirement),
      );
      const reasons: string[] = [];
      let score = 0;
      for (const criterion of option.criteria) {
        if (!signalSet.has(criterion.signal)) continue;
        const delta = criterion.effect === "prefer" ? criterion.weight : -criterion.weight;
        score += delta;
        reasons.push(
          `${delta >= 0 ? "+" : ""}${String(delta)} ${criterion.signal}: ${criterion.reason}`,
        );
      }
      if (missingRequirements.length > 0) {
        reasons.push(`missing requirements: ${missingRequirements.join(", ")}`);
      }
      if (conflicts.length > 0) reasons.push(`conflicts: ${conflicts.join(", ")}`);
      return {
        optionId: option.id,
        name: option.name,
        score,
        eligible: conflicts.length === 0 && missingRequirements.length === 0,
        reasons,
        conflicts,
        tradeoffs: [...option.tradeoffs],
        sources: [...option.sources],
      };
    })
    .sort((left, right) => {
      if (left.eligible !== right.eligible) return left.eligible ? -1 : 1;
      if (left.score !== right.score) return right.score - left.score;
      return left.optionId.localeCompare(right.optionId);
    });
  const drivers = new Map<string, DecisionDriver>();
  for (const catalog of selectedCatalogs) {
    for (const driver of catalog.spec.drivers) {
      const previous = drivers.get(driver.id);
      if (previous !== undefined && digest(previous) !== digest(driver)) {
        throw new AifwError(
          "POLICY_CONFLICT",
          `Decision driver ${driver.id} has conflicting definitions.`,
        );
      }
      drivers.set(driver.id, structuredClone(driver));
    }
  }
  const unansweredDrivers = [...drivers.values()]
    .filter((driver) => !driver.signals.some((signal) => signalSet.has(signal)))
    .sort((left, right) => left.id.localeCompare(right.id));
  const top = rankings.find((ranking) => ranking.eligible);
  const confidence: DecisionRecommendation["confidence"] =
    signals.length === 0 || top === undefined || top.score <= 0
      ? "low"
      : unansweredDrivers.length === 0 && top.score >= 4
        ? "high"
        : "medium";
  const payload = {
    apiVersion: "aifw.dev/v1alpha1" as const,
    kind: "DecisionCase" as const,
    category: input.category,
    impact: selectedCatalogs.reduce<DecisionImpact>(
      (highest, catalog) => {
        const order: DecisionImpact[] = ["L1", "L2", "L3"];
        return order.indexOf(catalog.metadata.impact) > order.indexOf(highest)
          ? catalog.metadata.impact
          : highest;
      },
      "L1",
    ),
    signals,
    selectedOptionIds,
    catalogs: selectedCatalogs.map((catalog) => ({
      id: catalog.metadata.id,
      version: catalog.metadata.version,
      scope: catalog.metadata.scope,
    })),
    rankings,
    unansweredDrivers,
    confidence,
    requiresHumanApproval: true as const,
    recordRequired: "ADR" as const,
  };
  return { ...payload, digest: digest(payload) };
}

export async function loadWorkspaceDecisionCatalogs(
  root: string,
): Promise<DecisionCatalog[]> {
  const manifest = await loadWorkspaceManifest(root);
  const relativePaths = [
    ...(await fg("decision-catalogs/*.yaml", {
      cwd: frameworkRoot,
      onlyFiles: true,
      followSymbolicLinks: false,
    })),
    ...(
      await Promise.all(
        manifest.spec.profiles.map((profileId) =>
          fg(`profiles/${profileId}/decisions/*.yaml`, {
            cwd: frameworkRoot,
            onlyFiles: true,
            followSymbolicLinks: false,
          }),
        ),
      )
    ).flat(),
  ].sort();
  return Promise.all(
    relativePaths.map(async (relativePath) =>
      parseDecisionCatalog(
        await readFile(path.join(frameworkRoot, relativePath), "utf8"),
        relativePath.replaceAll("\\", "/"),
      ),
    ),
  );
}

export async function recommendWorkspaceDecision(
  root: string,
  input: DecisionRecommendationInput & { write: boolean },
): Promise<DecisionRecommendation> {
  const result = recommendDecision(await loadWorkspaceDecisionCatalogs(root), input);
  if (input.write) {
    const directory = path.join(root, ".aifw", "decision-cases");
    await mkdir(directory, { recursive: true });
    await writeFile(
      path.join(directory, `${input.category}.json`),
      `${JSON.stringify(result, null, 2)}\n`,
      "utf8",
    );
  }
  return result;
}

export async function approveWorkspaceDecision(
  root: string,
  input: {
    category: string;
    optionId: string;
    approvedBy: string;
    approvedAt: string;
    adrPath: string;
  },
): Promise<DecisionRecord> {
  if (!input.approvedBy.startsWith("human:")) {
    throw new AifwError(
      "APPROVAL_REQUIRED",
      "An architectural decision requires human approval.",
    );
  }
  if (Number.isNaN(Date.parse(input.approvedAt))) {
    throw new AifwError("MANIFEST_INVALID", "Decision approval time must be ISO-8601.");
  }
  const casePath = path.join(root, ".aifw", "decision-cases", `${input.category}.json`);
  const decisionCase = JSON.parse(await readFile(casePath, "utf8")) as DecisionRecommendation;
  const { digest: storedDigest, ...casePayload } = decisionCase;
  if (storedDigest !== digest(casePayload)) {
    throw new AifwError("POLICY_CONFLICT", "The persisted decision case digest is invalid.");
  }
  const ranking = decisionCase.rankings.find(
    (candidate) => candidate.optionId === input.optionId,
  );
  if (ranking === undefined || !ranking.eligible) {
    throw new AifwError(
      "POLICY_CONFLICT",
      `Decision option ${input.optionId} is not eligible in the persisted case.`,
    );
  }
  const resolvedRoot = path.resolve(root);
  const resolvedAdr = path.resolve(resolvedRoot, input.adrPath);
  const relativeAdr = path.relative(resolvedRoot, resolvedAdr);
  if (relativeAdr.startsWith("..") || path.isAbsolute(relativeAdr)) {
    throw new AifwError("POLICY_CONFLICT", "The ADR must be stored inside the project.");
  }
  const adrSource = await readFile(resolvedAdr, "utf8");
  const record: DecisionRecord = {
    apiVersion: "aifw.dev/v1alpha1",
    kind: "DecisionRecord",
    category: input.category,
    optionId: input.optionId,
    status: "accepted",
    recommendationDigest: storedDigest,
    approvedBy: input.approvedBy,
    approvedAt: new Date(input.approvedAt).toISOString(),
    adr: {
      path: relativeAdr.replaceAll("\\", "/"),
      digest: createHash("sha256").update(adrSource).digest("hex"),
    },
  };
  const decisionDirectory = path.join(root, ".aifw", "decisions");
  await mkdir(decisionDirectory, { recursive: true });
  await writeFile(
    path.join(decisionDirectory, `${input.category}.yaml`),
    stringify(record, { lineWidth: 0, sortMapEntries: false }),
    "utf8",
  );
  return record;
}
