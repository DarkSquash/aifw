import { createHash } from "node:crypto";

import { AifwError } from "./errors.ts";

export type PolicyKeyword = "MUST" | "MUST_NOT" | "SHOULD" | "MAY";
export type EnforcementMode = "hard" | "audit" | "human";

export interface PolicyRule {
  id: string;
  version: string;
  keyword: PolicyKeyword;
  statement: string;
  scope: string[];
  rationale: string;
  owner: string;
  enforcement: {
    mode: EnforcementMode;
    evidence: string[];
  };
  source: string;
  overridable: boolean;
}

export interface ProfileManifest {
  id: string;
  version: string;
  kind: "capability" | "stack";
  provides: string[];
  requires: string[];
  conflicts: string[];
  rules: PolicyRule[];
}

export type RuleOrigin =
  | "core"
  | "personal"
  | `capability:${string}`
  | `stack:${string}`
  | "project";

export interface EffectivePolicyRule extends PolicyRule {
  origin: RuleOrigin;
}

export interface FrameworkResolutionInput {
  coreRules: PolicyRule[];
  personalRules: PolicyRule[];
  profiles: ProfileManifest[];
  projectRules: PolicyRule[];
}

export interface ProfileLockEntry {
  id: string;
  version: string;
  kind: ProfileManifest["kind"];
  digest: string;
}

export interface ProfileLock {
  profiles: ProfileLockEntry[];
  digest: string;
}

export interface FrameworkResolution {
  rules: EffectivePolicyRule[];
  profileLock: ProfileLock;
}

function stableValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(stableValue);
  }
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

function originPriority(origin: RuleOrigin): number {
  if (origin === "core") return 0;
  if (origin === "personal") return 1;
  if (origin.startsWith("capability:")) return 2;
  if (origin.startsWith("stack:")) return 3;
  return 4;
}

function sameRule(left: PolicyRule, right: PolicyRule): boolean {
  return digest(left) === digest(right);
}

function validateProfiles(profiles: readonly ProfileManifest[]): void {
  const selected = new Set(profiles.map((profile) => profile.id));
  const provided = new Set(profiles.flatMap((profile) => profile.provides));

  for (const profile of profiles) {
    for (const conflict of profile.conflicts) {
      if (selected.has(conflict)) {
        throw new AifwError(
          "PROFILE_CONFLICT",
          `Profile ${profile.id} conflicts with ${conflict}`,
          [profile.id, conflict],
        );
      }
    }
    for (const requirement of profile.requires) {
      if (!provided.has(requirement)) {
        throw new AifwError(
          "PROFILE_CONFLICT",
          `Profile ${profile.id} requires missing capability ${requirement}`,
          [profile.id, requirement],
        );
      }
    }
  }
}

function addRule(
  effective: Map<string, EffectivePolicyRule>,
  rule: PolicyRule,
  origin: RuleOrigin,
): void {
  const current = effective.get(rule.id);
  const candidate: EffectivePolicyRule = { ...structuredClone(rule), origin };

  if (current === undefined) {
    effective.set(rule.id, candidate);
    return;
  }

  if (current.origin === "core" && !current.overridable) {
    if (!sameRule(current, rule)) {
      throw new AifwError(
        "POLICY_CONFLICT",
        `Core invariant ${rule.id} cannot be overridden by ${origin}`,
        [rule.id, current.origin, origin],
      );
    }
    return;
  }

  const currentPriority = originPriority(current.origin);
  const candidatePriority = originPriority(origin);

  if (candidatePriority === currentPriority && !sameRule(current, rule)) {
    throw new AifwError(
      "POLICY_CONFLICT",
      `Rule ${rule.id} has conflicting definitions at the same authority level`,
      [rule.id, current.origin, origin],
    );
  }

  if (candidatePriority > currentPriority) {
    effective.set(rule.id, candidate);
  }
}

function createProfileLock(profiles: readonly ProfileManifest[]): ProfileLock {
  const entries = profiles
    .map((profile) => ({
      id: profile.id,
      version: profile.version,
      kind: profile.kind,
      digest: digest(profile),
    }))
    .sort((left, right) => left.id.localeCompare(right.id));

  return {
    profiles: entries,
    digest: digest(entries),
  };
}

export function resolveFramework(
  input: FrameworkResolutionInput,
): FrameworkResolution {
  validateProfiles(input.profiles);
  const effective = new Map<string, EffectivePolicyRule>();

  for (const rule of input.coreRules) addRule(effective, rule, "core");
  for (const rule of input.personalRules) addRule(effective, rule, "personal");

  const profiles = [...input.profiles].sort((left, right) => {
    const kindOrder = left.kind === right.kind ? 0 : left.kind === "capability" ? -1 : 1;
    return kindOrder || left.id.localeCompare(right.id);
  });
  for (const profile of profiles) {
    const origin: RuleOrigin = `${profile.kind}:${profile.id}`;
    for (const rule of profile.rules) addRule(effective, rule, origin);
  }

  for (const rule of input.projectRules) addRule(effective, rule, "project");

  return {
    rules: [...effective.values()].sort((left, right) =>
      left.id.localeCompare(right.id),
    ),
    profileLock: createProfileLock(input.profiles),
  };
}
