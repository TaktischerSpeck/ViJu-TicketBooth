import { afterEach, expect, it, vi } from 'vitest'
import { germanDate, idempotencyKey, validGermanDate } from './ticketInput'

afterEach(() => vi.unstubAllGlobals())

it('shows old ISO dates in German format and rejects invalid dates', () => {
  expect(germanDate('1999-09-02')).toBe('02.09.1999')
  expect(germanDate('02091999')).toBe('02.09.1999')
  expect(validGermanDate('02.09.1999')).toBe(true)
  expect(validGermanDate('31.02.1999')).toBe(false)
  expect(validGermanDate('')).toBe(true)
})

it('creates a print idempotency key when randomUUID is unavailable', () => {
  vi.stubGlobal('crypto', {getRandomValues: (bytes: Uint8Array) => bytes.fill(42)})
  expect(idempotencyKey()).toBe('2a'.repeat(16))
})
