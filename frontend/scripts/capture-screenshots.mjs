// Regenerates docs/screenshots from a freshly seeded stack: `make reset && node scripts/capture-screenshots.mjs`
import { chromium } from '@playwright/test'
import path from 'node:path'

const BASE = process.env.BASE_URL ?? 'http://localhost:5173'
const OUT = path.resolve(import.meta.dirname, '../../docs/screenshots')
const H = { 'X-Requested-With': 'supportlens' }

const browser = await chromium.launch()
async function session(email) {
  const page = await (await browser.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 })).newPage()
  await page.goto(`${BASE}/login`)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill('supportlens-demo')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('heading', { name: 'Inbox' }).waitFor()
  return page
}
const shot = (page, name) => page.screenshot({ path: path.join(OUT, `${name}.png`) })
const draft = async (page, id, question) => {
  await page.request.post(`${BASE}/api/tickets/${id}/drafts`, { headers: H, data: question ? { question } : {} })
}

const alex = await session('alex@supportlens.dev')
const admin = await session('admin@supportlens.dev')

// Some realistic activity first, so queues and the dashboard aren't empty.
for (const id of [2, 4, 5, 6, 8, 9, 14, 16]) await draft(alex, id)
await alex.waitForTimeout(3000)

await alex.goto(`${BASE}/tickets`)
await alex.waitForLoadState('networkidle')
await shot(alex, 'inbox')

await alex.goto(`${BASE}/tickets/1`)
await alex.getByRole('button', { name: 'Draft reply' }).click()
await alex.getByTestId('draft-reply').waitFor()
await shot(alex, 'cited-draft')
await alex.getByTestId('draft-reply').getByRole('button', { name: /Citation 1/ }).first().click()
await alex.getByTestId('evidence-passage').waitFor()
await shot(alex, 'evidence')
await alex.getByRole('button', { name: 'Close evidence' }).click()

await alex.goto(`${BASE}/tickets/10`)
await alex.getByRole('button', { name: 'Draft reply' }).click()
await alex.getByTestId('insufficient-evidence').waitFor()
await shot(alex, 'insufficient-evidence')
await alex.getByRole('button', { name: 'Create knowledge-gap task' }).click()
await alex.getByText(/Knowledge-gap task #\d+ created/).waitFor()
await alex.goto(`${BASE}/knowledge-gaps`)
await alex.getByRole('list', { name: 'Knowledge gaps' }).waitFor()
await shot(alex, 'knowledge-gaps')

// Provider outage drill: trip the breaker with real requests, show what agents see, then recover.
await admin.request.put(`${BASE}/api/system/chaos`, { headers: H, data: { mode: 'error' } })
for (let i = 0; i < 3; i++) {
  await draft(alex, 6)
  await alex.waitForTimeout(800)
}
await alex.goto(`${BASE}/tickets/6`)
await alex.getByTestId('degraded-banner').waitFor()
await alex.waitForTimeout(500)
await shot(alex, 'degraded-mode')
await admin.goto(`${BASE}/admin/system`)
await admin.waitForLoadState('networkidle')
await shot(admin, 'system')
await admin.request.put(`${BASE}/api/system/chaos`, { headers: H, data: { mode: 'none' } })

await admin.goto(`${BASE}/admin/usage`)
await admin.waitForLoadState('networkidle')
await admin.waitForTimeout(500)
await admin.screenshot({ path: path.join(OUT, 'usage.png'), fullPage: true })

await admin.goto(`${BASE}/collections/1`)
await admin.waitForLoadState('networkidle')
await shot(admin, 'knowledge-access')

await browser.close()
console.log(`screenshots written to ${OUT}`)
