/**
 * Test utilities and helpers
 *
 * Provides common testing utilities like custom render functions
 * with providers, mock data factories, and test helpers.
 */

import { ChakraProvider, defaultSystem } from "@chakra-ui/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { type RenderOptions, render } from "@testing-library/react"
import type { ReactElement, ReactNode } from "react"
import { AgentProvider } from "@/features/agent/context"

/**
 * Create a new QueryClient for each test to ensure isolation
 */
export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries in tests
        gcTime: 0, // Disable cache time
      },
      mutations: {
        retry: false,
      },
    },
  })
}

/**
 * Wrapper component that provides all necessary context providers for tests
 */
interface AllProvidersProps {
  children: ReactNode
  queryClient?: QueryClient
}

function AllProviders({
  children,
  queryClient = createTestQueryClient(),
}: AllProvidersProps) {
  return (
    <ChakraProvider value={defaultSystem}>
      <QueryClientProvider client={queryClient}>
        <AgentProvider>{children}</AgentProvider>
      </QueryClientProvider>
    </ChakraProvider>
  )
}

/**
 * Custom render function that includes all necessary providers
 */
export interface CustomRenderOptions extends Omit<RenderOptions, "wrapper"> {
  queryClient?: QueryClient
}

export function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {},
) {
  const { queryClient, ...renderOptions } = options

  // Use the same client instance for both the provider and the return value
  const client = queryClient ?? createTestQueryClient()

  const Wrapper = ({ children }: { children: ReactNode }) => (
    <AllProviders queryClient={client}>{children}</AllProviders>
  )

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient: client,
  }
}

/**
 * Wait for loading states to complete
 * Useful for testing components with async data loading
 */
export async function waitForLoadingToFinish() {
  const { waitFor } = await import("@testing-library/react")
  await waitFor(() => {
    const loadingElements = document.querySelectorAll('[aria-busy="true"]')
    expect(loadingElements.length).toBe(0)
  })
}

// Re-export everything from testing library
export * from "@testing-library/react"
export { default as userEvent } from "@testing-library/user-event"
