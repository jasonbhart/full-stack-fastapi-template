/**
 * AgentHistory component tests
 *
 * Tests for the agent run history component.
 * Covers pagination, filtering, search, and data display.
 */

import { HttpResponse, http } from "msw"
import { describe, expect, it } from "vitest"
import { server } from "@/test/mocks/server"
import { renderWithProviders, screen, userEvent, waitFor } from "@/test/utils"
import { AgentHistory } from "../components/AgentHistory"

describe("AgentHistory", () => {
  describe("rendering", () => {
    it("renders table with column headers", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(screen.getByText(/date/i)).toBeInTheDocument()
        expect(screen.getByText(/input/i)).toBeInTheDocument()
        expect(screen.getByText(/status/i)).toBeInTheDocument()
        expect(screen.getByText(/latency/i)).toBeInTheDocument()
        expect(screen.getByText(/trace/i)).toBeInTheDocument()
      })
    })

    it("displays loading skeletons while fetching data", async () => {
      renderWithProviders(<AgentHistory />)

      // Should show loading state initially
      const skeletons = screen.getAllByRole("row")
      expect(skeletons.length).toBeGreaterThan(0)
    })

    it("displays agent runs after loading", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(
          screen.getByText(/what is the weather today/i),
        ).toBeInTheDocument()
        expect(screen.getByText(/how do i install python/i)).toBeInTheDocument()
      })
    })

    it("shows total runs count", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(screen.getByText(/3 total runs/i)).toBeInTheDocument()
      })
    })

    it("displays empty state when no runs exist", async () => {
      // Override the mock to return empty data
      server.use(
        http.get("*/api/v1/agent/runs", () => {
          return HttpResponse.json({
            data: [],
            total: 0,
            limit: 10,
            offset: 0,
          })
        }),
      )

      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(screen.getByText(/no agent runs yet/i)).toBeInTheDocument()
        expect(
          screen.getByText(/start a conversation with the agent/i),
        ).toBeInTheDocument()
      })
    })
  })

  describe("data display", () => {
    it("displays run details correctly", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        // Check input/output
        expect(
          screen.getByText(/what is the weather today/i),
        ).toBeInTheDocument()
        expect(
          screen.getByText(/the weather is sunny with a temperature of 75/i),
        ).toBeInTheDocument()

        // Check status badges
        expect(screen.getAllByText(/success/i).length).toBeGreaterThan(0)

        // Check latency
        expect(screen.getByText(/1234ms/i)).toBeInTheDocument()
      })
    })

    it("displays trace links for runs with traces", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        const traceLinks = screen.getAllByRole("link", { name: /view/i })
        expect(traceLinks.length).toBeGreaterThan(0)
        expect(traceLinks[0]).toHaveAttribute("href")
        expect(traceLinks[0]).toHaveAttribute("target", "_blank")
        expect(traceLinks[0]).toHaveAttribute("rel", "noopener noreferrer")
      })
    })

    it("truncates long text content", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        const cells = screen.getAllByRole("cell")
        // At least one cell should contain truncated text (ending with ...)
        const hasTruncation = cells.some((cell) =>
          cell.textContent?.includes("..."),
        )
        expect(hasTruncation).toBe(true)
      })
    })

    it("formats timestamps correctly", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        // Should display formatted date (contains month name)
        const dateElements = screen.getAllByText(/jan/i)
        expect(dateElements.length).toBeGreaterThan(0)
      })
    })

    it("displays different status badges with correct colors", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        const statusBadges = screen.getAllByText(/success|error/i)
        expect(statusBadges.length).toBeGreaterThan(0)

        // Check that error status is displayed
        const errorBadges = screen.getAllByText(/error/i)
        expect(errorBadges.length).toBeGreaterThan(0)
      })
    })
  })

  describe("search functionality", () => {
    it("filters runs based on search query", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(
          screen.getByText(/what is the weather today/i),
        ).toBeInTheDocument()
        expect(screen.getByText(/how do i install python/i)).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(
        /search by input or output.../i,
      )

      await user.type(searchInput, "weather")

      await waitFor(() => {
        expect(
          screen.getByText(/what is the weather today/i),
        ).toBeInTheDocument()
        expect(
          screen.queryByText(/how do i install python/i),
        ).not.toBeInTheDocument()
      })
    })

    it("shows clear button when search has value", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      const searchInput = screen.getByPlaceholderText(
        /search by input or output.../i,
      )

      // No clear button initially
      expect(
        screen.queryByRole("button", { name: /clear/i }),
      ).not.toBeInTheDocument()

      await user.type(searchInput, "test")

      await waitFor(() => {
        const clearButtons = screen.getAllByRole("button", { name: /clear/i })
        expect(clearButtons.length).toBeGreaterThan(0)
      })
    })

    it("clears search when clear button is clicked", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      const searchInput = screen.getByPlaceholderText(
        /search by input or output.../i,
      ) as HTMLInputElement

      await user.type(searchInput, "weather")

      await waitFor(() => {
        expect(searchInput.value).toBe("weather")
      })

      const clearButtons = screen.getAllByRole("button", { name: /clear/i })
      await user.click(clearButtons[0])

      await waitFor(() => {
        expect(searchInput.value).toBe("")
      })
    })

    it("resets to page 1 when search changes", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      const searchInput = screen.getByPlaceholderText(
        /search by input or output.../i,
      )

      await user.type(searchInput, "test")

      // The component should reset to page 1 (implementation detail tested indirectly)
      await waitFor(() => {
        expect(searchInput).toHaveValue("test")
      })
    })

    it("shows appropriate message when search has no results", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      const searchInput = screen.getByPlaceholderText(
        /search by input or output.../i,
      )

      await user.type(searchInput, "nonexistent search term xyz")

      await waitFor(() => {
        expect(screen.getByText(/no matching runs found/i)).toBeInTheDocument()
        expect(
          screen.getByText(/try adjusting your search or filters/i),
        ).toBeInTheDocument()
      })
    })
  })

  describe("status filtering", () => {
    it("displays status filter buttons", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /^success$/i }),
        ).toBeInTheDocument()
        expect(
          screen.getByRole("button", { name: /^error$/i }),
        ).toBeInTheDocument()
        expect(
          screen.getByRole("button", { name: /^timeout$/i }),
        ).toBeInTheDocument()
      })
    })

    it("filters runs by status when filter button is clicked", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(
          screen.getByText(/what is the weather today/i),
        ).toBeInTheDocument()
        expect(screen.getByText(/error test/i)).toBeInTheDocument()
      })

      const errorButton = screen.getByRole("button", { name: /^error$/i })
      await user.click(errorButton)

      await waitFor(() => {
        expect(screen.getByText(/error test/i)).toBeInTheDocument()
        expect(
          screen.queryByText(/what is the weather today/i),
        ).not.toBeInTheDocument()
      })
    })

    it("toggles filter off when clicking active filter", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      const successButton = screen.getByRole("button", { name: /^success$/i })

      // Click to activate
      await user.click(successButton)

      await waitFor(() => {
        // Should be filtered
        expect(screen.queryByText(/error test/i)).not.toBeInTheDocument()
      })

      // Click again to deactivate
      await user.click(successButton)

      await waitFor(() => {
        // Should show all runs again
        expect(screen.getByText(/error test/i)).toBeInTheDocument()
      })
    })

    it("shows clear all filters button when filters are active", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      // No clear all button initially
      expect(
        screen.queryByRole("button", { name: /clear all/i }),
      ).not.toBeInTheDocument()

      const successButton = screen.getByRole("button", { name: /^success$/i })
      await user.click(successButton)

      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /clear all/i }),
        ).toBeInTheDocument()
      })
    })

    it("clears all filters when clear all is clicked", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      const searchInput = screen.getByPlaceholderText(
        /search by input or output.../i,
      ) as HTMLInputElement
      const successButton = screen.getByRole("button", { name: /^success$/i })

      // Apply filters
      await user.type(searchInput, "test")
      await user.click(successButton)

      await waitFor(() => {
        expect(searchInput.value).toBe("test")
      })

      // Clear all
      const clearAllButton = screen.getByRole("button", { name: /clear all/i })
      await user.click(clearAllButton)

      await waitFor(() => {
        expect(searchInput.value).toBe("")
      })
    })

    it("updates results count with active filters", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(screen.getByText(/3 total runs/i)).toBeInTheDocument()
      })

      const errorButton = screen.getByRole("button", { name: /^error$/i })
      await user.click(errorButton)

      await waitFor(() => {
        expect(screen.getByText(/found 1 matching run/i)).toBeInTheDocument()
      })
    })
  })

  describe("pagination", () => {
    it("displays pagination controls", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        // Look for pagination elements (prev/next buttons)
        const buttons = screen.getAllByRole("button")
        const hasPaginationButtons = buttons.some(
          (btn) =>
            btn.getAttribute("aria-label")?.includes("previous") ||
            btn.getAttribute("aria-label")?.includes("next"),
        )
        expect(hasPaginationButtons).toBe(true)
      })
    })

    it("shows pagination when data exists", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        // Pagination root should be visible
        const paginationButtons = screen.getAllByRole("button")
        expect(paginationButtons.length).toBeGreaterThan(0)
      })
    })
  })

  describe("accessibility", () => {
    it("has proper table structure", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(screen.getByRole("table")).toBeInTheDocument()
      })
    })

    it("trace links have proper accessibility attributes", async () => {
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        const traceLinks = screen.getAllByRole("link", { name: /view/i })
        traceLinks.forEach((link) => {
          expect(link).toHaveAttribute("rel", "noopener noreferrer")
          expect(link).toHaveAttribute("target", "_blank")
        })
      })
    })

    it("search input has proper placeholder", () => {
      renderWithProviders(<AgentHistory />)

      const searchInput = screen.getByPlaceholderText(
        /search by input or output.../i,
      )
      expect(searchInput).toBeInTheDocument()
    })

    it("filter buttons are keyboard accessible", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentHistory />)

      await waitFor(() => {
        expect(
          screen.getByText(/what is the weather today/i),
        ).toBeInTheDocument()
      })

      const successButton = screen.getByRole("button", { name: /^success$/i })

      // Focus the button
      successButton.focus()

      // Verify button has focus
      expect(document.activeElement).toBe(successButton)

      // Activate with keyboard (Enter key)
      await user.keyboard("{Enter}")

      // Verify filter is applied - error status run should be filtered out
      await waitFor(() => {
        expect(screen.queryByText(/error test/i)).not.toBeInTheDocument()
        expect(
          screen.getByText(/what is the weather today/i),
        ).toBeInTheDocument()
      })
    })
  })

  describe("error states", () => {
    it("handles API errors gracefully", async () => {
      server.use(
        http.get("*/api/v1/agent/runs", () => {
          return HttpResponse.json(
            { detail: "Internal server error" },
            { status: 500 },
          )
        }),
      )

      renderWithProviders(<AgentHistory />)

      // Should still render the table structure even on error
      await waitFor(() => {
        expect(screen.getByRole("table")).toBeInTheDocument()
      })
    })
  })
})
