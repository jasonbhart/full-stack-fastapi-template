/**
 * Vitest test setup
 *
 * This file is executed before all tests and sets up:
 * - Jest DOM matchers
 * - MSW server for API mocking
 * - Global test utilities
 */

import "@testing-library/jest-dom"
import { cleanup } from "@testing-library/react"
import { afterAll, afterEach, beforeAll } from "vitest"
import { server } from "./mocks/server"

// Start MSW server before all tests
beforeAll(() => {
  server.listen({ onUnhandledRequest: "warn" })
})

// Reset handlers and cleanup after each test
afterEach(() => {
  server.resetHandlers()
  cleanup()
})

// Stop MSW server after all tests
afterAll(() => {
  server.close()
})
