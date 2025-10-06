/**
 * MSW request handlers for agent API endpoints
 *
 * These handlers mock the agent API for testing purposes.
 * They provide realistic responses that match the backend API contract.
 */

import { HttpResponse, http } from "msw"
import type {
  AgentHealthResponse,
  AgentInvocationResponse,
  AgentRunPublic,
  AgentRunsPublic,
} from "@/features/agent/types"

// Use wildcard pattern to match any host
const API_PATTERN = "*/api/v1"

// Mock agent runs data
const mockRuns: AgentRunPublic[] = [
  {
    id: "run-1",
    user_id: "user-1",
    thread_id: "thread-1",
    input: "What is the weather today?",
    output: "The weather is sunny with a temperature of 75°F.",
    status: "success",
    latency_ms: 1234,
    trace_id: "trace-1",
    trace_url: "https://langfuse.example.com/trace/trace-1",
    created_at: new Date("2024-01-01T10:00:00Z").toISOString(),
    prompt_tokens: 50,
    completion_tokens: 20,
  },
  {
    id: "run-2",
    user_id: "user-1",
    thread_id: "thread-2",
    input: "How do I install Python?",
    output:
      "You can install Python by downloading it from python.org and following the installation instructions for your operating system.",
    status: "success",
    latency_ms: 2345,
    trace_id: "trace-2",
    trace_url: "https://langfuse.example.com/trace/trace-2",
    created_at: new Date("2024-01-01T11:00:00Z").toISOString(),
    prompt_tokens: 60,
    completion_tokens: 35,
  },
  {
    id: "run-3",
    user_id: "user-1",
    thread_id: "thread-3",
    input: "Error test",
    output: "An error occurred during processing.",
    status: "error",
    latency_ms: 500,
    trace_id: "trace-3",
    trace_url: "https://langfuse.example.com/trace/trace-3",
    created_at: new Date("2024-01-01T12:00:00Z").toISOString(),
  },
]

export const handlers = [
  // POST /api/v1/agent/run - Run agent with a message
  http.post(`${API_PATTERN}/agent/run`, async ({ request }) => {
    const body = (await request.json()) as {
      message: string
      thread_id?: string | null
    }

    // Simulate error for specific test cases
    if (body.message.toLowerCase().includes("error")) {
      return HttpResponse.json(
        { detail: "Agent execution failed" },
        { status: 500 },
      )
    }

    // Simulate rate limiting for specific test cases
    if (body.message.toLowerCase().includes("rate limit")) {
      return HttpResponse.json(
        { detail: "Rate limit exceeded" },
        { status: 429 },
      )
    }

    const response: AgentInvocationResponse = {
      response: `Mock response to: ${body.message}`,
      thread_id: body.thread_id || crypto.randomUUID(),
      trace_id: `trace-${crypto.randomUUID()}`,
      trace_url: `https://langfuse.example.com/trace/trace-${crypto.randomUUID()}`,
      run_id: `run-${crypto.randomUUID()}`,
      latency_ms: 1500,
      status: "success",
      plan: "1. Understand the question\n2. Provide a helpful response",
    }

    return HttpResponse.json(response)
  }),

  // GET /api/v1/agent/runs - Get agent run history
  http.get(`${API_PATTERN}/agent/runs`, ({ request }) => {
    const url = new URL(request.url)
    const skip = Number.parseInt(url.searchParams.get("skip") || "0", 10)
    const limit = Number.parseInt(url.searchParams.get("limit") || "10", 10)
    const search = url.searchParams.get("search")
    const status = url.searchParams.get("status")

    let filteredRuns = [...mockRuns]

    // Apply search filter
    if (search) {
      const searchLower = search.toLowerCase()
      filteredRuns = filteredRuns.filter(
        (run) =>
          run.input.toLowerCase().includes(searchLower) ||
          run.output.toLowerCase().includes(searchLower),
      )
    }

    // Apply status filter
    if (status) {
      filteredRuns = filteredRuns.filter((run) => run.status === status)
    }

    // Apply pagination
    const paginatedRuns = filteredRuns.slice(skip, skip + limit)

    const response: AgentRunsPublic = {
      data: paginatedRuns,
      total: filteredRuns.length,
      limit,
      offset: skip,
    }

    return HttpResponse.json(response)
  }),

  // POST /api/v1/agent/evaluations - Create evaluation
  http.post(`${API_PATTERN}/agent/evaluations`, async ({ request }) => {
    const body = (await request.json()) as {
      run_id: string
      metric_name: string
      score: number
    }

    // Validate required fields
    if (!body.run_id || !body.metric_name || body.score === undefined) {
      return HttpResponse.json(
        { detail: "Missing required fields" },
        { status: 422 },
      )
    }

    return HttpResponse.json({
      message: "Evaluation submitted successfully",
    })
  }),

  // GET /api/v1/agent/health - Health check
  http.get(`${API_PATTERN}/agent/health`, () => {
    const response: AgentHealthResponse = {
      status: "healthy",
      langfuse_enabled: true,
      langfuse_configured: true,
      model_name: "gpt-4",
      available_tools: 5,
    }

    return HttpResponse.json(response)
  }),
]
