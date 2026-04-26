import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview } from "../hooks/useBilling";
import {
  downloadInvoiceSummary,
  formatInvoiceDate,
  formatInvoicePeriodRange,
  invoiceIsDownloadable,
  localeTag,
  moneyFromCents,
} from "../billingInvoiceUtils";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";

function numberValue(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export default function BillingInvoicesPage() {
  const { t, locale } = useTranslation();
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const { data: billingOverview, isLoading, error: billingError } = useBillingOverview();

  const billingErrMsg =
    billingError && typeof (billingError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (billingError as { response?: { data?: { detail?: string } } }).response!.data!.detail
      : billingError
        ? t("common.errorGeneric")
        : null;

  const invoicesSorted = useMemo(() => {
    const raw = billingOverview?.invoices ?? [];
    const copy = [...raw];
    copy.sort((a, b) => {
      const ta = new Date(String((a as { issued_at?: unknown }).issued_at ?? 0)).getTime();
      const tb = new Date(String((b as { issued_at?: unknown }).issued_at ?? 0)).getTime();
      return (Number.isNaN(tb) ? 0 : tb) - (Number.isNaN(ta) ? 0 : ta);
    });
    return copy;
  }, [billingOverview?.invoices]);

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)] flex justify-center">
        <div className="w-full max-w-2xl bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] flex justify-center">
        <div className="max-w-2xl text-center">{t("common.loading")}</div>
      </div>
    );
  }

  const estimated = billingOverview?.estimated_next_invoice ?? {};
  const periodMultiplier = Math.max(1, Number(estimated.period_multiplier ?? 1) || 1);
  const basePlanCents = Number(estimated.base_plan_cents ?? 0) || 0;
  const recurringAddonsCents = Number(estimated.recurring_addons_cents ?? 0) || 0;
  const discountPercent = Math.max(0, Number(estimated.discount_percent ?? 0) || 0);
  const basePlanMonthlyCents = periodMultiplier > 0 ? Math.round(basePlanCents / periodMultiplier) : basePlanCents;
  const recurringAddonsMonthlyCents =
    periodMultiplier > 0 ? Math.round(recurringAddonsCents / periodMultiplier) : recurringAddonsCents;
  const amountLocale = localeTag(locale);
  const formatCyclePart = (cents: number) =>
    `${periodMultiplier} x ${(cents / 100).toLocaleString(amountLocale, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    })} €`;
  const monthlyBreakdown = formatCyclePart(basePlanMonthlyCents);
  const recurringBreakdown = formatCyclePart(recurringAddonsMonthlyCents);
  const totalLabel =
    discountPercent > 0
      ? `${t("billing.totalEstimated")} (${t("billing.discountPercent")} ${discountPercent}%)`
      : t("billing.totalEstimated");
  const dueAtLabel = estimated.due_at_iso ? formatInvoiceDate(estimated.due_at_iso, locale) : "—";
  const subscription = (billingOverview?.subscription as Record<string, unknown>) ?? {};
  const subscriptionStatus = String(subscription.status ?? "active").toLowerCase();
  const isHealthyStatus = subscriptionStatus === "active" || subscriptionStatus === "trial";
  const statusTitle =
    subscriptionStatus === "trial"
      ? t("billing.statusTrialTitle")
      : isHealthyStatus
        ? t("billing.statusScheduledTitle")
        : t("billing.statusRestrictedTitle");
  const statusSummary =
    subscriptionStatus === "trial"
      ? t("billing.statusTrialSummary")
      : isHealthyStatus
        ? t("billing.statusHealthySummary")
        : t("billing.statusRestrictedSummary");
  const statusAsideClass = isHealthyStatus
    ? "rounded-3xl border border-[var(--color-success-border)] bg-[var(--color-success-bg)] p-6 text-[var(--color-success-text)] shadow-sm"
    : "rounded-3xl border border-[var(--color-danger-border)] bg-[var(--color-danger-bg)] p-6 text-[var(--color-danger-text)] shadow-sm";
  const statusMutedClass = isHealthyStatus ? "text-[var(--color-success-text)]" : "text-[var(--color-danger-text)]";
  const statusPanelClass = isHealthyStatus
    ? "rounded-2xl border border-[var(--color-success-border)] bg-[var(--color-card)]/70 p-4"
    : "rounded-2xl border border-[var(--color-danger-border)] bg-[var(--color-card)]/70 p-4";
  const totalDisplay = `${numberValue(estimated.total).toFixed(2)} €`;

  return (
    <div className="app-page">
      <div className="app-page-container">
        <PageHeader
          eyebrow={t("billing.overviewLabel")}
          title={t("billing.pageTitle")}
          description={t("billing.pageIntro")}
          actions={
            <>
              <Button variant="secondary" onClick={() => navigate("/admin/megrendeles")}>
                {t("nav.orders")}
              </Button>
              <Button onClick={() => navigate("/admin/csomagok")}>{t("nav.packages")}</Button>
            </>
          }
        />

        {billingErrMsg ? (
          <Alert tone="error">{billingErrMsg}</Alert>
        ) : null}

        <section className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
          <div className="app-surface p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-[var(--color-muted)]">{t("billing.nextEstimateTitle")}</p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--color-foreground)]">{totalDisplay}</h2>
                <p className="mt-2 text-sm text-[var(--color-muted)]">
                  {t("billing.invoiceDueLabel")}: <span className="font-medium text-[var(--color-foreground)]">{dueAtLabel}</span>
                </p>
              </div>

              <div className="rounded-2xl bg-[var(--color-accent-soft)] px-3 py-2 text-right">
                <p className="text-xs font-medium uppercase tracking-wide text-[var(--color-accent-foreground)]">{t("billing.highlightInvoiceLabel")}</p>
                <p className="mt-1 text-sm text-[var(--color-foreground)]">{t("billing.highlightInvoiceDescription")}</p>
              </div>
            </div>

            <div className="app-surface-muted mt-6 space-y-4 p-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-[var(--color-foreground)]">
                    {t("billing.linePlan")} <span className="text-[var(--color-muted)]">({monthlyBreakdown})</span>
                  </p>
                  <p className="text-sm text-[var(--color-muted)]">{t("billing.linePlanHint")}</p>
                </div>
                <p className="text-lg font-semibold text-[var(--color-foreground)]">{moneyFromCents(estimated.base_plan_cents)} €</p>
              </div>

              <div className="flex items-center justify-between gap-4 border-t border-[var(--color-border)] pt-4">
                <div>
                  <p className="text-sm font-medium text-[var(--color-foreground)]">
                    {t("billing.lineRecurringAddons")} <span className="text-[var(--color-muted)]">({recurringBreakdown})</span>
                  </p>
                  <p className="text-sm text-[var(--color-muted)]">{t("billing.lineRecurringAddonsHint")}</p>
                </div>
                <p className="text-lg font-semibold text-[var(--color-foreground)]">{moneyFromCents(estimated.recurring_addons_cents)} €</p>
              </div>

              <div className="flex items-center justify-between gap-4 border-t border-[var(--color-border)] pt-4">
                <div>
                  <p className="text-sm font-medium text-[var(--color-foreground)]">{totalLabel}</p>
                  <p className="text-sm text-[var(--color-success-text)]">
                    {discountPercent > 0 ? t("billing.discountApplied") : t("billing.noDiscountApplied")}
                  </p>
                </div>
                <p className="text-2xl font-semibold text-[var(--color-foreground)]">{totalDisplay}</p>
              </div>
            </div>
          </div>

          <aside className={statusAsideClass}>
            <p className={`text-sm font-medium ${statusMutedClass}`}>{t("billing.statusLabel")}</p>
            <h3 className="mt-2 text-2xl font-semibold tracking-tight">{statusTitle}</h3>

            <div className="mt-6">
              <div className={statusPanelClass}>
              <p className={`text-sm ${statusMutedClass}`}>{t("billing.paymentSummaryLabel")}</p>
              <p className="mt-1 font-medium">{statusSummary}</p>
              </div>
            </div>

            <div className={`mt-4 ${statusPanelClass}`}>
              <p className={`text-sm ${statusMutedClass}`}>{t("billing.exampleStatusLabel")}</p>
              <p className="mt-1 text-sm leading-6">
                {isHealthyStatus ? t("billing.exampleStatusHealthy") : t("billing.exampleStatusRestricted")}
              </p>
            </div>

            <Button
              type="button"
              onClick={() => navigate(isHealthyStatus ? "/admin/csomagok" : "/admin/megrendeles")}
              variant={isHealthyStatus ? "primary" : "danger"}
              fullWidth
              size="lg"
              className="mt-6"
            >
              {isHealthyStatus ? t("billing.managePaymentCta") : t("billing.restrictedCta")}
            </Button>
          </aside>
        </section>

        <section className="app-surface p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-[var(--color-muted)]">{t("billing.historyTitle")}</p>
              <h2 className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">{t("billing.historySubtitle")}</h2>
            </div>
            <div className="badge-soft">
              {t("billing.historyBadge")}
            </div>
          </div>

          <div className="app-table-wrap mt-6">
            {invoicesSorted.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-[var(--color-muted)]">{t("billing.noInvoices")}</p>
            ) : (
              <>
                <div className="app-table-head hidden grid-cols-[1.5fr_1.2fr_0.7fr_0.9fr] gap-4 px-5 py-3 text-sm font-medium md:grid">
                  <div>{t("billing.colPeriod")}</div>
                  <div>{t("billing.colDescription")}</div>
                  <div>{t("billing.colAmount")}</div>
                  <div>{t("billing.colDownload")}</div>
                </div>

                <div className="divide-y divide-[var(--color-border)]">
                  {invoicesSorted.map((invoice, index) => {
                    const inv = invoice as Record<string, unknown>;
                    const periodLabel = formatInvoicePeriodRange(inv, locale);
                    const canDownload = invoiceIsDownloadable(inv);
                    return (
                      <div
                        key={`${String(invoice.period_key)}-${index}`}
                        className="grid gap-3 px-5 py-4 md:grid-cols-[1.5fr_1.2fr_0.7fr_0.9fr] md:items-center"
                      >
                        <div>
                          <p className="font-medium text-[var(--color-foreground)]">{periodLabel}</p>
                          <p className="mt-1 text-sm text-[var(--color-muted)]">
                            {t("billing.issuedLabel")} {formatInvoiceDate(invoice.issued_at, locale)}
                          </p>
                        </div>
                        <div className="text-[var(--color-muted-foreground)]">{String(invoice.description ?? "—")}</div>
                        <div className="font-medium text-[var(--color-foreground)]">{Number(invoice.total ?? 0).toFixed(2)} €</div>
                        <div>
                          {canDownload ? (
                            <Button
                              type="button"
                              onClick={() => downloadInvoiceSummary(inv, periodLabel)}
                              variant="secondary"
                            >
                              {t("billing.download")}
                            </Button>
                          ) : (
                            <span className="text-sm text-[var(--color-muted)]">{t("billing.noDownloadFree")}</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </section>

      </div>
    </div>
  );
}
