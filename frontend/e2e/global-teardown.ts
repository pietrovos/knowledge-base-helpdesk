import { execSync } from 'node:child_process'
import path from 'node:path'

export default function globalTeardown() {
  if (process.env.E2E_SKIP_RESET) return
  // The demo flow revokes Tier 1's access to Customer Policies. Put the demo data back so the
  // app isn't left in that state for whoever uses it next.
  execSync('make reset', { cwd: path.resolve(import.meta.dirname, '../..'), stdio: 'inherit' })
}
