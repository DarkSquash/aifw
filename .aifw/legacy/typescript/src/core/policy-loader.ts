import { access, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import semver from "semver";
import { parseDocument, stringify } from "yaml";

import { AifwError } from "./errors.ts";
import {
  resolveFramework,
  type FrameworkResolution,
  type PolicyRule,
  type ProfileManifest,
} from "./resolution.ts";
import { loadWorkspaceManifest } from "./workspace.ts";

interface PolicySet {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "PolicySet";
  metadata: { id: string; version: string };
  rules: PolicyRule[];
}

interface ProfileDocument {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "Profile";
  metadata: { id: string; version: string };
  spec: {
    kind: "capability" | "stack";
    provides: string[];
    requires: string[];
    conflicts: string[];
    rules: PolicyRule[];
  };
}

export interface WorkspaceResolutionResult {
  current: boolean;
  resolution: FrameworkResolution;
  effectivePolicyPath: string;
  lockPath: string;
}

const frameworkRoot = fileURLToPath(new URL("../../", import.meta.url));

function parseYaml<T>(source: string, label: string): T {
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
    throw new AifwError("MANIFEST_INVALID", `${label} must contain a YAML object.`);
  }
  return value as T;
}

function arrayOfStrings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function validateRule(rule: PolicyRule, label: string): void {
  const valid =
    typeof rule?.id === "string" &&
    /^[a-z][a-z0-9.-]+$/u.test(rule.id) &&
    semver.valid(rule.version) !== null &&
    ["MUST", "MUST_NOT", "SHOULD", "MAY"].includes(rule.keyword) &&
    typeof rule.statement === "string" &&
    rule.statement.trim().length > 0 &&
    arrayOfStrings(rule.scope) &&
    typeof rule.rationale === "string" &&
    typeof rule.owner === "string" &&
    ["hard", "audit", "human"].includes(rule.enforcement?.mode) &&
    arrayOfStrings(rule.enforcement?.evidence) &&
    typeof rule.source === "string" &&
    typeof rule.overridable === "boolean";

  if (!valid) {
    throw new AifwError(
      "MANIFEST_INVALID",
      `${label} contains an invalid policy rule${rule?.id ? `: ${rule.id}` : "."}`,
    );
  }
}

export function parsePolicySet(source: string, label: string): PolicySet {
  const value = parseYaml<PolicySet>(source, label);
  if (
    value.apiVersion !== "aifw.dev/v1alpha1" ||
    value.kind !== "PolicySet" ||
    typeof value.metadata?.id !== "string" ||
    semver.valid(value.metadata?.version) === null ||
    !Array.isArray(value.rules)
  ) {
    throw new AifwError("MANIFEST_INVALID", `${label} is not a valid PolicySet.`);
  }
  const seen = new Set<string>();
  for (const rule of value.rules) {
    validateRule(rule, label);
    if (seen.has(rule.id)) {
      throw new AifwError(
        "POLICY_CONFLICT",
        `${label} repeats rule id ${rule.id}.`,
        [rule.id],
      );
    }
    seen.add(rule.id);
  }
  return structuredClone(value);
}

export function parseProfile(source: string, label: string): ProfileManifest {
  const value = parseYaml<ProfileDocument>(source, label);
  if (
    value.apiVersion !== "aifw.dev/v1alpha1" ||
    value.kind !== "Profile" ||
    typeof value.metadata?.id !== "string" ||
    semver.valid(value.metadata?.version) === null ||
    !["capability", "stack"].includes(value.spec?.kind) ||
    !arrayOfStrings(value.spec?.provides) ||
    !arrayOfStrings(value.spec?.requires) ||
    !arrayOfStrings(value.spec?.conflicts) ||
    !Array.isArray(value.spec?.rules)
  ) {
    throw new AifwError("MANIFEST_INVALID", `${label} is not a valid Profile.`);
  }
  for (const rule of value.spec.rules) validateRule(rule, label);
  return {
    id: value.metadata.id,
    version: value.metadata.version,
    kind: value.spec.kind,
    provides: [...value.spec.provides],
    requires: [...value.spec.requires],
    conflicts: [...value.spec.conflicts],
    rules: structuredClone(value.spec.rules),
  };
}

async function optionalPolicySet(filePath: string): Promise<PolicyRule[]> {
  try {
    await access(filePath);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }
  return parsePolicySet(await readFile(filePath, "utf8"), filePath).rules;
}

function normalize(source: string): string {
  return source.replaceAll("\r\n", "\n").trimEnd();
}

async function currentFile(filePath: string, expected: string): Promise<boolean> {
  try {
    return normalize(await readFile(filePath, "utf8")) === normalize(expected);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

export async function resolveWorkspace(
  root: string,
  options: { personalPolicyPath?: string; write: boolean },
): Promise<WorkspaceResolutionResult> {
  const manifest = await loadWorkspaceManifest(root);
  const corePath = path.join(frameworkRoot, "policies", "core.yaml");
  const coreRules = parsePolicySet(await readFile(corePath, "utf8"), corePath).rules;
  const personalRules = options.personalPolicyPath
    ? await optionalPolicySet(options.personalPolicyPath)
    : [];
  const profiles = await Promise.all(
    manifest.spec.profiles.map(async (id) => {
      const profilePath = path.join(frameworkRoot, "profiles", id, "profile.yaml");
      return parseProfile(await readFile(profilePath, "utf8"), profilePath);
    }),
  );
  const projectRules = await optionalPolicySet(
    path.join(root, ".aifw", "project-rules.yaml"),
  );
  const resolution = resolveFramework({
    coreRules,
    personalRules,
    profiles,
    projectRules,
  });

  const effective = `${JSON.stringify(
    {
      apiVersion: "aifw.dev/v1alpha1",
      kind: "EffectivePolicy",
      projectId: manifest.metadata.id,
      frameworkVersion: manifest.spec.frameworkVersion,
      rules: resolution.rules,
      profileLock: resolution.profileLock,
    },
    null,
    2,
  )}\n`;
  const lock = stringify(
    {
      apiVersion: "aifw.dev/v1alpha1",
      kind: "FrameworkLock",
      frameworkVersion: manifest.spec.frameworkVersion,
      profiles: resolution.profileLock.profiles,
      resolutionDigest: resolution.profileLock.digest,
      generatedBy: `aifw/${manifest.spec.frameworkVersion}`,
    },
    { lineWidth: 0 },
  );
  const effectivePolicyPath = path.join(root, ".aifw", "effective-policy.json");
  const lockPath = path.join(root, ".aifw", "framework.lock.yaml");
  let current =
    (await currentFile(effectivePolicyPath, effective)) &&
    (await currentFile(lockPath, lock));
  if (options.write && !current) {
    await writeFile(effectivePolicyPath, effective, "utf8");
    await writeFile(lockPath, lock, "utf8");
    current = true;
  }

  return { current, resolution, effectivePolicyPath, lockPath };
}
