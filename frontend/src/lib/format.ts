export const inr = (v: string | number | null | undefined, dp = 2) =>
  v === null || v === undefined || v === ""
    ? "—"
    : new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: dp,
      }).format(Number(v));

export const num = (v: string | number | null | undefined, dp = 2) =>
  v === null || v === undefined || v === ""
    ? "—"
    : new Intl.NumberFormat("en-IN", { maximumFractionDigits: dp }).format(Number(v));

export const pct = (v: string | number | null | undefined, dp = 2) =>
  v === null || v === undefined || v === "" ? "—" : `${Number(v) >= 0 ? "+" : ""}${num(v, dp)}%`;

export const signClass = (v: string | number | null | undefined) =>
  v === null || v === undefined || v === "" || Number(v) === 0
    ? "text-muted"
    : Number(v) > 0
      ? "text-up"
      : "text-down";
