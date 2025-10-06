/**
 * TypeScript types for agent feature module
 *
 * These types match the backend Pydantic schemas for agent interactions.
 * Once the OpenAPI client is regenerated, these can be replaced with
 * auto-generated types from @/client
 */

// ============================================================================
// Agent Invocation Types
// ============================================================================

export interface AgentInvocationRequest {
  /** User's message/prompt for the agent */
  message: string
  /** Optional conversation thread ID for continuity */
  thread_id?: string | null
  /** Optional metadata to attach to the agent run */
  run_metadata?: Record<string, any> | null
}

export interface AgentInvocationResponse {
  /** Agent's response message */
  response: string
  /** Conversation thread ID for continuity */
  thread_id: string
  /** Langfuse trace ID for observability correlation */
  trace_id?: string | null
  /** URL to view the trace in Langfuse UI */
  trace_url?: string | null
  /** Unique identifier for this agent run */
  run_id: string
  /** Execution time in milliseconds */
  latency_ms: number
  /** Run status (success, error, timeout, etc.) */
  status: string
  /** Execution plan created by the planner node */
  plan?: string | null
}

// ============================================================================
// Agent Run History Types
// ============================================================================

export interface AgentRunPublic {
  /** Unique identifier for the run */
  id: string
  /** ID of the user who initiated the run */
  user_id: string
  /** Conversation thread ID */
  thread_id: string
  /** User's input message */
  input: string
  /** Agent's output response */
  output: string
  /** Run status (success, error, timeout, etc.) */
  status: string
  /** Execution time in milliseconds */
  latency_ms: number
  /** Langfuse trace ID for observability */
  trace_id?: string | null
  /** URL to view the trace in Langfuse UI */
  trace_url?: string | null
  /** Timestamp when the run was created */
  created_at: string
  /** Number of tokens in the prompt (if available) */
  prompt_tokens?: number | null
  /** Number of tokens in the completion (if available) */
  completion_tokens?: number | null
}

export interface AgentRunsPublic {
  /** List of agent run records */
  data: AgentRunPublic[]
  /** Total number of runs available for the user */
  total: number
  /** Maximum number of runs requested per page */
  limit: number
  /** Number of runs skipped (for pagination) */
  offset: number
}

// ============================================================================
// Utility Types
// ============================================================================

export interface AgentHealthResponse {
  /** Service status (healthy, degraded, unhealthy) */
  status: string
  /** Whether Langfuse tracing is enabled */
  langfuse_enabled: boolean
  /** Whether Langfuse is properly configured */
  langfuse_configured: boolean
  /** LLM model name being used */
  model_name: string
  /** Number of tools available to the agent */
  available_tools: number
}

export interface AgentEvaluationCreate {
  /** UUID of the agent run to evaluate */
  run_id: string
  /** Name of the evaluation metric */
  metric_name: string
  /** Numerical score for the metric */
  score: number
  /** Optional metadata for the evaluation */
  eval_metadata?: Record<string, any> | null
}

// ============================================================================
// UI State Types
// ============================================================================

export interface AgentMessage {
  id: string
  role: "user" | "agent"
  content: string
  timestamp: Date
  trace_id?: string | null
  trace_url?: string | null
  latency_ms?: number
  status?: string
}

export interface AgentConversation {
  thread_id: string
  messages: AgentMessage[]
  created_at: Date
  updated_at: Date
}
