const IST = "Asia/Kolkata"

export function formatDateTime(value?: string | null): string {
  if (!value) return "—"
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleString("en-IN", { timeZone: IST, day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
}

export function formatDate(value?: string | null): string {
  if (!value) return "—"
  const d = new Date(value.length === 10 ? `${value}T00:00:00Z` : value)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleDateString("en-IN", { timeZone: value.length === 10 ? "UTC" : IST, day: "2-digit", month: "short", year: "numeric" })
}

export function timeAgo(value?: string | null): string {
  if (!value) return "—"
  const diff = (Date.now() - new Date(value).getTime()) / 1000
  if (diff < 0) return "just now"
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} d ago`
  return formatDate(value)
}

export function formatDuration(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return "—"
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`
  if (seconds < 60) return `${seconds.toFixed(1)} s`
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)} h`
  return `${(seconds / 86400).toFixed(1)} days`
}

export function humanize(value?: string | null): string {
  if (!value) return "—"
  return value
    .toLowerCase()
    .split("_")
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(" ")
}

export function ageFrom(dob?: string | null): number | null {
  if (!dob) return null
  const d = new Date(dob)
  const now = new Date()
  let age = now.getFullYear() - d.getFullYear()
  if (now.getMonth() < d.getMonth() || (now.getMonth() === d.getMonth() && now.getDate() < d.getDate())) age--
  return age
}

export const CATEGORY_INFO: Record<string, { label: string; description: string; source: string }> = {
  IDENTITY: { label: "Identity Information", description: "Name, date of birth, gender, contact and address", source: "Identity Service" },
  EDUCATION: { label: "Education Information", description: "Highest qualification, institution and passing year", source: "Education Registry" },
  EMPLOYMENT: { label: "Employment Information", description: "Job-seeker registration and current employment status", source: "Employment Registry" },
}
