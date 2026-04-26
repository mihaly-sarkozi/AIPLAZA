export function moneyFromCents(cents: unknown): string {
  const n = Number(cents ?? 0);
  if (Number.isNaN(n)) return "0.00";
  return (n / 100).toFixed(2);
}

export function localeTag(locale: string): string {
  if (locale === "es") return "es-ES";
  if (locale === "en") return "en-GB";
  return "hu-HU";
}

export function formatInvoiceDate(iso: unknown, locale: string): string {
  if (iso == null || iso === "") return "—";
  const d = new Date(String(iso));
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString(localeTag(locale), {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Számlázási időszak: YYYY-MM → hónap első–utolsó napja; egyébként kiadás–esedék. */
export function formatInvoicePeriodRange(invoice: Record<string, unknown>, locale: string): string {
  const pk = String(invoice.period_key ?? "").trim();
  const ym = /^(\d{4})-(\d{2})$/.exec(pk);
  const tag = localeTag(locale);
  const df = new Intl.DateTimeFormat(tag, { year: "numeric", month: "short", day: "numeric" });
  if (ym) {
    const y = Number(ym[1]);
    const mo = Number(ym[2]);
    const start = new Date(y, mo - 1, 1);
    const end = new Date(y, mo, 0);
    return `${df.format(start)} – ${df.format(end)}`;
  }
  const issued = invoice.issued_at;
  const due = invoice.due_at;
  if (issued && due) {
    const a = new Date(String(issued));
    const b = new Date(String(due));
    if (!Number.isNaN(a.getTime()) && !Number.isNaN(b.getTime())) {
      return `${df.format(a)} – ${df.format(b)}`;
    }
  }
  if (issued) return formatInvoiceDate(issued, locale);
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
