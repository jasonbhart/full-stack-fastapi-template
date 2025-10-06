/**
 * Agent API service
 *
 * This module provides methods to interact with agent endpoints.
 * Once the OpenAPI client is regenerated, this can be replaced with
 * the auto-generated AgentService from @/client
 */

import type { CancelablePromise } from "@/client/core/CancelablePromise"
import { OpenAPI } from "@/client/core/OpenAPI"
import { request as __request } from "@/client/core/request"
import type {
  AgentEvaluationCreate,
  AgentHealthResponse,
  AgentInvocationRequest,
  AgentInvocationResponse,
  AgentRunsPublic,
} from "./types"

export interface RunAgentData {
  requestBody: AgentInvocationRequest
}

export interface GetAgentRunsData {
  skip?: number
  limit?: number
  thread_id?: string | null
  search?: string | null
  status?: string | null
}

export interface CreateEvaluationData {
  requestBody: AgentEvaluationCreate
}

/**
 * Run Agent
 * Execute the agent with a user message
 * @param data The data for the request
 * @param data.requestBody Agent invocation request
 * @returns AgentInvocationResponse Successful Response
 * @throws ApiError
 */
export function runAgent(
  data: RunAgentData,
): CancelablePromise<AgentInvocationResponse> {
  return __request(OpenAPI, {
    method: "POST",
    url: "/api/v1/agent/run",
    body: data.requestBody,
    mediaType: "application/json",
    errors: {
      422: "Validation Error",
    },
  })
}

/**
 * Get Agent Runs
 * Retrieve agent run history
 * @param data The data for the request
 * @param data.skip Number of runs to skip
 * @param data.limit Maximum number of runs to return
 * @param data.thread_id Optional thread ID to filter by
 * @param data.search Optional search query to filter by input or output
 * @param data.status Optional status filter
 * @returns AgentRunsPublic Successful Response
 * @throws ApiError
 */
export function getAgentRuns(
  data: GetAgentRunsData = {},
): CancelablePromise<AgentRunsPublic> {
  return __request(OpenAPI, {
    method: "GET",
    url: "/api/v1/agent/runs",
    query: {
      skip: data.skip,
      limit: data.limit,
      thread_id: data.thread_id,
      search: data.search,
      status: data.status,
    },
    errors: {
      422: "Validation Error",
    },
  })
}

/**
 * Create Agent Evaluation
 * Submit an evaluation for an agent run
 * @param data The data for the request
 * @param data.requestBody Evaluation data
 * @returns Message Successful Response
 * @throws ApiError
 */
export function createEvaluation(
  data: CreateEvaluationData,
): CancelablePromise<{ message: string }> {
  return __request(OpenAPI, {
    method: "POST",
    url: "/api/v1/agent/evaluations",
    body: data.requestBody,
    mediaType: "application/json",
    errors: {
      422: "Validation Error",
    },
  })
}

/**
 * Health Check
 * Check agent service health
 * @returns AgentHealthResponse Successful Response
 * @throws ApiError
 */
export function agentHealthCheck(): CancelablePromise<AgentHealthResponse> {
  return __request(OpenAPI, {
    method: "GET",
    url: "/api/v1/agent/health",
  })
}
