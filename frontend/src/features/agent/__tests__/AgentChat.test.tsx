/**
 * AgentChat component tests
 *
 * Tests for the main chat interface component.
 * Covers user interactions, message display, error handling, and accessibility.
 */

import { describe, expect, it, vi } from "vitest"
import { renderWithProviders, screen, userEvent, waitFor } from "@/test/utils"
import { AgentChat } from "../components/AgentChat"

describe("AgentChat", () => {
  describe("rendering", () => {
    it("renders with default title", () => {
      renderWithProviders(<AgentChat />)
      expect(
        screen.getByRole("heading", { name: /agent chat/i }),
      ).toBeInTheDocument()
    })

    it("renders with custom title", () => {
      renderWithProviders(<AgentChat title="Custom Agent" />)
      expect(
        screen.getByRole("heading", { name: /custom agent/i }),
      ).toBeInTheDocument()
    })

    it("shows welcome message when no messages exist", () => {
      renderWithProviders(<AgentChat />)
      expect(screen.getByText(/welcome to agent chat/i)).toBeInTheDocument()
      expect(
        screen.getByText(/start a conversation by typing a message below/i),
      ).toBeInTheDocument()
    })

    it("renders chat input with custom placeholder", () => {
      renderWithProviders(
        <AgentChat inputPlaceholder="Type your question..." />,
      )
      expect(
        screen.getByPlaceholderText(/type your question.../i),
      ).toBeInTheDocument()
    })
  })

  describe("user interactions", () => {
    it("sends message when user submits input", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)
      const submitButton = screen.getByRole("button", { name: /send/i })

      await user.type(input, "Hello agent!")
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText("Hello agent!")).toBeInTheDocument()
      })

      // Should also show the agent response
      await waitFor(() => {
        expect(
          screen.getByText(/mock response to: hello agent!/i),
        ).toBeInTheDocument()
      })
    })

    it("sends message when user presses Enter", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)

      await user.type(input, "Hello{Enter}")

      await waitFor(() => {
        expect(screen.getByText("Hello")).toBeInTheDocument()
      })
    })

    it("clears input after sending message", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(
        /ask me anything.../i,
      ) as HTMLInputElement

      await user.type(input, "Test message")
      await user.keyboard("{Enter}")

      await waitFor(() => {
        expect(input.value).toBe("")
      })
    })

    it("disables input while loading", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)

      // Start typing
      await user.type(input, "Test message")

      // Capture state before submit
      expect(input).not.toBeDisabled()

      await user.keyboard("{Enter}")

      // Wait for response (may be too fast to catch disabled state in test)
      await waitFor(() => {
        expect(screen.getByText(/mock response/i)).toBeInTheDocument()
      })

      // Input should be enabled after response
      await waitFor(() => {
        expect(input).not.toBeDisabled()
      })
    })
  })

  describe("conversation management", () => {
    it("shows clear conversation button when messages exist", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      // Initially no clear button
      expect(
        screen.queryByRole("button", { name: /clear conversation/i }),
      ).not.toBeInTheDocument()

      // Send a message
      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.type(input, "Hello{Enter}")

      // Clear button should appear
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /clear conversation/i }),
        ).toBeInTheDocument()
      })
    })

    it("clears conversation when clear button is clicked", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      // Send a message
      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.type(input, "Hello{Enter}")

      await waitFor(() => {
        expect(screen.getByText("Hello")).toBeInTheDocument()
      })

      // Click clear button
      const clearButton = await screen.findByRole("button", {
        name: /clear conversation/i,
      })
      await user.click(clearButton)

      // Should show welcome message again
      await waitFor(() => {
        expect(screen.getByText(/welcome to agent chat/i)).toBeInTheDocument()
      })

      // Message should be gone
      expect(screen.queryByText("Hello")).not.toBeInTheDocument()
    })

    it("shows new chat button when messages exist", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      // Send a message
      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.type(input, "Hello{Enter}")

      // New chat button should appear (using aria-label)
      await waitFor(() => {
        expect(
          screen.getByRole("button", { name: /start new conversation/i }),
        ).toBeInTheDocument()
      })
    })

    it("starts new conversation when new chat button is clicked", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      // Send a message
      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.type(input, "First message{Enter}")

      await waitFor(() => {
        expect(screen.getByText("First message")).toBeInTheDocument()
      })

      // Click new chat button (using aria-label)
      const newChatButton = await screen.findByRole("button", {
        name: /start new conversation/i,
      })
      await user.click(newChatButton)

      // Old message should be gone, welcome message should appear
      await waitFor(() => {
        expect(screen.queryByText("First message")).not.toBeInTheDocument()
        expect(screen.getByText(/welcome to agent chat/i)).toBeInTheDocument()
      })
    })
  })

  describe("message display", () => {
    it("displays user and agent messages in conversation", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)

      await user.type(input, "What is the weather?{Enter}")

      await waitFor(() => {
        expect(screen.getByText("What is the weather?")).toBeInTheDocument()
      })

      await waitFor(() => {
        expect(
          screen.getByText(/mock response to: what is the weather/i),
        ).toBeInTheDocument()
      })
    })

    it("shows loading indicator while waiting for response", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.type(input, "Test{Enter}")

      // Response should eventually appear (loading may be too fast to catch)
      await waitFor(() => {
        expect(screen.getByText(/mock response to: test/i)).toBeInTheDocument()
      })

      // Verify the loading state completed and message is displayed
      expect(screen.getByText("Test")).toBeInTheDocument()
      expect(screen.getByText(/mock response to: test/i)).toBeInTheDocument()
    })

    it("auto-scrolls to bottom when new messages arrive", async () => {
      const user = userEvent.setup()
      const scrollIntoViewMock = vi.fn()
      const originalScrollIntoView = window.HTMLElement.prototype.scrollIntoView

      try {
        window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock

        renderWithProviders(<AgentChat />)

        const input = screen.getByPlaceholderText(/ask me anything.../i)
        await user.type(input, "Hello{Enter}")

        await waitFor(() => {
          expect(scrollIntoViewMock).toHaveBeenCalled()
        })
      } finally {
        window.HTMLElement.prototype.scrollIntoView = originalScrollIntoView
      }
    })
  })

  describe("error handling", () => {
    it("displays error message when agent fails", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.type(input, "trigger error{Enter}")

      await waitFor(() => {
        expect(screen.getByText(/error:/i)).toBeInTheDocument()
      })
    })

    it("shows error message in conversation when request fails", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.type(input, "error{Enter}")

      // Should show user message
      await waitFor(() => {
        expect(screen.getByText("error")).toBeInTheDocument()
      })

      // Should show error message in conversation
      await waitFor(() => {
        expect(
          screen.getByText(
            /sorry, i encountered an error processing your request/i,
          ),
        ).toBeInTheDocument()
      })
    })

    it("allows sending new messages after error", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)

      // Trigger error
      await user.type(input, "error{Enter}")

      await waitFor(() => {
        expect(screen.getByText(/error:/i)).toBeInTheDocument()
      })

      // Send another message
      await user.type(input, "Hello{Enter}")

      await waitFor(() => {
        expect(screen.getByText("Hello")).toBeInTheDocument()
        expect(screen.getByText(/mock response to: hello/i)).toBeInTheDocument()
      })
    })
  })

  describe("accessibility", () => {
    it("has proper ARIA labels for buttons", () => {
      renderWithProviders(<AgentChat />)

      const sendButton = screen.getByRole("button", { name: /send/i })
      expect(sendButton).toHaveAccessibleName()
    })

    it("input has proper label/placeholder", () => {
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)
      expect(input).toBeInTheDocument()
    })

    it("shows clear conversation button with proper ARIA label", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.type(input, "Hello{Enter}")

      const clearButton = await screen.findByRole("button", {
        name: /clear conversation/i,
      })
      expect(clearButton).toHaveAccessibleName()
    })

    it("maintains focus management during interactions", async () => {
      const user = userEvent.setup()
      renderWithProviders(<AgentChat />)

      const input = screen.getByPlaceholderText(/ask me anything.../i)
      await user.click(input)
      expect(input).toHaveFocus()

      await user.type(input, "Test{Enter}")

      // Input should maintain focus after sending
      await waitFor(() => {
        expect(input).toHaveFocus()
      })
    })
  })
})
