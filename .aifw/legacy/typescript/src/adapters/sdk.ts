import type { ChangeLevel, CognitiveRoute } from "../core/change.ts";

export type AgentRole =
  | "orchestrator"
  | "researcher"
  | "architect"
  | "implementer"
  | "reviewer"
  | "auditor";

export interface AdapterTask {
  id: string;
  role: AgentRole;
  route: CognitiveRoute;
  impact: ChangeLevel;
  capabilities: string[];
  instructions: string;
}

export interface AdapterExecutionPlan {
  adapter: string;
  taskId: string;
  role: AgentRole;
  impact: ChangeLevel;
  instructions: string;
  permissions: string[];
  routing: {
    enabled: boolean;
    mode: "recommendation-only" | "automatic";
    suggestedModel: string;
    selectedModel?: string;
  };
}

export interface AgentAdapter {
  id: string;
  plan(task: AdapterTask): AdapterExecutionPlan;
}
