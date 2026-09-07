import { formatInTimeZone, getTimezoneOffset } from "date-fns-tz";
import type { Time } from "lightweight-charts";

export const IST = "Asia/Kolkata";

/**
 * Convert an ISO timestamp to the `time` value lightweight-charts expects, in IST.
 * - daily/weekly/monthly: a "yyyy-MM-dd" business day (its IST calendar date)
 * - intraday: a UNIX timestamp offset by the real IST offset, so the axis and
 *   crosshair render IST wall-clock (the library renders "in UTC")
 * Uses date-fns-tz so it's correct for any zone / DST, not a hard-coded number.
 */
export function chartTime(iso: string, daily: boolean): Time {
  const ms = Date.parse(iso);
  if (daily) {
    return formatInTimeZone(new Date(ms), IST, "yyyy-MM-dd") as unknown as Time;
  }
  const offsetMs = getTimezoneOffset(IST, new Date(ms));
  return (Math.floor((ms + offsetMs) / 1000) as number) as unknown as Time;
}

/** Format an ISO timestamp in IST, e.g. "07 Sep, 15:04". */
export const fmtIST = (iso: string, pattern = "dd MMM, HH:mm") =>
  formatInTimeZone(new Date(iso), IST, pattern);
