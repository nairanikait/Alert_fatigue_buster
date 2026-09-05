/**
 * Safely parses an ISO date string from the backend into a local Date object.
 * If the backend sends UTC timestamps without timezone indicators ('Z' or offset),
 * this helper guarantees it is parsed as UTC so it correctly converts to the user's local timezone.
 */
export function parseUtcDate(dateStr?: string | null): Date {
  if (!dateStr) return new Date();
  const s = String(dateStr).trim();
  // If already contains timezone indicator ('Z' or '+' or offset), parse directly
  if (s.endsWith("Z") || s.includes("+") || (s.includes("-") && s.lastIndexOf("-") > 10)) {
    return new Date(s);
  }
  // Naive ISO string (e.g. "2026-09-04T21:38:00") represents UTC in Alert Buster backend
  return new Date(`${s}Z`);
}

/**
 * Formats date into localized time (e.g. "03:08 AM" or "03:08:15 AM")
 */
export function formatTime(dateStr?: string | null, includeSeconds = false): string {
  if (!dateStr) return "N/A";
  try {
    const d = parseUtcDate(dateStr);
    if (isNaN(d.getTime())) return String(dateStr);
    return d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      ...(includeSeconds ? { second: "2-digit" } : {})
    });
  } catch {
    return String(dateStr);
  }
}

/**
 * Formats date into localized full date and time string
 */
export function formatDateTime(dateStr?: string | null): string {
  if (!dateStr) return "N/A";
  try {
    const d = parseUtcDate(dateStr);
    if (isNaN(d.getTime())) return String(dateStr);
    return d.toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  } catch {
    return String(dateStr);
  }
}
