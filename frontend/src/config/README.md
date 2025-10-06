# Frontend Configuration

This directory contains centralized configuration for the frontend application.

## Feature Flags

Feature flags allow you to enable/disable functionality without code changes. All flags are controlled via environment variables.

### Usage

```tsx
import { features } from '@/config/features'

// Conditional rendering
function MyComponent() {
  return (
    <div>
      {features.agent && <AgentChat />}
    </div>
  )
}

// Conditional logic
if (features.agent) {
  // Initialize agent-related services
  initializeAgentServices()
}

// Use helper functions
import { isFeatureEnabled, getEnabledFeatures } from '@/config/features'

if (isFeatureEnabled('agent')) {
  // Agent feature is enabled
}

const enabled = getEnabledFeatures() // ['agent', ...]
```

### Available Feature Flags

#### `VITE_ENABLE_AGENT`

**Purpose**: Controls visibility of AI Agent/Assistant features

**Environment Variable**: `VITE_ENABLE_AGENT`

**Type**: `boolean`

**Default**: `false`

**Values**:
- `true`, `1` - Enable agent features
- `false`, `0` - Disable agent features (case-insensitive)

**Controls**:
- Agent chat interface
- Agent history viewer
- Agent navigation menu items
- Agent-related API interactions

**Configuration**:

```bash
# .env (development)
VITE_ENABLE_AGENT=false

# .env.production (production)
VITE_ENABLE_AGENT=true
```

**When to Enable**:
- ✅ Development: Enable to test agent features
- ✅ Staging: Enable to validate agent functionality
- ✅ Production: Enable only after agent backend is fully configured and tested

### Adding New Feature Flags

To add a new feature flag:

1. **Add environment variable to TypeScript types** (`vite-env.d.ts`):
   ```typescript
   interface ImportMetaEnv {
     readonly VITE_ENABLE_AGENT?: string
     readonly VITE_ENABLE_NEW_FEATURE?: string  // Add new flag
   }
   ```

2. **Add to features object** (`config/features.ts`):
   ```typescript
   export const features = {
     agent: parseBoolean(import.meta.env.VITE_ENABLE_AGENT, false),
     newFeature: parseBoolean(import.meta.env.VITE_ENABLE_NEW_FEATURE, false),
   } as const
   ```

3. **Document in environment files** (`.env.example`, `.env.local.example`, `.env.production`):
   ```bash
   # New Feature Description
   # Controls [describe what it controls]
   # Default: false
   VITE_ENABLE_NEW_FEATURE=false
   ```

4. **Update this README** with the new flag documentation

### Best Practices

1. **Keep feature checks centralized** - Import from `@/config/features`, not `import.meta.env`
2. **Use meaningful flag names** - `VITE_ENABLE_AGENT` not `VITE_FLAG_1`
3. **Document all flags** - Update `.env.example` and this README
4. **Default to disabled** - New features should be opt-in
5. **Clean up old flags** - Remove flags when features are fully rolled out
6. **Test both states** - Ensure app works with flag enabled AND disabled

### Environment-Specific Configuration

The application supports environment-specific configuration files:

- `.env` - Base configuration (always loaded)
- `.env.local` - Local development overrides (loaded when `APP_ENV=local`)
- `.env.production` - Production overrides (loaded when `APP_ENV=production`)

Feature flags can be set differently per environment:

```bash
# .env.local (development)
VITE_ENABLE_AGENT=true  # Enable for testing

# .env.production (production)
VITE_ENABLE_AGENT=false  # Disable until ready
```

### Troubleshooting

**Flag not working?**
1. Check environment variable is set in `.env`
2. Restart Vite dev server (environment variables are loaded at startup)
3. Verify value is `true` or `1` (case-insensitive)
4. Check browser console for feature flag values: `console.log(features)`

**TypeScript errors?**
1. Ensure flag is added to `ImportMetaEnv` interface in `vite-env.d.ts`
2. Run `npm run type-check` to verify types
