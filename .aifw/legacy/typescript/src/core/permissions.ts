export type PermissionDecision = "allow" | "deny" | "require-approval";

export type ActionRequest =
  | { kind: "read-only"; resource: string }
  | { kind: "filesystem-write"; destructive?: boolean }
  | { kind: "git-local"; operation: "add" | "commit" | "branch" | "merge" }
  | { kind: "git-remote"; operation: "push" | "pull-request" | "tag" }
  | { kind: "deploy"; environment: "preview" | "staging" | "production" }
  | { kind: "external-read"; service: string }
  | { kind: "external-write"; service: string };

export interface PermissionPolicy {
  externalAllowlist: string[];
  approveRemoteMutations: boolean;
  approveProduction: boolean;
  approveExternalWrites: boolean;
  approveDestructiveWrites: boolean;
}

export interface AuthorizationResult {
  decision: PermissionDecision;
  reason: string;
}

export interface DelegationResult {
  valid: boolean;
  excessCapabilities: string[];
}

export interface BreakGlassGrant {
  incidentId: string;
  scope: string[];
  approvedBy: string;
  approvedAt: string;
  expiresAt: string;
  reason: string;
}

export interface BreakGlassValidation {
  valid: boolean;
  reasons: string[];
}

export const defaultPermissionPolicy: Readonly<PermissionPolicy> = {
  externalAllowlist: [],
  approveRemoteMutations: true,
  approveProduction: true,
  approveExternalWrites: true,
  approveDestructiveWrites: true,
};

function allowedExternalService(service: string, allowlist: string[]): boolean {
  return allowlist.includes(service);
}

export function authorizeAction(
  request: ActionRequest,
  policy: PermissionPolicy,
): AuthorizationResult {
  switch (request.kind) {
    case "read-only":
      return { decision: "allow", reason: "read-only" };
    case "git-local":
      return { decision: "allow", reason: "local-version-control" };
    case "git-remote":
      return policy.approveRemoteMutations
        ? { decision: "require-approval", reason: "remote-mutation" }
        : { decision: "allow", reason: "policy-allows-remote-mutation" };
    case "deploy":
      if (request.environment === "production" && policy.approveProduction) {
        return { decision: "require-approval", reason: "production-effect" };
      }
      return { decision: "allow", reason: `${request.environment}-deployment` };
    case "external-read":
      return allowedExternalService(request.service, policy.externalAllowlist)
        ? { decision: "allow", reason: "allowlisted-external-read" }
        : { decision: "deny", reason: "service-not-allowlisted" };
    case "external-write":
      if (!allowedExternalService(request.service, policy.externalAllowlist)) {
        return { decision: "deny", reason: "service-not-allowlisted" };
      }
      return policy.approveExternalWrites
        ? { decision: "require-approval", reason: "external-side-effect" }
        : { decision: "allow", reason: "policy-allows-external-write" };
    case "filesystem-write":
      if (request.destructive === true && policy.approveDestructiveWrites) {
        return { decision: "require-approval", reason: "destructive-write" };
      }
      return { decision: "allow", reason: "local-reversible-write" };
  }
}

export function validateDelegation(
  parentCapabilities: string[],
  requestedCapabilities: string[],
): DelegationResult {
  const parent = new Set(parentCapabilities);
  const excessCapabilities = [...new Set(requestedCapabilities)]
    .filter((capability) => !parent.has(capability))
    .sort((left, right) => left.localeCompare(right));

  return { valid: excessCapabilities.length === 0, excessCapabilities };
}

export function validateBreakGlass(
  grant: BreakGlassGrant,
  requestedScope: string,
  now = new Date(),
): BreakGlassValidation {
  const reasons: string[] = [];
  const approvedAt = new Date(grant.approvedAt);
  const expiresAt = new Date(grant.expiresAt);

  if (grant.incidentId.trim().length === 0) reasons.push("incident-id");
  if (!grant.approvedBy.startsWith("human:")) reasons.push("human-approval");
  if (grant.reason.trim().length === 0) reasons.push("reason");
  if (!grant.scope.includes(requestedScope)) reasons.push("scope");
  if (Number.isNaN(approvedAt.valueOf()) || Number.isNaN(expiresAt.valueOf())) {
    reasons.push("invalid-time-window");
  } else {
    if (expiresAt <= approvedAt) reasons.push("invalid-time-window");
    if (now < approvedAt || now >= expiresAt) reasons.push("expired-or-not-active");
  }

  return { valid: reasons.length === 0, reasons };
}
