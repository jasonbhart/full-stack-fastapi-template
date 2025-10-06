/**
 * MSW server setup for testing
 *
 * This configures the Mock Service Worker server for intercepting
 * API requests during tests.
 */

import { setupServer } from "msw/node"
import { handlers } from "./handlers"

// Setup MSW server with our request handlers
export const server = setupServer(...handlers)
