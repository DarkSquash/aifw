import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import fg from "fast-glob";
import { parseDocument } from "yaml";

import { AifwError } from "./errors.ts";

export type PrincipleFamily = "clean-code" | "solid" | "foundational";

export interface EngineeringPrinciple {
  id: string;
  name: string;
  family: PrincipleFamily;
  statement: string;
  appliesWhen: string[];
  reviewQuestions: string[];
  evidence: string[];
  misuseRisks: string[];
  exceptions: string[];
  sources: string[];
}

export interface PrincipleCatalog {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "PrincipleCatalog";
  metadata: {
    id: string;
    version: string;
    scope: "core";
  };
  spec: {
    title: string;
    principles: EngineeringPrinciple[];
  };
}

export interface PrincipleCheck extends EngineeringPrinciple {
  principleId: string;
  applicability: "applicable" | "deferred";
  matchedSignals: string[];
}

export interface PrincipleReview {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "PrincipleReview";
  signals: string[];
  catalogs: Array<{ id: string; version: string }>;
  checks: PrincipleCheck[];
  enforcement: "contextual-review";
  digest: string;
}

export interface PrincipleReviewAssessment {
  status: "pending" | "current" | "stale" | "invalid";
  reason: string;
}

const frameworkRoot = fileURLToPath(new URL("../../", import.meta.url));
const idPattern = /^[a-z][a-z0-9.-]+$/u;

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function strings(value: unknown, minimum = 0): value is string[] {
  return (
    Array.isArray(value) &&
    value.length >= minimum &&
    value.every((item) => typeof item === "string" && item.trim().length > 0)
  );
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stableValue);
  if (record(value)) {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => [key, stableValue(nested)]),
    );
  }
  return value;
}

function digest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(stableValue(value))).digest("hex");
}

function validPrinciple(value: unknown): value is EngineeringPrinciple {
  return (
    record(value) &&
    typeof value.id === "string" &&
    idPattern.test(value.id) &&
    typeof value.name === "string" &&
    value.name.trim().length > 0 &&
    (value.family === "clean-code" ||
      value.family === "solid" ||
      value.family === "foundational") &&
    typeof value.statement === "string" &&
    value.statement.trim().length > 0 &&
    strings(value.appliesWhen) &&
    strings(value.reviewQuestions, 1) &&
    strings(value.evidence, 1) &&
    strings(value.misuseRisks, 1) &&
    strings(value.exceptions, 1) &&
    strings(value.sources, 1)
  );
}

function validCatalog(value: unknown): value is PrincipleCatalog {
  if (!record(value) || !record(value.metadata) || !record(value.spec)) return false;
  return (
    value.apiVersion === "aifw.dev/v1alpha1" &&
    value.kind === "PrincipleCatalog" &&
    typeof value.metadata.id === "string" &&
    idPattern.test(value.metadata.id) &&
    typeof value.metadata.version === "string" &&
    /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/u.test(value.metadata.version) &&
    value.metadata.scope === "core" &&
    typeof value.spec.title === "string" &&
    value.spec.title.trim().length > 0 &&
    Array.isArray(value.spec.principles) &&
    value.spec.principles.length > 0 &&
    value.spec.principles.every(validPrinciple)
  );
}

export function parsePrincipleCatalog(source: string, label: string): PrincipleCatalog {
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
    throw new AifwError("MANIFEST_INVALID", `${label} is not a valid PrincipleCatalog.`);
  }
  const catalog = structuredClone(value);
  const ids = catalog.spec.principles.map((principle) => principle.id);
  if (new Set(ids).size !== ids.length) {
    throw new AifwError("POLICY_CONFLICT", `${label} repeats a principle id.`);
  }
  return catalog;
}

export function reviewPrinciples(
  catalogs: readonly PrincipleCatalog[],
  input: { signals: string[] },
): PrincipleReview {
  if (catalogs.length === 0) {
    throw new AifwError("MANIFEST_INVALID", "No engineering principle catalog is available.");
  }
  const signals = [...new Set(input.signals)].sort();
  const signalSet = new Set(signals);
  const principles = catalogs
    .flatMap((catalog) => catalog.spec.principles)
    .sort((left, right) => left.id.localeCompare(right.id));
  const ids = principles.map((principle) => principle.id);
  if (new Set(ids).size !== ids.length) {
    throw new AifwError("POLICY_CONFLICT", "Engineering principle ids must be globally unique.");
  }
  const checks = principles.map((principle): PrincipleCheck => {
    const matchedSignals = principle.appliesWhen
      .filter((signal) => signalSet.has(signal))
      .sort();
    return {
      ...structuredClone(principle),
      principleId: principle.id,
      applicability:
        principle.appliesWhen.length === 0 || matchedSignals.length > 0
          ? "applicable"
          : "deferred",
      matchedSignals,
    };
  });
  const payload = {
    apiVersion: "aifw.dev/v1alpha1" as const,
    kind: "PrincipleReview" as const,
    signals,
    catalogs: catalogs
      .map((catalog) => ({ id: catalog.metadata.id, version: catalog.metadata.version }))
      .sort((left, right) => left.id.localeCompare(right.id)),
    checks,
    enforcement: "contextual-review" as const,
  };
  return { ...payload, digest: digest(payload) };
}

export async function loadPrincipleCatalogs(): Promise<PrincipleCatalog[]> {
  const relativePaths = await fg("principle-catalogs/*.yaml", {
    cwd: frameworkRoot,
    onlyFiles: true,
    followSymbolicLinks: false,
  });
  return Promise.all(
    relativePaths.sort().map(async (relativePath) =>
      parsePrincipleCatalog(
        await readFile(path.join(frameworkRoot, relativePath), "utf8"),
        relativePath.replaceAll("\\", "/"),
      ),
    ),
  );
}

export async function reviewWorkspacePrinciples(
  root: string,
  input: { signals: string[]; write: boolean },
): Promise<PrincipleReview> {
  const review = reviewPrinciples(await loadPrincipleCatalogs(), input);
  if (input.write) {
    const directory = path.join(root, ".aifw", "reviews");
    await mkdir(directory, { recursive: true });
    await writeFile(
      path.join(directory, "engineering-principles.json"),
      `${JSON.stringify(review, null, 2)}\n`,
      "utf8",
    );
  }
  return review;
}

export async function assessWorkspacePrincipleReview(
  root: string,
): Promise<PrincipleReviewAssessment> {
  const reviewPath = path.join(root, ".aifw", "reviews", "engineering-principles.json");
  let source: string;
  try {
    source = await readFile(reviewPath, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return {
        status: "pending",
        reason: "No contextual engineering-principles review has been recorded yet.",
      };
    }
    throw error;
  }

  let stored: unknown;
  try {
    stored = JSON.parse(source) as unknown;
  } catch {
    return {
      status: "invalid",
      reason: "The recorded engineering-principles review is not valid JSON.",
    };
  }
  if (
    !record(stored) ||
    stored.kind !== "PrincipleReview" ||
    !strings(stored.signals) ||
    typeof stored.digest !== "string"
  ) {
    return {
      status: "invalid",
      reason: "The recorded engineering-principles review does not match its contract.",
    };
  }

  const expected = reviewPrinciples(await loadPrincipleCatalogs(), {
    signals: stored.signals,
  });
  if (JSON.stringify(stableValue(stored)) !== JSON.stringify(stableValue(expected))) {
    return {
      status: "stale",
      reason: "The review no longer matches its signals or the active principle catalogs.",
    };
  }
  return {
    status: "current",
    reason: "The contextual engineering-principles review matches the active catalogs.",
  };
}
