import { useEffect, useState } from 'react'

type Preview = { key: string; url: string; error: string }

export function usePreview(ticket: unknown, token: string, enabled: boolean) {
  const body = JSON.stringify(ticket)
  const key = JSON.stringify([body, token])
  const [result, setResult] = useState<Preview | null>(null)
  useEffect(() => {
    setResult(null)
    if (!enabled) return
    const controller = new AbortController()
    let url = ''
    const timer = setTimeout(async () => {
      try {
        const response = await fetch('/api/preview', {
          method: 'POST', signal: controller.signal,
          headers: { 'Content-Type': 'application/json', 'X-Admin-Token': token },
          body,
        })
        if (!response.ok) throw Error(`Vorschau nicht verfügbar (HTTP ${response.status}). Ändere die Auswahl, um es erneut zu versuchen.`)
        const blob = await response.blob()
        if (controller.signal.aborted) return
        url = URL.createObjectURL(blob)
        setResult({ key, url, error: '' })
      } catch (error) {
        if (!controller.signal.aborted) setResult({ key, url: '', error: error instanceof Error ? error.message : 'Vorschau nicht verfügbar.' })
      }
    }, 350)
    return () => {
      clearTimeout(timer)
      controller.abort()
      if (url) URL.revokeObjectURL(url)
    }
  }, [key, body, token, enabled])
  // Invalidate synchronously during render, before effect cleanup or the debounce.
  const current = enabled && result?.key === key ? result : null
  return { url: current?.url || '', error: current?.error || '' }
}
