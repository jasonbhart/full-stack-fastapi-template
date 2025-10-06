/**
 * Agent Context Provider
 *
 * Provides state management for agent conversations and UI state.
 * This follows React best practices for context and state management.
 */

import {
  createContext,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useCallback,
  useContext,
  useState,
} from "react"
import type { AgentConversation, AgentMessage } from "./types"

interface AgentContextValue {
  /** Current active conversation */
  currentConversation: AgentConversation | null
  /** Set the current conversation (supports both value and functional updates) */
  setCurrentConversation: Dispatch<SetStateAction<AgentConversation | null>>
  /** Add a message to the current conversation */
  addMessage: (message: AgentMessage) => void
  /** Clear the current conversation */
  clearConversation: () => void
  /** Start a new conversation */
  startNewConversation: () => void
  /** Loading state for agent operations */
  isLoading: boolean
  /** Set loading state */
  setIsLoading: (loading: boolean) => void
}

const AgentContext = createContext<AgentContextValue | undefined>(undefined)

export interface AgentProviderProps {
  children: ReactNode
}

export function AgentProvider({ children }: AgentProviderProps) {
  const [currentConversation, setCurrentConversation] =
    useState<AgentConversation | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const addMessage = useCallback((message: AgentMessage) => {
    setCurrentConversation((prev) => {
      if (!prev) {
        // This shouldn't happen - conversation should be initialized before adding messages
        console.warn("Adding message without active conversation")
        return {
          thread_id: crypto.randomUUID(),
          messages: [message],
          created_at: new Date(),
          updated_at: new Date(),
        }
      }

      return {
        ...prev,
        messages: [...prev.messages, message],
        updated_at: new Date(),
      }
    })
  }, [])

  const clearConversation = useCallback(() => {
    setCurrentConversation(null)
  }, [])

  const startNewConversation = useCallback(() => {
    const newConversation: AgentConversation = {
      thread_id: crypto.randomUUID(),
      messages: [],
      created_at: new Date(),
      updated_at: new Date(),
    }
    setCurrentConversation(newConversation)
  }, [])

  const value: AgentContextValue = {
    currentConversation,
    setCurrentConversation,
    addMessage,
    clearConversation,
    startNewConversation,
    isLoading,
    setIsLoading,
  }

  return <AgentContext.Provider value={value}>{children}</AgentContext.Provider>
}

/**
 * Hook to access agent context
 * @throws Error if used outside of AgentProvider
 */
export function useAgentContext() {
  const context = useContext(AgentContext)
  if (context === undefined) {
    throw new Error("useAgentContext must be used within an AgentProvider")
  }
  return context
}
