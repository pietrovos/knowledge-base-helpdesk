import { expect, test } from 'vitest'
import { sectionLabel } from './format'

test('section labels drop the repeated document title', () => {
  expect(sectionLabel('Returns and Refunds', 'Returns and Refunds > Refund timing')).toBe('Refund timing')
  expect(sectionLabel('Returns and Refunds', 'Returns and Refunds')).toBe('')
  expect(sectionLabel('FAQ', 'Billing > Invoices')).toBe('Billing › Invoices')
})
