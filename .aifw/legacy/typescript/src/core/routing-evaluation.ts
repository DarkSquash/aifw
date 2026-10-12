import { readFile } from "node:fs/promises";

import { parseDocument } from "yaml";

import type { CognitiveRoute } from "./change.ts";
import { AifwError } from "./errors.ts";
import { routeTask, type RoutingTask } from "./routing.ts";

interface RoutingCase {
  id: string;
  critical: boolean;
  input: RoutingTask;
  expectedRoute: CognitiveRoute;
}

export interface RoutingCaseFailure {
  id: string;
  expectedRoute: CognitiveRoute;
  actualRoute: CognitiveRoute;
  critical: boolean;
}

export interface RoutingEvaluationReport {
  cases: number;
  passed: number;
  passRate: number;
  criticalFailures: number;
  failures: RoutingCaseFailure[];
}

function parseCases(source: string): RoutingCase[] {
  const document = parseDocument(source, { schema: "core", strict: true, uniqueKeys: true });
  if (document.errors.length > 0) {
    throw new AifwError(
      "YAML_INVALID",
      `Routing cases are invalid: ${document.errors.map((error) => error.message).join("; ")}`,
    );
  }
  const value = document.toJS() as { cases?: unknown[] } | null;
  if (value === null || !Array.isArray(value.cases)) {
    throw new AifwError("MANIFEST_INVALID", "Routing evaluation requires a cases array.");
  }
  const cases: RoutingCase[] = [];
  for (const candidate of value.cases) {
    const item = candidate as Record<string, unknown> | null;
    if (
      item === null ||
      typeof item.id !== "string" ||
      typeof item.critical !== "boolean" ||
      typeof item.expectedRoute !== "string" ||
      !["FAST", "WORK", "BRAIN"].includes(item.expectedRoute) ||
      typeof item.input !== "object" ||
      item.input === null
    ) {
      throw new AifwError("MANIFEST_INVALID", "A routing evaluation case is malformed.");
    }
    cases.push(structuredClone(item) as unknown as RoutingCase);
  }
  if (new Set(cases.map((item) => item.id)).size !== cases.length) {
    throw new AifwError("MANIFEST_INVALID", "Routing evaluation case IDs must be unique.");
  }
  return cases;
}

export async function evaluateRoutingCases(
  fixturePath: string,
): Promise<RoutingEvaluationReport> {
  const cases = parseCases(await readFile(fixturePath, "utf8"));
  const failures = cases.flatMap((item): RoutingCaseFailure[] => {
    const actualRoute = routeTask(item.input).route;
    return actualRoute === item.expectedRoute
      ? []
      : [{ id: item.id, expectedRoute: item.expectedRoute, actualRoute, critical: item.critical }];
  });
  const passed = cases.length - failures.length;
  return {
    cases: cases.length,
    passed,
    passRate: cases.length === 0 ? 0 : passed / cases.length,
    criticalFailures: failures.filter((failure) => failure.critical).length,
    failures,
  };
}
