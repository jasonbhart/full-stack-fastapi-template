import path from "node:path"
import { fileURLToPath } from "node:url"
import dotenv from "dotenv"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Load .env.test for Playwright tests, fallback to .env if not found
const testEnvPath = path.join(__dirname, "../../.env.test")
const defaultEnvPath = path.join(__dirname, "../../.env")
dotenv.config({ path: testEnvPath })
// Fallback to .env if .env.test doesn't provide the variables
if (!process.env.FIRST_SUPERUSER) {
  dotenv.config({ path: defaultEnvPath })
}

const { FIRST_SUPERUSER, FIRST_SUPERUSER_PASSWORD } = process.env

if (typeof FIRST_SUPERUSER !== "string") {
  throw new Error("Environment variable FIRST_SUPERUSER is undefined")
}

if (typeof FIRST_SUPERUSER_PASSWORD !== "string") {
  throw new Error("Environment variable FIRST_SUPERUSER_PASSWORD is undefined")
}

export const firstSuperuser = FIRST_SUPERUSER as string
export const firstSuperuserPassword = FIRST_SUPERUSER_PASSWORD as string
