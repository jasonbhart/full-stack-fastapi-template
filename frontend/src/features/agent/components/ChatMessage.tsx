/**
 * ChatMessage Component
 *
 * Displays an individual message in the agent chat interface.
 * Supports user and agent messages with different styling.
 */

import { Box, HStack, Link, Text, VStack } from "@chakra-ui/react"
import { FaExternalLinkAlt, FaRobot, FaUser } from "react-icons/fa"
import type { AgentMessage } from "../types"

interface ChatMessageProps {
  message: AgentMessage
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user"
  const isError = message.status === "error"

  return (
    <HStack
      width="full"
      justify={isUser ? "flex-end" : "flex-start"}
      align="flex-start"
      gap={3}
      mb={4}
    >
      {!isUser && (
        <Box
          flexShrink={0}
          width="32px"
          height="32px"
          borderRadius="full"
          bg={isError ? "red.500" : "teal.500"}
          display="flex"
          alignItems="center"
          justifyContent="center"
          color="white"
        >
          <FaRobot size={16} />
        </Box>
      )}

      <VStack
        align={isUser ? "flex-end" : "flex-start"}
        gap={1}
        maxWidth={{ base: "85%", md: "70%" }}
      >
        <Box
          bg={isUser ? "teal.500" : isError ? "red.50" : "gray.100"}
          color={isUser ? "white" : isError ? "red.800" : "gray.800"}
          borderRadius="lg"
          px={4}
          py={2}
          boxShadow="sm"
          wordBreak="break-word"
        >
          <Text fontSize="sm" whiteSpace="pre-wrap">
            {message.content}
          </Text>
        </Box>

        <HStack gap={2} fontSize="xs" color="gray.500">
          <Text>
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </Text>

          {message.latency_ms && <Text>• {message.latency_ms}ms</Text>}

          {message.trace_url && (
            <Link
              href={message.trace_url}
              target="_blank"
              rel="noopener noreferrer"
              color="teal.500"
              display="flex"
              alignItems="center"
              gap={1}
              _hover={{ textDecoration: "underline" }}
            >
              <Text>View Trace</Text>
              <FaExternalLinkAlt size={10} />
            </Link>
          )}
        </HStack>
      </VStack>

      {isUser && (
        <Box
          flexShrink={0}
          width="32px"
          height="32px"
          borderRadius="full"
          bg="teal.600"
          display="flex"
          alignItems="center"
          justifyContent="center"
          color="white"
        >
          <FaUser size={14} />
        </Box>
      )}
    </HStack>
  )
}
