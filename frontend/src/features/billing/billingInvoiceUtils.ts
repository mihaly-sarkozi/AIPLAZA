import type { SettingsDateFormat, SettingsTimezone } from "../../api/services/settingsService";
import { formatDateOnly, localeTag } from "../../utils/dateTimeFormatting";

export function moneyFromCents(cents: unknown): string {
  const n = Number(cents ?? 0);
  if (Number.isNaN(n)) return "0.00";
  return (n / 100).toFixed(2);
}

export { localeTag };

export function formatInvoiceDate(
  iso: unknown,
  locale: string,
  timezone?: SettingsTimezone | string,
  dateFormat?: SettingsDateFormat
): string {
  if (iso == null || iso === "") return "—";
  return formatDateOnly(iso, { locale, timezone, dateFormat });
}

/** Számlázási időszak: YYYY-MM → hónap első–utolsó napja; egyébként kiadás–esedék. */
export function formatInvoicePeriodRange(
  invoice: Record<string, unknown>,
  locale: string,
  timezone?: SettingsTimezone | string,
  dateFormat?: SettingsDateFormat
): string {
  const pk = String(invoice.period_key ?? "").trim();
  const ym = /^(\d{4})-(\d{2})$/.exec(pk);
  if (ym) {
    const y = Number(ym[1]);
    const mo = Number(ym[2]);
    const start = `${String(y).padStart(4, "0")}-${String(mo).padStart(2, "0")}-01`;
    const end = new Date(Date.UTC(y, mo, 0)).toISOString().slice(0, 10);
    return `${formatInvoiceDate(start, locale, timezone, dateFormat)} – ${formatInvoiceDate(end, locale, timezone, dateFormat)}`;
  }
  const issued = invoice.issued_at;
  const due = invoice.due_at;
  if (issued && due) {
    const a = new Date(String(issued));
    const b = new Date(String(due));
    if (!Number.isNaN(a.getTime()) && !Number.isNaN(b.getTime())) {
      return `${formatInvoiceDate(a.toISOString(), locale, timezone, dateFormat)} – ${formatInvoiceDate(b.toISOString(), locale, timezone, dateFormat)}`;
    }
  }
  if (issued) return formatInvoiceDate(issued, locale, timezone, dateFormat);
  return pk || "—";
}

export function invoiceTotalCents(inv: Record<string, unknown>): number {
  const c = inv.total_cents;
  if (c != null && c !== "") {
    const n = Number(c);
    if (!Number.isNaN(n)) return n;
  }
  return Math.round(Number(inv.total ?? 0) * 100);
}

export function invoiceIsDownloadable(inv: Record<string, unknown>): boolean {
  return invoiceTotalCents(inv) > 0;
}

export function downloadInvoiceSummary(invoice: Record<string, unknown>, periodLabel: string) {
  const lines = [
    "BrainBankCenter — számla / invoice summary",
    `period_range: ${periodLabel}`,
    `issued_at: ${invoice.issued_at ?? ""}`,
    `description: ${invoice.description ?? ""}`,
    `type: ${invoice.invoice_type ?? ""}`,
    `period_key: ${invoice.period_key ?? ""}`,
    `status: ${invoice.status ?? ""}`,
    `currency: ${invoice.currency ?? "EUR"}`,
    `total: ${Number(invoice.total ?? 0).toFixed(2)}`,
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const safeKey = String(invoice.period_key ?? "invoice").replace(/[^\w.-]+/g, "_");
  a.download = `szamla-${safeKey}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}
