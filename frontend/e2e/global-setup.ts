import { execSync } from 'node:child_process'
import path from 'node:path'

export default function globalSetup() {
  if (process.env.E2E_SKIP_RESET) return
  // Fresh database + seed data, so the demo flow starts from a known state.
  execSync('make reset', { cwd: path.resolve(import.meta.dirname, '../..'), stdio: 'inherit' })
}
