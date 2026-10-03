export function germanDate(value: string): string {
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (iso) return `${iso[3]}.${iso[2]}.${iso[1]}`
  const digits = value.replace(/\D/g, '')
  return digits.length === 8 ? `${digits.slice(0,2)}.${digits.slice(2,4)}.${digits.slice(4)}` : value
}

export function formatGermanDateInput(value: string, inputType = ''): string {
  const digits = value.replace(/\D/g, '').slice(0, 8)
  if (digits.length < 2) return digits
  const deleting = inputType.startsWith('delete')
  if (digits.length === 2) return deleting ? digits : `${digits}.`
  if (digits.length < 4) return `${digits.slice(0, 2)}.${digits.slice(2)}`
  if (digits.length === 4) return deleting ? `${digits.slice(0, 2)}.${digits.slice(2)}` : `${digits.slice(0, 2)}.${digits.slice(2)}.`
  return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`
}

export function validGermanDate(value: string): boolean {
  if (!value) return true
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(value)
  if (!match) return false
  const day = Number(match[1]), month = Number(match[2]), year = Number(match[3])
  const date = new Date(year, month - 1, day)
  return date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day
}

export function idempotencyKey(): string {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  const bytes = new Uint8Array(16)
  if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(bytes)
  else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256)
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
}
