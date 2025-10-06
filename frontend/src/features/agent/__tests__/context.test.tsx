/**
 * AgentProvider context tests
 *
 * Tests for the agent context provider and its hooks.
 * Ensures proper state management and conversation handling.
 */

import { act, renderHook, waitFor } from "@testing-library/react"
import type { ReactNode } from "react"
import { describe, expect, it } from "vitest"
import { AgentProvider, useAgentContext } from "../context"
import type { AgentMessage } from "../types"

// Wrapper component for hook tests
function wrapper({ children }: { children: ReactNode }) {
  return <AgentProvider>{children}</AgentProvider>
}

describe("AgentProvider", () => {
  describe("useAgentContext", () => {
    it("throws error when used outside of provider", () => {
      // Suppress console error for this test
      const originalError = console.error
      console.error = () => {}

      expect(() => {
        renderHook(() => useAgentContext())
      }).toThrow("useAgentContext must be used within an AgentProvider")

      console.error = originalError
    })

    it("provides initial state", () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      expect(result.current.currentConversation).toBeNull()
      expect(result.current.isLoading).toBe(false)
    })
  })

  describe("conversation management", () => {
    it("adds messages to conversation", async () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      const message: AgentMessage = {
        id: "msg-1",
        role: "user",
        content: "Hello!",
        timestamp: new Date(),
      }

      act(() => {
        result.current.addMessage(message)
      })

      await waitFor(() => {
        expect(result.current.currentConversation).not.toBeNull()
        expect(result.current.currentConversation?.messages).toHaveLength(1)
        expect(result.current.currentConversation?.messages[0]).toEqual(message)
      })
    })

    it("creates new conversation when adding message without active conversation", async () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      const message: AgentMessage = {
        id: "msg-1",
        role: "user",
        content: "Hello!",
        timestamp: new Date(),
      }

      act(() => {
        result.current.addMessage(message)
      })

      await waitFor(() => {
        expect(result.current.currentConversation).not.toBeNull()
        expect(result.current.currentConversation?.thread_id).toBeDefined()
        expect(result.current.currentConversation?.messages).toHaveLength(1)
      })
    })

    it("appends messages to existing conversation", async () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      const message1: AgentMessage = {
        id: "msg-1",
        role: "user",
        content: "Hello!",
        timestamp: new Date(),
      }

      const message2: AgentMessage = {
        id: "msg-2",
        role: "agent",
        content: "Hi there!",
        timestamp: new Date(),
      }

      act(() => {
        result.current.addMessage(message1)
      })

      await waitFor(() => {
        expect(result.current.currentConversation?.messages).toHaveLength(1)
      })

      act(() => {
        result.current.addMessage(message2)
      })

      await waitFor(() => {
        expect(result.current.currentConversation?.messages).toHaveLength(2)
        expect(result.current.currentConversation?.messages[0]).toEqual(
          message1,
        )
        expect(result.current.currentConversation?.messages[1]).toEqual(
          message2,
        )
      })
    })

    it("clears conversation", async () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      const message: AgentMessage = {
        id: "msg-1",
        role: "user",
        content: "Hello!",
        timestamp: new Date(),
      }

      act(() => {
        result.current.addMessage(message)
      })

      await waitFor(() => {
        expect(result.current.currentConversation).not.toBeNull()
      })

      act(() => {
        result.current.clearConversation()
      })

      await waitFor(() => {
        expect(result.current.currentConversation).toBeNull()
      })
    })

    it("starts new conversation with fresh state", async () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      act(() => {
        result.current.startNewConversation()
      })

      await waitFor(() => {
        expect(result.current.currentConversation).not.toBeNull()
        expect(result.current.currentConversation?.messages).toHaveLength(0)
        expect(result.current.currentConversation?.thread_id).toBeDefined()
      })
    })

    it("updates loading state", async () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      expect(result.current.isLoading).toBe(false)

      act(() => {
        result.current.setIsLoading(true)
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(true)
      })

      act(() => {
        result.current.setIsLoading(false)
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })
    })

    it("updates conversation timestamp when messages are added", async () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      act(() => {
        result.current.startNewConversation()
      })

      await waitFor(() => {
        expect(result.current.currentConversation).not.toBeNull()
      })

      const createdAt = result.current.currentConversation!.created_at
      const initialUpdatedAt = result.current.currentConversation!.updated_at

      // Wait a bit to ensure timestamp difference
      await new Promise((resolve) => setTimeout(resolve, 10))

      const message: AgentMessage = {
        id: "msg-1",
        role: "user",
        content: "Hello!",
        timestamp: new Date(),
      }

      act(() => {
        result.current.addMessage(message)
      })

      await waitFor(() => {
        expect(
          result.current.currentConversation!.updated_at.getTime(),
        ).toBeGreaterThan(initialUpdatedAt.getTime())
        expect(result.current.currentConversation!.created_at).toEqual(
          createdAt,
        )
      })
    })
  })

  describe("setCurrentConversation", () => {
    it("supports functional updates", async () => {
      const { result } = renderHook(() => useAgentContext(), { wrapper })

      act(() => {
        result.current.startNewConversation()
      })

      await waitFor(() => {
        expect(result.current.currentConversation).not.toBeNull()
      })

      const originalThreadId = result.current.currentConversation!.thread_id

      act(() => {
        result.current.setCurrentConversation((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            thread_id: "new-thread-id",
          }
        })
      })

      await waitFor(() => {
        expect(result.current.currentConversation?.thread_id).toBe(
          "new-thread-id",
        )
        expect(result.current.currentConversation?.thread_id).not.toBe(
          originalThreadId,
        )
      })
    })
  })
})
