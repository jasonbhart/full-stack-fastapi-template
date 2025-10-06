/**
 * ChatLoadingIndicator Component
 *
 * Displays a loading animation when the agent is processing a request.
 */

import { Box, HStack } from "@chakra-ui/react"
import { FaRobot } from "react-icons/fa"
import { SkeletonText } from "@/components/ui/skeleton"

export function ChatLoadingIndicator() {
  return (
    <HStack width="full" justify="flex-start" align="flex-start" gap={3} mb={4}>
      <Box
        flexShrink={0}
        width="32px"
        height="32px"
        borderRadius="full"
        bg="teal.500"
        display="flex"
        alignItems="center"
        justifyContent="center"
        color="white"
      >
        <FaRobot size={16} />
      </Box>

      <Box
        bg="gray.100"
        borderRadius="lg"
        px={4}
        py={2}
        boxShadow="sm"
        maxWidth={{ base: "85%", md: "70%" }}
        minWidth="150px"
      >
        <SkeletonText noOfLines={2} gap={2} />
      </Box>
    </HStack>
  )
}
