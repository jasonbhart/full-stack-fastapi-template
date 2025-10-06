/**
 * ChatInput Component
 *
 * Input field for sending messages to the agent.
 * Includes submit button and handles keyboard shortcuts.
 */

import { Box, IconButton, Textarea } from "@chakra-ui/react"
import {
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react"
import { FaPaperPlane } from "react-icons/fa"

interface ChatInputProps {
  onSubmit: (message: string) => void
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({
  onSubmit,
  disabled = false,
  placeholder = "Type your message...",
}: ChatInputProps) {
  const [message, setMessage] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-grow textarea based on content
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current
    if (textarea) {
      // Reset height to auto to get accurate scrollHeight
      textarea.style.height = "auto"
      // Set height to scrollHeight (content height)
      textarea.style.height = `${textarea.scrollHeight}px`
    }
  }, [])

  // Auto-focus on mount and set initial height
  useEffect(() => {
    if (textareaRef.current && !disabled) {
      textareaRef.current.focus()
    }
    adjustHeight()
  }, [disabled, adjustHeight])

  const handleSubmit = () => {
    const trimmedMessage = message.trim()
    if (trimmedMessage && !disabled) {
      onSubmit(trimmedMessage)
      setMessage("")
      // Reset textarea height after clearing
      setTimeout(() => adjustHeight(), 0)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Enter (without Shift)
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <Box
      position="relative"
      width="full"
      bg="white"
      borderTop="1px solid"
      borderColor="gray.200"
      p={4}
    >
      <Box position="relative" width="full">
        <Textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => {
            setMessage(e.target.value)
            adjustHeight()
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          resize="none"
          minHeight="48px"
          maxHeight="200px"
          pr="56px"
          fontSize="sm"
          borderRadius="lg"
          _focus={{
            borderColor: "teal.500",
            boxShadow: "0 0 0 1px var(--chakra-colors-teal-500)",
          }}
          aria-label="Chat message input"
        />
        <IconButton
          position="absolute"
          right="8px"
          bottom="8px"
          size="sm"
          aria-label="Send message"
          onClick={handleSubmit}
          disabled={disabled || !message.trim()}
          colorPalette="teal"
          variant="solid"
        >
          <FaPaperPlane />
        </IconButton>
      </Box>
      <Box mt={2} fontSize="xs" color="gray.500">
        Press <strong>Enter</strong> to send, <strong>Shift+Enter</strong> for
        new line
      </Box>
    </Box>
  )
}
