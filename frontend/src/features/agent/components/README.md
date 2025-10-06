# Agent Chat Components

This directory contains the UI components for the agent chat feature.

## Components

### AgentChat

The main chat interface component. Provides a complete chat experience with message history, input field, and loading/error states.

**Features:**
- Message history display with auto-scrolling
- User and agent message differentiation
- Loading indicators when agent is processing
- Error handling and display
- New conversation and clear conversation actions
- Trace URL links for observability (when available)
- Responsive design
- Accessibility support (ARIA labels, keyboard navigation)

**Props:**
- `title?: string` - Optional title for the chat panel (default: "Agent Chat")
- `inputPlaceholder?: string` - Optional placeholder for input field (default: "Ask me anything...")
- `maxHeight?: string` - Maximum height of the chat container (default: "600px")

**Example Usage:**
```tsx
import { AgentProvider, AgentChat } from "@/features/agent"

function MyPage() {
  return (
    <AgentProvider>
      <AgentChat
        title="My Agent Assistant"
        inputPlaceholder="How can I help you?"
        maxHeight="500px"
      />
    </AgentProvider>
  )
}
```

### ChatMessage

Displays an individual message in the chat interface. Automatically styles user and agent messages differently.

**Features:**
- Different styling for user vs agent messages
- Avatar icons for user and agent
- Timestamp display
- Latency information (for agent messages)
- Trace URL links (when available)
- Error state styling
- Responsive layout

**Props:**
- `message: AgentMessage` - The message object to display

**Example Usage:**
```tsx
import { ChatMessage } from "@/features/agent"

function MessageList({ messages }) {
  return (
    <>
      {messages.map((message) => (
        <ChatMessage key={message.id} message={message} />
      ))}
    </>
  )
}
```

### ChatInput

Input component for sending messages to the agent.

**Features:**
- Auto-expanding textarea that grows with content
- Submit button
- Keyboard shortcuts (Enter to send, Shift+Enter for new line)
- Auto-focus on mount
- Disabled state while agent is processing
- Automatic height reset after message submission

**Props:**
- `onSubmit: (message: string) => void` - Callback when message is submitted
- `disabled?: boolean` - Whether the input is disabled (default: false)
- `placeholder?: string` - Placeholder text (default: "Type your message...")

**Example Usage:**
```tsx
import { ChatInput } from "@/features/agent"

function CustomChat() {
  const handleSubmit = (message: string) => {
    console.log("Sending:", message)
  }

  return (
    <ChatInput
      onSubmit={handleSubmit}
      disabled={isLoading}
      placeholder="What would you like to know?"
    />
  )
}
```

### ChatLoadingIndicator

Displays a loading animation when the agent is processing a request.

**Features:**
- Skeleton text animation
- Consistent styling with agent messages
- Robot icon indicator

**Example Usage:**
```tsx
import { ChatLoadingIndicator } from "@/features/agent"

function MessageList({ messages, isLoading }) {
  return (
    <>
      {messages.map((message) => (
        <ChatMessage key={message.id} message={message} />
      ))}
      {isLoading && <ChatLoadingIndicator />}
    </>
  )
}
```

## Design Patterns

### State Management
Components use the `useAgent` hook which combines:
- React Query for API state management
- Agent Context for conversation state
- Custom toast notifications for feedback

### Error Handling
- API errors are caught and displayed inline
- Error messages are styled distinctly (red background)
- Error state prevents message submission until resolved

### Accessibility
- All interactive elements have ARIA labels
- Keyboard navigation is fully supported
- Color contrast meets WCAG AA standards
- Screen reader friendly message structure

### Responsive Design
- Mobile-first approach
- Breakpoints at base (mobile) and md (desktop)
- Message width adapts to screen size
- Touch-friendly tap targets (min 44x44px)

## Integration Notes

### Required Context
All components require the `AgentProvider` context to be present in the component tree:

```tsx
import { AgentProvider } from "@/features/agent"

function App() {
  return (
    <AgentProvider>
      {/* Your components here */}
    </AgentProvider>
  )
}
```

### API Integration
Components automatically integrate with the agent API via the `useAgent` hook. Ensure:
- Backend API is running at `VITE_API_URL`
- User is authenticated (JWT token present)
- Agent endpoints are available at `/api/v1/agent/*`

### Styling
Components use Chakra UI v3 components and follow the project's design system:
- Primary color: teal.500
- Error color: red.500
- Neutral colors: gray scale
- Border radius: lg (0.5rem)
- Spacing: Chakra spacing scale

## Future Enhancements

Potential improvements for future iterations:
- [ ] Server-sent events (SSE) for streaming responses
- [ ] File upload support for document analysis
- [ ] Code block syntax highlighting
- [ ] Markdown rendering in messages
- [ ] Message editing and regeneration
- [ ] Voice input/output support
- [ ] Multi-agent conversation support
- [ ] Export conversation history
