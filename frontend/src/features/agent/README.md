# Agent Feature Module

This module provides the frontend foundation for agent interactions, including API integration, state management, and React hooks.

## Structure

```
frontend/src/features/agent/
├── api.ts           # Agent API service methods
├── context.tsx      # React context for agent state management
├── types.ts         # TypeScript type definitions
├── index.ts         # Public API exports
└── README.md        # This file
```

## Usage

### 1. Wrap your app with AgentProvider

```tsx
import { AgentProvider } from "@/features/agent"

function App() {
  return (
    <AgentProvider>
      {/* Your app components */}
    </AgentProvider>
  )
}
```

### 2. Use the agent hooks

```tsx
import useAgent, { useAgentRuns, useAgentHealth } from "@/hooks/useAgent"

function AgentChatComponent() {
  const {
    currentConversation,
    runAgent,
    isRunning,
    startNewConversation,
    clearConversation,
  } = useAgent()

  const handleSendMessage = (message: string) => {
    runAgent({ message })
  }

  return (
    <div>
      {currentConversation?.messages.map((msg) => (
        <div key={msg.id}>
          <strong>{msg.role}:</strong> {msg.content}
        </div>
      ))}
      <button onClick={() => handleSendMessage("Hello!")}>
        Send Message
      </button>
    </div>
  )
}
```

### 3. Fetch agent run history

```tsx
import { useAgentRuns } from "@/hooks/useAgent"

function AgentHistoryComponent() {
  const { data, isLoading } = useAgentRuns({ limit: 20 })

  if (isLoading) return <div>Loading...</div>

  return (
    <ul>
      {data?.data.map((run) => (
        <li key={run.id}>
          <div>{run.input}</div>
          <div>{run.output}</div>
          {run.trace_url && (
            <a href={run.trace_url} target="_blank" rel="noopener noreferrer">
              View Trace
            </a>
          )}
        </li>
      ))}
    </ul>
  )
}
```

### 4. Check agent health

```tsx
import { useAgentHealth } from "@/hooks/useAgent"

function AgentHealthIndicator() {
  const { data: health } = useAgentHealth()

  return (
    <div>
      Status: {health?.status}
      {health?.langfuse_enabled && " (Tracing enabled)"}
    </div>
  )
}
```

## API Methods

### AgentService

- `runAgent(data)` - Execute the agent with a user message
- `getAgentRuns(data)` - Retrieve agent run history
- `createEvaluation(data)` - Submit an evaluation for an agent run
- `healthCheck()` - Check agent service health

## Hooks

### useAgent()

Main hook that combines all agent functionality:

```typescript
const {
  // State
  currentConversation,
  isLoading,

  // Actions
  runAgent,
  runAgentAsync,
  startNewConversation,
  clearConversation,
  addMessage,
  setCurrentConversation,

  // Mutation state
  isRunning,
  runError,
  createEvaluation,
  isEvaluating,
} = useAgent()
```

### useAgentRuns(options)

Fetch agent run history with pagination:

```typescript
const { data, isLoading, error } = useAgentRuns({
  skip: 0,
  limit: 20,
  thread_id: "optional-thread-id",
  enabled: true,
})
```

### useRunAgent()

Low-level hook for running agents (used internally by `useAgent`):

```typescript
const mutation = useRunAgent()
mutation.mutate({ message: "Hello!", thread_id: "optional" })
```

### useCreateEvaluation()

Submit evaluations for agent runs:

```typescript
const mutation = useCreateEvaluation()
mutation.mutate({
  run_id: "agent-run-id",
  metric_name: "helpfulness",
  score: 0.8,
})
```

### useAgentHealth(enabled)

Monitor agent service health (auto-refreshes every 30s):

```typescript
const { data, isLoading } = useAgentHealth(true)
```

## State Management

The `AgentProvider` manages conversation state:

- **currentConversation**: Active conversation with messages
- **isLoading**: Loading state for agent operations
- **addMessage**: Add a message to the current conversation
- **clearConversation**: Clear the current conversation
- **startNewConversation**: Start a new conversation thread

### Thread ID Synchronization

The conversation's `thread_id` is synchronized with the backend's authoritative value:

1. When starting a conversation, a temporary `thread_id` is generated (or taken from the request)
2. After the backend responds, the conversation is updated with the backend's authoritative `thread_id`
3. All subsequent messages in the conversation use this authoritative `thread_id`

This ensures multi-turn conversations maintain continuity across agent calls.

## Type Definitions

All types are exported from `@/features/agent`:

- `AgentInvocationRequest`
- `AgentInvocationResponse`
- `AgentRunPublic`
- `AgentRunsPublic`
- `AgentHealthResponse`
- `AgentEvaluationCreate`
- `AgentMessage`
- `AgentConversation`

## Integration with Generated Client

Once the OpenAPI client is regenerated (by running `./scripts/generate-client.sh`), the `api.ts` file can be replaced with imports from `@/client/sdk.gen.ts`. The types in `types.ts` can also be replaced with the auto-generated types from `@/client/types.gen.ts`.

## Next Steps

1. Build UI components (AgentChat, AgentHistory) - See task 17 and 18
2. Add feature flags for conditional rendering - See task 19
3. Regenerate OpenAPI client after backend is stable
4. Add tests for hooks and context, especially:
   - Test that multi-turn conversations use the backend's `thread_id`
   - Test that the second mutation in a conversation uses the `thread_id` from the first response
   - Test conversation initialization and message handling
