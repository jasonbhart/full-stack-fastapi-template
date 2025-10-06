/**
 * Custom hooks for agent operations
 *
 * This module provides React Query hooks for interacting with the agent API.
 * It follows existing frontend patterns for API integration and state management.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { ApiError } from "@/client/core/ApiError"
import {
  agentHealthCheck,
  createEvaluation,
  getAgentRuns,
  runAgent,
} from "@/features/agent/api"
import { useAgentContext } from "@/features/agent/context"
import type {
  AgentEvaluationCreate,
  AgentInvocationRequest,
  AgentInvocationResponse,
  AgentMessage,
} from "@/features/agent/types"
import { handleError } from "@/utils"
import useCustomToast from "./useCustomToast"

interface UseAgentRunsOptions {
  skip?: number
  limit?: number
  thread_id?: string | null
  search?: string | null
  status?: string | null
  enabled?: boolean
}

/**
 * Hook for fetching agent run history
 */
export function useAgentRuns(options: UseAgentRunsOptions = {}) {
  const {
    skip = 0,
    limit = 20,
    thread_id,
    search,
    status,
    enabled = true,
  } = options

  return useQuery({
    queryKey: ["agentRuns", { skip, limit, thread_id, search, status }],
    queryFn: () => getAgentRuns({ skip, limit, thread_id, search, status }),
    enabled,
  })
}

/**
 * Hook for running the agent with a message
 */
export function useRunAgent() {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()
  const {
    addMessage,
    setIsLoading,
    currentConversation,
    setCurrentConversation,
  } = useAgentContext()

  return useMutation({
    mutationFn: (request: AgentInvocationRequest) => {
      // Use current conversation's thread_id if available
      const requestWithThread: AgentInvocationRequest = {
        ...request,
        thread_id: request.thread_id || currentConversation?.thread_id || null,
      }
      return runAgent({ requestBody: requestWithThread })
    },
    onMutate: async (request) => {
      setIsLoading(true)

      // Initialize conversation if it doesn't exist
      if (!currentConversation) {
        setCurrentConversation({
          thread_id: request.thread_id ?? crypto.randomUUID(),
          messages: [],
          created_at: new Date(),
          updated_at: new Date(),
        })
      }

      // Add user message to conversation
      const userMessage: AgentMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: request.message,
        timestamp: new Date(),
      }
      addMessage(userMessage)
    },
    onSuccess: (response: AgentInvocationResponse) => {
      // Update conversation with authoritative thread_id from backend
      setCurrentConversation((prev) => {
        const base = prev ?? {
          thread_id: response.thread_id,
          messages: [],
          created_at: new Date(),
        }

        // Create agent message
        const agentMessage: AgentMessage = {
          id: response.run_id,
          role: "agent",
          content: response.response,
          timestamp: new Date(),
          trace_id: response.trace_id,
          trace_url: response.trace_url,
          latency_ms: response.latency_ms,
          status: response.status,
        }

        return {
          ...base,
          thread_id: response.thread_id, // Use backend's authoritative thread_id
          messages: [...base.messages, agentMessage],
          updated_at: new Date(),
        }
      })

      showSuccessToast("Agent responded successfully")
    },
    onError: (err: ApiError) => {
      handleError(err)
      // Add error message to conversation
      const errorMessage: AgentMessage = {
        id: crypto.randomUUID(),
        role: "agent",
        content: "Sorry, I encountered an error processing your request.",
        timestamp: new Date(),
        status: "error",
      }
      addMessage(errorMessage)
    },
    onSettled: () => {
      setIsLoading(false)
      queryClient.invalidateQueries({ queryKey: ["agentRuns"] })
    },
  })
}

/**
 * Hook for creating agent evaluations
 */
export function useCreateEvaluation() {
  const queryClient = useQueryClient()
  const { showSuccessToast } = useCustomToast()

  return useMutation({
    mutationFn: (evaluation: AgentEvaluationCreate) =>
      createEvaluation({ requestBody: evaluation }),
    onSuccess: () => {
      showSuccessToast("Evaluation submitted successfully")
    },
    onError: (err: ApiError) => {
      handleError(err)
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["agentRuns"] })
    },
  })
}

/**
 * Hook for checking agent service health
 */
export function useAgentHealth(enabled = true) {
  return useQuery({
    queryKey: ["agentHealth"],
    queryFn: () => agentHealthCheck(),
    enabled,
    // Refetch every 30 seconds to monitor health
    refetchInterval: 30000,
  })
}

/**
 * Combined hook that provides all agent operations
 */
export default function useAgent() {
  const context = useAgentContext()
  const runAgentMutation = useRunAgent()
  const createEvaluationMutation = useCreateEvaluation()

  return {
    // Context state
    ...context,
    // Mutations
    runAgent: runAgentMutation.mutate,
    runAgentAsync: runAgentMutation.mutateAsync,
    isRunning: runAgentMutation.isPending,
    runError: runAgentMutation.error,
    createEvaluation: createEvaluationMutation.mutate,
    createEvaluationAsync: createEvaluationMutation.mutateAsync,
    isEvaluating: createEvaluationMutation.isPending,
  }
}
