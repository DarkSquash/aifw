import type {
  AdapterExecutionPlan,
  AdapterTask,
  AgentAdapter,
  AgentRole,
} from "./sdk.ts";
import { DEFAULT_MODEL_ALIASES } from "../core/routing.ts";

export interface PiRoleDefinition {
  id: AgentRole;
  purpose: string;
  defaultCapabilities: string[];
}

export const PI_ROLES: ReadonlyArray<PiRoleDefinition> = [
  { id: "orchestrator", purpose: "Coordinate bounded work and evidence.", defaultCapabilities: [] },
  { id: "researcher", purpose: "Collect and attribute evidence.", defaultCapabilities: [] },
  { id: "architect", purpose: "Evaluate system-level decisions.", defaultCapabilities: [] },
  { id: "implementer", purpose: "Implement an approved change case.", defaultCapabilities: [] },
  { id: "reviewer", purpose: "Review correctness and risk independently.", defaultCapabilities: [] },
  { id: "auditor", purpose: "Evaluate policy and gate conformance.", defaultCapabilities: [] },
];

export interface PiAdapterOptions {
  routingEnabled?: boolean;
}

export function createPiAdapter(options: PiAdapterOptions = {}): AgentAdapter {
  const routingEnabled = options.routingEnabled === true;

  return {
    id: "pi",
    plan(task: AdapterTask): AdapterExecutionPlan {
      const suggestedModel = DEFAULT_MODEL_ALIASES[task.route];
      return {
        adapter: "pi",
        taskId: task.id,
        role: task.role,
        impact: task.impact,
        instructions: task.instructions,
        permissions: [...new Set(task.capabilities)].sort((left, right) =>
          left.localeCompare(right),
        ),
        routing: {
          enabled: routingEnabled,
          mode: routingEnabled ? "automatic" : "recommendation-only",
          suggestedModel,
          ...(routingEnabled ? { selectedModel: suggestedModel } : {}),
        },
      };
    },
  };
}
