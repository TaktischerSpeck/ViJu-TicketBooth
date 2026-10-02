// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { usePreview } from './usePreview'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(r => { resolve = r })
  return { promise, resolve }
}
const requests: { signal: AbortSignal; response: ReturnType<typeof deferred<Response>> }[] = []
const response = (blob = Promise.resolve(new Blob(['png']))) => ({ ok: true, blob: () => blob }) as Response
beforeEach(() => {
  vi.useFakeTimers()
  requests.length = 0
  vi.stubGlobal('fetch', vi.fn((_url, init) => {
    const reply = deferred<Response>()
    requests.push({ signal: init.signal, response: reply })
    return reply.promise // Deliberately ignore abort to simulate a late response.
  }))
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => `blob:${requests.length}`) })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals() })
const start = async () => { await act(async () => { vi.advanceTimersByTime(350) }) }

it('aborts A and keeps B when A responds after B', async () => {
  const hook = renderHook(({ poster }) => usePreview({ poster }, true), { initialProps: { poster: 'A' } })
  await start()
  hook.rerender({ poster: 'B' })
  expect(requests[0].signal.aborted).toBe(true)
  expect(hook.result.current.url).toBe('')
  await start()
  await act(async () => { requests[1].response.resolve(response()) })
  expect(hook.result.current.url).toBe('blob:2')
  await act(async () => { requests[0].response.resolve(response()) })
  expect(hook.result.current.url).toBe('blob:2')
  expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
  hook.unmount()
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:2')
})

it('does not publish a blob decoded after removal of the poster', async () => {
  const blob = deferred<Blob>()
  const hook = renderHook(({ enabled }) => usePreview({ poster: 'A' }, enabled), { initialProps: { enabled: true } })
  await start()
  await act(async () => { requests[0].response.resolve(response(blob.promise)) })
  hook.rerender({ enabled: false })
  await act(async () => { blob.resolve(new Blob(['png'])) })
  expect(hook.result.current.url).toBe('')
  expect(URL.createObjectURL).not.toHaveBeenCalled()
})

it('invalidates a completed preview immediately and clears debounce on unmount', async () => {
  const hook = renderHook(({ poster }) => usePreview({ poster }, true), { initialProps: { poster: 'A' } })
  await start()
  await act(async () => { requests[0].response.resolve(response()) })
  hook.rerender({ poster: 'B' })
  expect(hook.result.current.url).toBe('')
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:1')
  hook.unmount()
  await start()
  expect(requests).toHaveLength(1)
})

it('shows a failure and recovers after a new selection', async () => {
  const hook = renderHook(({ poster }) => usePreview({ poster }, true), { initialProps: { poster: 'A' } })
  await start()
  await act(async () => { requests[0].response.resolve({ ok: false, status: 422 } as Response) })
  expect(hook.result.current.error).toContain('422')
  hook.rerender({ poster: 'B' })
  expect(hook.result.current.error).toBe('')
  await start()
  await act(async () => { requests[1].response.resolve(response()) })
  expect(hook.result.current.url).toBe('blob:2')
})

it('does not reuse a revoked URL when switching back to A', async () => {
  const hook = renderHook(({ poster }) => usePreview({ poster }, true), { initialProps: { poster: 'A' } })
  await start()
  await act(async () => { requests[0].response.resolve(response()) })
  hook.rerender({ poster: 'B' })
  hook.rerender({ poster: 'A' })
  expect(hook.result.current.url).toBe('')
  await start()
  await act(async () => { requests[1].response.resolve(response()) })
  expect(hook.result.current.url).toBe('blob:2')
})
