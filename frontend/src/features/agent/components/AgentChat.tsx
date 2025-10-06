/**
 * AgentChat Component
 *
 * Main chat interface for interacting with the agent.
 * Features:
 * - Message history display
 * - Real-time message updates
 * - Loading states
 * - Error handling
 * - Accessibility support
 * - Responsive design
 */

import {
  Box,
  Button,
  Container,
  Heading,
  HStack,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useEffect, useRef } from "react"
import { FaTrash } from "react-icons/fa"
import useAgent from "@/hooks/useAgent"
import { ChatInput } from "./ChatInput"
import { ChatLoadingIndicator } from "./ChatLoadingIndicator"
import { ChatMessage } from "./ChatMessage"

interface AgentChatProps {
  /** Optional title for the chat panel */
  title?: string
  /** Optional placeholder for input field */
  inputPlaceholder?: string
  /** Maximum height of the chat container */
  maxHeight?: string
}

export function AgentChat({
  title = "Agent Chat",
  inputPlaceholder = "Ask me anything...",
  maxHeight = "600px",
}: AgentChatProps) {
  const {
    currentConversation,
    isLoading,
    runAgent,
    runError,
    clearConversation,
    startNewConversation,
  } = useAgent()

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when new messages arrive or loading state changes
  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll should trigger on message/loading changes
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [currentConversation?.messages, isLoading])

  const handleSendMessage = (message: string) => {
    runAgent({
      message,
      thread_id: currentConversation?.thread_id,
    })
  }

  const handleClearConversation = () => {
    clearConversation()
  }

  const handleNewConversation = () => {
    startNewConversation()
  }

  const hasMessages =
    currentConversation && currentConversation.messages.length > 0

  return (
    <VStack
      width="full"
      height="full"
      gap={0}
      bg="white"
      borderRadius="lg"
      boxShadow="md"
      overflow="hidden"
    >
      {/* Header */}
      <HStack
        width="full"
        px={4}
        py={3}
        bg="teal.500"
        color="white"
        justify="space-between"
        borderBottom="1px solid"
        borderColor="teal.600"
      >
        <Heading size="md">{title}</Heading>
        <HStack gap={2}>
          {hasMessages && (
            <>
              <Button
                size="sm"
                variant="ghost"
                color="white"
                onClick={handleNewConversation}
                _hover={{ bg: "teal.600" }}
                aria-label="Start new conversation"
              >
                New Chat
              </Button>
              <Button
                size="sm"
                variant="ghost"
                color="white"
                onClick={handleClearConversation}
                _hover={{ bg: "teal.600" }}
                aria-label="Clear conversation"
              >
                <FaTrash />
              </Button>
            </>
          )}
        </HStack>
      </HStack>

      {/* Messages Container */}
      <Box
        ref={messagesContainerRef}
        width="full"
        flex="1"
        overflowY="auto"
        maxHeight={maxHeight}
        bg="gray.50"
        position="relative"
      >
        <Container maxW="container.md" py={4}>
          {!hasMessages && !isLoading && (
            <VStack
              width="full"
              height="full"
              justify="center"
              align="center"
              py={12}
              color="gray.500"
            >
              <Text fontSize="lg" fontWeight="medium">
                Welcome to Agent Chat
              </Text>
              <Text fontSize="sm" textAlign="center" maxW="md">
                Start a conversation by typing a message below. The agent can
                help you with various tasks and answer your questions.
              </Text>
            </VStack>
          )}

          {currentConversation?.messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))}

          {isLoading && <ChatLoadingIndicator />}

          {runError && (
            <Box
              width="full"
              bg="red.50"
              border="1px solid"
              borderColor="red.200"
              borderRadius="md"
              p={4}
              mt={4}
            >
              <Text fontSize="sm" color="red.800" fontWeight="medium">
                Error: {runError.message || "Failed to send message"}
              </Text>
            </Box>
          )}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} />
        </Container>
      </Box>

      {/* Input Area */}
      <ChatInput
        onSubmit={handleSendMessage}
        disabled={isLoading}
        placeholder={inputPlaceholder}
      />
    </VStack>
  )
}
