export type ChangeLevel = "L0" | "L1" | "L2" | "L3";
export type CognitiveRoute = "FAST" | "WORK" | "BRAIN";

export interface ChangeSignals {
  readOnly?: boolean;
  docsOnly?: boolean;
  behaviorChange?: boolean;
  localOnly?: boolean;
  reversible?: boolean;
  crossModule?: boolean;
  sharedContract?: boolean;
  sensitiveData?: boolean;
  globalDesignSystem?: boolean;
  externalCost?: boolean;
  production?: boolean;
  touchesAuth?: boolean;
  frameworkCore?: boolean;
  constitution?: boolean;
  securityBoundary?: boolean;
  destructiveMigration?: boolean;
  breakingContract?: boolean;
  irreversibleProduction?: boolean;
  semanticComplexity?: "fast" | "work" | "brain";
}

export interface ChangeClassification {
  level: ChangeLevel;
  humanApproval: "none" | "conditional" | "required";
  reasons: string[];
  requiredArtifacts: string[];
  suggestedRoute: CognitiveRoute;
}

const l3Signals: ReadonlyArray<[keyof ChangeSignals, string]> = [
  ["frameworkCore", "framework-core"],
  ["constitution", "constitution"],
  ["securityBoundary", "security-boundary"],
  ["destructiveMigration", "destructive-migration"],
  ["breakingContract", "breaking-contract"],
  ["irreversibleProduction", "irreversible-production"],
];

const l2Signals: ReadonlyArray<[keyof ChangeSignals, string]> = [
  ["crossModule", "cross-module"],
  ["sharedContract", "shared-contract"],
  ["sensitiveData", "sensitive-data"],
  ["globalDesignSystem", "global-design-system"],
  ["externalCost", "external-cost"],
  ["production", "production"],
  ["touchesAuth", "authorization"],
];

const l2ApprovalReasons = new Set([
  "shared-contract",
  "sensitive-data",
  "global-design-system",
  "external-cost",
  "production",
  "authorization",
]);

function activeReasons(
  signals: ChangeSignals,
  definitions: ReadonlyArray<[keyof ChangeSignals, string]>,
): string[] {
  return definitions
    .filter(([field]) => signals[field] === true)
    .map(([, reason]) => reason);
}

function routeFor(
  complexity: ChangeSignals["semanticComplexity"],
  level: ChangeLevel,
): CognitiveRoute {
  if (complexity === "brain") return "BRAIN";
  if (complexity === "work") return "WORK";
  if (complexity === "fast") return "FAST";
  if (level === "L3") return "BRAIN";
  if (level === "L0") return "FAST";
  return "WORK";
}

export function classifyChange(signals: ChangeSignals): ChangeClassification {
  const l3Reasons = activeReasons(signals, l3Signals);
  const l2Reasons = activeReasons(signals, l2Signals);

  let level: ChangeLevel;
  let reasons: string[];
  let humanApproval: ChangeClassification["humanApproval"];
  let requiredArtifacts: string[];

  if (l3Reasons.length > 0) {
    level = "L3";
    reasons = l3Reasons;
    humanApproval = "required";
    requiredArtifacts = [
      "change-case",
      "rfc",
      "spec",
      "technical-plan",
      "adr",
      "threat-model",
      "migration",
      "rollback",
      "independent-review",
      "human-approval",
    ];
  } else if (l2Reasons.length > 0) {
    level = "L2";
    reasons = l2Reasons;
    humanApproval = l2Reasons.some((reason) => l2ApprovalReasons.has(reason))
      ? "required"
      : "conditional";
    requiredArtifacts = [
      "change-case",
      "spec",
      "technical-plan",
      "tests",
      "rollback",
      "independent-review",
    ];
  } else if (signals.behaviorChange === true) {
    level = "L1";
    reasons = [signals.localOnly === true ? "local-behavior" : "behavior"];
    humanApproval = "none";
    requiredArtifacts = ["change-case", "tests", "rollback"];
  } else {
    level = "L0";
    reasons = [signals.docsOnly === true ? "documentation" : "read-only"];
    humanApproval = "none";
    requiredArtifacts = ["change-record", "evidence"];
  }

  return {
    level,
    humanApproval,
    reasons,
    requiredArtifacts,
    suggestedRoute: routeFor(signals.semanticComplexity, level),
  };
}
