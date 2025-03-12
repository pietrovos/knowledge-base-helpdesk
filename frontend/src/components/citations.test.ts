import { expect, test } from 'vitest'
import { parseCitations, stripCitations } from './citations'

test('parses single and grouped markers', () => {
  expect(parseCitations('A [1]. B [2, 3].')).toEqual([
    { kind: 'text', text: 'A ' },
    { kind: 'cite', chunkId: 1 },
    { kind: 'text', text: '. B ' },
    { kind: 'cite', chunkId: 2 },
    { kind: 'cite', chunkId: 3 },
    { kind: 'text', text: '.' },
  ])
})

test('strips markers for the customer', () => {
  expect(stripCitations('Hi,\n\nRefunds take 5 days [12][13]. Thanks [9].')).toBe('Hi,\n\nRefunds take 5 days. Thanks.')
})
