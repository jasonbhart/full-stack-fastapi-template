/**
 * AgentHistory Component
 *
 * Displays paginated agent run history with filtering, search, and Langfuse trace links.
 * Filtering and search are handled server-side for optimal performance with large datasets.
 */

import {
  Badge,
  EmptyState,
  Flex,
  HStack,
  Input,
  Link,
  Table,
  Text,
  VStack,
} from "@chakra-ui/react"
import { useEffect, useState } from "react"
import { FaExternalLinkAlt } from "react-icons/fa"
import { FiSearch } from "react-icons/fi"
import { Button } from "@/components/ui/button"
import { InputGroup } from "@/components/ui/input-group"
import {
  PaginationItems,
  PaginationNextTrigger,
  PaginationPrevTrigger,
  PaginationRoot,
} from "@/components/ui/pagination"
import { Skeleton } from "@/components/ui/skeleton"
import { useAgentRuns } from "@/hooks/useAgent"
import type { AgentRunPublic } from "../types"

const PER_PAGE = 10

/**
 * Get status badge color based on run status
 */
function getStatusColor(status: string): string {
  const statusMap: Record<string, string> = {
    success: "green",
    error: "red",
    timeout: "orange",
    pending: "blue",
  }
  return statusMap[status.toLowerCase()] || "gray"
}

/**
 * Format timestamp to localized date and time
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

/**
 * Truncate text with ellipsis
 */
function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return `${text.substring(0, maxLength)}...`
}

/**
 * Loading skeleton for table rows
 */
function LoadingRows() {
  return (
    <>
      {[...Array(5)].map((_, i) => (
        <Table.Row key={i}>
          <Table.Cell>
            <Skeleton height="20px" />
          </Table.Cell>
          <Table.Cell>
            <Skeleton height="20px" />
          </Table.Cell>
          <Table.Cell>
            <Skeleton height="20px" />
          </Table.Cell>
          <Table.Cell>
            <Skeleton height="20px" />
          </Table.Cell>
          <Table.Cell>
            <Skeleton height="20px" />
          </Table.Cell>
        </Table.Row>
      ))}
    </>
  )
}

/**
 * Empty state when no runs are found
 */
function EmptyHistoryState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <Table.Row>
      <Table.Cell colSpan={5}>
        <EmptyState.Root py={8}>
          <EmptyState.Content>
            <EmptyState.Indicator>
              <FiSearch />
            </EmptyState.Indicator>
            <VStack textAlign="center">
              <EmptyState.Title>
                {hasFilters ? "No matching runs found" : "No agent runs yet"}
              </EmptyState.Title>
              <EmptyState.Description>
                {hasFilters
                  ? "Try adjusting your search or filters"
                  : "Start a conversation with the agent to see your history here"}
              </EmptyState.Description>
            </VStack>
          </EmptyState.Content>
        </EmptyState.Root>
      </Table.Cell>
    </Table.Row>
  )
}

/**
 * Agent history table component
 */
export function AgentHistory() {
  const [page, setPage] = useState(1)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<string | null>(null)

  // Reset to page 1 when filters change
  // biome-ignore lint/correctness/useExhaustiveDependencies: Only run when filters change
  useEffect(() => {
    setPage(1)
  }, [searchQuery, statusFilter])

  const skip = (page - 1) * PER_PAGE

  // Fetch data with server-side filtering
  const { data, isLoading, isPlaceholderData } = useAgentRuns({
    skip,
    limit: PER_PAGE,
    search: searchQuery || null,
    status: statusFilter,
  })

  const runs = data?.data ?? []
  const count = data?.total ?? 0

  // Clear filters handler
  const clearFilters = () => {
    setSearchQuery("")
    setStatusFilter(null)
  }

  const hasActiveFilters = Boolean(searchQuery || statusFilter)

  return (
    <VStack gap={4} width="full" align="stretch">
      {/* Search and Filter Controls */}
      <Flex
        direction={{ base: "column", md: "row" }}
        gap={3}
        width="full"
        align={{ md: "center" }}
      >
        <InputGroup
          flex="1"
          startElement={<FiSearch />}
          endElement={
            searchQuery ? (
              <Button
                variant="ghost"
                size="xs"
                onClick={() => setSearchQuery("")}
              >
                Clear
              </Button>
            ) : undefined
          }
        >
          <Input
            placeholder="Search by input or output..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            size="sm"
          />
        </InputGroup>

        <HStack gap={2}>
          {["success", "error", "timeout"].map((status) => (
            <Button
              key={status}
              size="sm"
              variant={statusFilter === status ? "solid" : "outline"}
              colorPalette={getStatusColor(status)}
              onClick={() =>
                setStatusFilter(statusFilter === status ? null : status)
              }
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Button>
          ))}
        </HStack>

        {hasActiveFilters && (
          <Button size="sm" variant="ghost" onClick={clearFilters}>
            Clear All
          </Button>
        )}
      </Flex>

      {/* Results Count */}
      {count > 0 && (
        <Text fontSize="sm" color="gray.600">
          {hasActiveFilters
            ? `Found ${count} matching run${count !== 1 ? "s" : ""}`
            : `${count} total run${count !== 1 ? "s" : ""}`}
        </Text>
      )}

      {/* Agent Runs Table - Always visible */}
      <Table.Root size={{ base: "sm", md: "md" }}>
        <Table.Header>
          <Table.Row>
            <Table.ColumnHeader w="200px">Date</Table.ColumnHeader>
            <Table.ColumnHeader>Input</Table.ColumnHeader>
            <Table.ColumnHeader w="100px">Status</Table.ColumnHeader>
            <Table.ColumnHeader w="100px">Latency</Table.ColumnHeader>
            <Table.ColumnHeader w="100px">Trace</Table.ColumnHeader>
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {isLoading ? (
            <LoadingRows />
          ) : runs.length === 0 ? (
            <EmptyHistoryState hasFilters={hasActiveFilters} />
          ) : (
            runs.map((run: AgentRunPublic) => (
              <Table.Row key={run.id} opacity={isPlaceholderData ? 0.5 : 1}>
                <Table.Cell>
                  <Text fontSize="sm">{formatTimestamp(run.created_at)}</Text>
                </Table.Cell>

                <Table.Cell>
                  <VStack align="flex-start" gap={1}>
                    <Text fontSize="sm" fontWeight="medium" title={run.input}>
                      {truncateText(run.input, 100)}
                    </Text>
                    <Text fontSize="xs" color="gray.500" title={run.output}>
                      {truncateText(run.output, 80)}
                    </Text>
                  </VStack>
                </Table.Cell>

                <Table.Cell>
                  <Badge colorPalette={getStatusColor(run.status)}>
                    {run.status}
                  </Badge>
                </Table.Cell>

                <Table.Cell>
                  <Text fontSize="sm">{run.latency_ms}ms</Text>
                </Table.Cell>

                <Table.Cell>
                  {run.trace_url ? (
                    <Link
                      href={run.trace_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      color="teal.500"
                      display="flex"
                      alignItems="center"
                      gap={1}
                      fontSize="sm"
                      _hover={{ textDecoration: "underline" }}
                    >
                      <Text>View</Text>
                      <FaExternalLinkAlt size={10} />
                    </Link>
                  ) : (
                    <Text fontSize="sm" color="gray.400">
                      N/A
                    </Text>
                  )}
                </Table.Cell>
              </Table.Row>
            ))
          )}
        </Table.Body>
      </Table.Root>

      {/* Pagination - Always visible when there's data or filters */}
      {(count > 0 || hasActiveFilters) && (
        <Flex justifyContent="flex-end" mt={4}>
          <PaginationRoot
            count={count}
            pageSize={PER_PAGE}
            page={page}
            onPageChange={({ page }) => setPage(page)}
          >
            <Flex gap={2}>
              <PaginationPrevTrigger />
              <PaginationItems />
              <PaginationNextTrigger />
            </Flex>
          </PaginationRoot>
        </Flex>
      )}
    </VStack>
  )
}
