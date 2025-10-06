/**
 * Feature flags configuration
 *
 * Centralized feature flag management for the frontend application.
 * All flags are controlled via environment variables (VITE_* prefix required).
 *
 * Usage:
 * ```tsx
 * import { features } from '@/config/features'
 *
 * // Conditional rendering
 * {features.agent && <AgentChat />}
 *
 * // Conditional logic
 * if (features.agent) {
 *   // Initialize agent-related services
 * }
 * ```
 */

/**
 * Safely parse a boolean environment variable
 * @param value - Environment variable value
 * @param defaultValue - Default value if env var is not set
 * @returns Parsed boolean value
 */
const parseBoolean = (
  value: string | undefined,
  defaultValue = false,
): boolean => {
  if (value === undefined || value === "") {
    return defaultValue
  }
  return value.toLowerCase() === "true" || value === "1"
}

/**
 * Feature flags object
 *
 * All feature flags should be defined here to maintain a single source of truth.
 */
export const features = {
  /**
   * Agent/AI Assistant feature flag
   *
   * Controls visibility of:
   * - Agent chat interface
   * - Agent history viewer
   * - Agent navigation menu items
   * - Agent-related API interactions
   *
   * Environment variable: VITE_ENABLE_AGENT
   * Default: false
   */
  agent: parseBoolean(import.meta.env.VITE_ENABLE_AGENT, false),
} as const

/**
 * Type-safe feature flag keys
 */
export type FeatureFlag = keyof typeof features

/**
 * Check if a specific feature is enabled
 * @param flag - Feature flag to check
 * @returns true if feature is enabled
 */
export const isFeatureEnabled = (flag: FeatureFlag): boolean => {
  return features[flag]
}

/**
 * Get all enabled features
 * @returns Array of enabled feature names
 */
export const getEnabledFeatures = (): FeatureFlag[] => {
  return (Object.keys(features) as FeatureFlag[]).filter((key) => features[key])
}
