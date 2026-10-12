// One-time migration oracle. Python tests consume this JSON without Node.
import { writeFile } from "node:fs/promises";
import { classifyChange } from "../src/core/change.ts";
import { routeTask } from "../src/core/routing.ts";
import { authorizeAction, defaultPermissionPolicy } from "../src/core/permissions.ts";
const routing = [];
for (const impact of ["L0", "L1", "L2", "L3"])
for (const operation of ["single-read", "discovery", "documentation", "implementation", "review", "research", "architecture-decision", "incident-response"])
for (const uncertainty of ["low", "medium", "high"])
for (const failedAttempts of [0, 1, 2])
for (const requestedRoute of ["FAST", "WORK", "BRAIN"])
for (const crossDomain of [false, true]) {
  const input = { impact, operation, uncertainty, failedAttempts, requestedRoute, crossDomain };
  routing.push({ input, expected: routeTask(input) });
}
const classification = [{ input: {}, expected: classifyChange({}) }];
for (const signal of ["readOnly", "docsOnly", "behaviorChange", "localOnly", "reversible", "crossModule", "sharedContract", "sensitiveData", "globalDesignSystem", "externalCost", "production", "touchesAuth", "frameworkCore", "constitution", "securityBoundary", "destructiveMigration", "breakingContract", "irreversibleProduction"])
for (const semanticComplexity of ["fast", "work", "brain"]) {
  const input = { [signal]: true, semanticComplexity };
  classification.push({ input, expected: classifyChange(input) });
}
const permissions = [];
for (const request of [{kind:"read-only"}, {kind:"git-local"}, {kind:"git-remote"}, {kind:"deploy",environment:"production"}, {kind:"deploy",environment:"preview"}, {kind:"external-read",service:"known"}, {kind:"external-write",service:"known"}, {kind:"external-write",service:"unknown"}, {kind:"filesystem-write",destructive:true}])
for (const enabled of [false,true]) {
  const policy = { ...defaultPermissionPolicy, externalAllowlist:["known"], approveRemoteMutations:enabled, approveProduction:enabled, approveExternalWrites:enabled, approveDestructiveWrites:enabled };
  permissions.push({ request, policy, expected: authorizeAction(request, policy) });
}
await writeFile("tests_python/fixtures/legacy-parity.json", JSON.stringify({ routing, classification, permissions }, null, 2)+"\n");
