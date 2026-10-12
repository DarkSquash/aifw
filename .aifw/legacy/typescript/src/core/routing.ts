import type { ChangeLevel, CognitiveRoute } from "./change.ts";

export interface RoutingTask {
  impact: ChangeLevel;
  operation:
    | "single-read"
    | "discovery"
    | "documentation"
    | "implementation"
    | "review"
    | "research"
    | "architecture-decision"
    | "incident-response";
  uncertainty: "low" | "medium" | "high";
  requestedRoute?: CognitiveRoute;
  failedAttempts?: number;
  crossDomain?: boolean;
}

export interface ModelAliases {
  FAST: string;
  WORK: string;
  BRAIN: string;
}

export interface RoutingDecision {
  route: CognitiveRoute;
  suggestedModel: string;
  executionMode: "recommendation-only" | "automatic";
  reasons: string[];
}

export interface RoutingEvaluation {
  cases: number;
  passRate: number;
  criticalFailures: number;
}

export interface RoutingActivationInput {
  humanApproved: boolean;
  report: RoutingEvaluation;
  minimumCases?: number;
  minimumPassRate?: number;
}

export interface RoutingActivation {
  enabled: boolean;
  blockers: string[];
}

export const DEFAULT_MODEL_ALIASES: Readonly<ModelAliases> = {
  FAST: "Luna",
  WORK: "Terra",
  BRAIN: "Sol",
};

function chooseRoute(task: RoutingTask): { route: CognitiveRoute; reasons: string[] } {
  const reasons: string[] = [];

  if (task.impact === "L3") {
    return { route: "BRAIN", reasons: ["impact:L3"] };
  }
  if (task.operation === "architecture-decision") {
    return { route: "BRAIN", reasons: ["operation:architecture-decision"] };
  }
  if (task.uncertainty === "high" || (task.failedAttempts ?? 0) >= 2) {
    return {
      route: "BRAIN",
      reasons: [task.uncertainty === "high" ? "uncertainty:high" : "failed-attempts"],
    };
  }
  if (task.requestedRoute === "BRAIN") {
    return { route: "BRAIN", reasons: ["requested:BRAIN"] };
  }

  const fastEligible =
    (task.impact === "L0" || task.impact === "L1") &&
    task.uncertainty === "low" &&
    task.crossDomain !== true &&
    (task.operation === "single-read" ||
      task.operation === "discovery" ||
      task.operation === "documentation");

  if (fastEligible && task.requestedRoute !== "WORK") {
    reasons.push("bounded-low-risk");
    return { route: "FAST", reasons };
  }

  reasons.push(`impact:${task.impact}`, `operation:${task.operation}`);
  return { route: "WORK", reasons };
}

export function routeTask(
  task: RoutingTask,
  options: {
    aliases?: ModelAliases;
    routingEnabled?: boolean;
  } = {},
): RoutingDecision {
  const aliases = options.aliases ?? DEFAULT_MODEL_ALIASES;
  const { route, reasons } = chooseRoute(task);

  return {
    route,
    suggestedModel: aliases[route],
    executionMode: options.routingEnabled === true ? "automatic" : "recommendation-only",
    reasons,
  };
}

export function evaluateRoutingActivation(
  input: RoutingActivationInput,
): RoutingActivation {
  const minimumCases = input.minimumCases ?? 30;
  const minimumPassRate = input.minimumPassRate ?? 0.95;
  const blockers: string[] = [];

  if (!input.humanApproved) blockers.push("human-approval");
  if (input.report.cases < minimumCases) {
    blockers.push(`minimum-cases:${String(minimumCases)}`);
  }
  if (input.report.passRate < minimumPassRate) {
    blockers.push(`minimum-pass-rate:${String(minimumPassRate)}`);
  }
  if (input.report.criticalFailures > 0) blockers.push("critical-failures:0");

  return { enabled: blockers.length === 0, blockers };
}
