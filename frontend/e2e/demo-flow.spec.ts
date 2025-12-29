import { expect, test, type Browser, type Page } from '@playwright/test'
import path from 'node:path'

const PASSWORD = 'supportlens-demo'

async function signIn(browser: Browser, email: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage()
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('heading', { name: 'Inbox' })).toBeVisible()
  return page
}

async function createTicket(page: Page, subject: string, body: string): Promise<number> {
  const res = await page.request.post('/api/tickets', {
    headers: { 'X-Requested-With': 'supportlens' },
    data: { subject, body, customer_name: 'Jamie Fox', customer_email: 'jamie@example.com' },
  })
  expect(res.ok()).toBeTruthy()
  return (await res.json()).id
}

test('upload → cited answer → evidence → revoke → no retrieval → unsupported question → knowledge gap', async ({ browser }) => {
  const admin = await signIn(browser, 'admin@supportlens.dev')
  const agent = await signIn(browser, 'alex@supportlens.dev')

  // 1. Admin uploads a new policy to Customer Policies (readable by Tier 1 Support).
  await admin.getByRole('link', { name: 'Knowledge', exact: true }).click()
  await admin.getByRole('link', { name: /Customer Policies/ }).click()
  await admin.getByTestId('file-input').setInputFiles(path.join(import.meta.dirname, 'fixtures/loyalty-program.md'))
  const row = admin.getByRole('listitem').filter({ hasText: 'Kestrel Rewards Loyalty Program' })
  await expect(row.getByText('Live')).toBeVisible()

  // 2. The agent drafts a reply on a ticket about it: the answer cites the new policy.
  const ticketId = await createTicket(agent, 'Kestrel Rewards points', 'How many Kestrel Rewards points do I earn for every dollar I spend on hardware?')
  await agent.goto(`/tickets/${ticketId}`)
  await agent.getByRole('button', { name: 'Draft reply' }).click()
  const reply = agent.getByTestId('draft-reply')
  await expect(reply).toContainText('5 points')

  // 3. Clicking the citation shows the exact supporting passage.
  await reply.getByRole('button', { name: /Citation 1/ }).first().click()
  const evidence = agent.getByRole('dialog', { name: /Evidence for citation/ })
  await expect(evidence.getByTestId('evidence-passage')).toContainText('5 points for every dollar')
  await expect(evidence.getByRole('link', { name: 'Kestrel Rewards Loyalty Program' })).toBeVisible()
  await evidence.getByRole('button', { name: 'Close evidence' }).click()

  // 4. Admin revokes Tier 1 Support's access to Customer Policies.
  await admin.getByRole('button', { name: 'Revoke Tier 1 Support' }).click()
  await expect(admin.getByRole('list', { name: 'Grants' })).not.toContainText('Tier 1 Support')

  // 5. Retrieval no longer uses it: the old citation is now hidden, and a fresh draft
  //    finds no evidence (the policy is not in any collection Alex can still read).
  await agent.reload()
  await agent.getByTestId('draft-reply').getByRole('button', { name: /Citation 1/ }).first().click()
  await expect(agent.getByText('You no longer have access to this source')).toBeVisible()
  await agent.getByRole('button', { name: 'Close evidence' }).click()
  await agent.getByRole('button', { name: 'Regenerate' }).click()
  await expect(agent.getByTestId('insufficient-evidence')).toBeVisible()
  await expect(agent.getByTestId('draft-reply')).toHaveCount(0)

  // 6. An unsupported question gets an explicit "insufficient evidence" and becomes a
  //    knowledge-gap task.
  const giftId = await createTicket(agent, 'Gift wrapping', 'Can you gift wrap my order and include a handwritten card?')
  await agent.goto(`/tickets/${giftId}`)
  await agent.getByRole('button', { name: 'Draft reply' }).click()
  const insufficient = agent.getByTestId('insufficient-evidence')
  await expect(insufficient).toContainText('Insufficient evidence')
  await insufficient.getByRole('button', { name: 'Create knowledge-gap task' }).click()
  await expect(insufficient.getByText(/Knowledge-gap task #\d+ created/)).toBeVisible()
  await insufficient.getByRole('link', { name: 'view queue' }).click()
  await expect(agent.getByRole('list', { name: 'Knowledge gaps' })).toContainText('gift wrap my order')
})
