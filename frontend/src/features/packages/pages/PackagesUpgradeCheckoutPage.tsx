import { useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import {
  useBillingOverview,
  useBillingUpgradePreview,
  useCompleteUpgradeMutation,
  type BillingCatalogEntry,
} from "../../billing/hooks/useBilling";
import { formatPlanResourceBlockMessage, planResourceBlock, readBillingResourceUsage } from "../planEligibility";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";

const VALID_PERIODS = ["monthly", "quarterly", "yearly"] as const;
type BillingPeriod = (typeof VALID_PERIODS)[number];

function isFreePlan(plan: BillingCatalogEntry): boolean {
  return plan.code === "free" || plan.price_cents === 0;
}

function localeTag(locale: string): string {
  if (locale === "es") return "es-ES";
  if (locale === "en") return "en-GB";
  return "hu-HU";
}

function formatEuroFromCents(cents: number, loc: string): string {
  const value = Number(cents) / 100;
  const tag = localeTag(loc);
  const whole = Math.round(value * 100) % 100 === 0;
  return value.toLocaleString(tag, whole ? { maximumFractionDigits: 0 } : { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function percentValue(part: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min((part / total) * 100, 100));
}

export default function PackagesUpgradeCheckoutPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading: overviewLoading } = useBillingOverview();
  const completeUpgradeMutation = useCompleteUpgradeMutation();

  const planCode = (searchParams.get("plan") ?? "").toLowerCase();
  const rawPeriod = (searchParams.get("period") ?? "quarterly").toLowerCase();
  const billingPeriod: BillingPeriod = VALID_PERIODS.includes(rawPeriod as BillingPeriod) ? (rawPeriod as BillingPeriod) : "quarterly";

  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");
  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [country, setCountry] = useState("");
  const [taxId, setTaxId] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);

  const catalog = billingOverview?.catalog ?? [];
  const plan = useMemo(
    () => catalog.find((e) => e.entry_type === "plan" && e.code === planCode && !isFreePlan(e)),
    [catalog, planCode]
  );

  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");

  const previewEnabled = Boolean(plan) && currentPlanCode !== "free";
  const {
    data: preview,
    isLoading: previewLoading,
    isError: previewError,
    error: previewErr,
  } = useBillingUpgradePreview(planCode, billingPeriod, { enabled: previewEnabled });

  const billedPhrase =
    billingPeriod === "monthly"
      ? t("packages.bannerBilledMonthly")
      : billingPeriod === "yearly"
        ? t("packages.bannerBilledYearly")
        : t("packages.bannerBilledQuarterly");

  const previewErrMsg = previewError ? getApiErrorMessage(previewErr) ?? t("common.errorGeneric") : null;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!plan || !acceptTerms || !preview || currentPlanCode === "free") return;
    const { usedGb, usedKbCount } = readBillingResourceUsage(billingOverview?.usage as Record<string, unknown> | undefined);
    const block = planResourceBlock(plan, usedGb, usedKbCount, false);
    if (block.blocked) return;
    try {
      const res = await completeUpgradeMutation.mutateAsync({ plan_code: plan.code, billing_period: billingPeriod });
      const amountLabel = formatEuroFromCents(res.prorated_charge_cents, locale);
      const message =
        res.prorated_charge_cents > 0
          ? t("packages.upgradeCheckoutSuccessPaid").replace("{{amount}}", amountLabel)
          : t("packages.upgradeCheckoutSuccessZero");
      navigate("/admin/csomagok", {
        state: { upgradeCheckoutComplete: true, message, status: res.status },
      });
    } catch {
      /* axios error surfaced via mutation */
    }
  };

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)]">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded max-w-lg mx-auto">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (overviewLoading) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  if (currentPlanCode === "free") {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.upgradeCheckoutOnlyFromPaid")}</p>
        <button
          type="button"
          className="rounded-lg px-4 py-2 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-medium"
          onClick={() => navigate("/admin/csomagok")}
        >
          {t("packages.checkoutBackToPackages")}
        </button>
      </div>
    );
  }

  if (!plan) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.checkoutInvalidPlan")}</p>
        <button
          type="button"
          className="rounded-lg px-4 py-2 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-medium"
          onClick={() => navigate("/admin/csomagok")}
        >
          {t("packages.checkoutBackToPackages")}
        </button>
      </div>
    );
  }

  const tag = localeTag(locale);
  const startIso = billingOverview?.current_period_start_iso ?? "";
  const endIso = billingOverview?.current_period_end_iso ?? "";
  const fromLabel = startIso ? new Date(startIso + "T12:00:00").toLocaleDateString(tag, { dateStyle: "long" }) : "—";
  const toLabel = endIso ? new Date(endIso + "T12:00:00").toLocaleDateString(tag, { dateStyle: "long" }) : "—";

  const { usedGb: checkoutUsedGb, usedKbCount: checkoutUsedKb } = readBillingResourceUsage(
    billingOverview?.usage as Record<string, unknown> | undefined
  );
  const checkoutResourceBlock = planResourceBlock(plan, checkoutUsedGb, checkoutUsedKb, false);

  const submitDisabled =
    !acceptTerms ||
    completeUpgradeMutation.isPending ||
    !fullName.trim() ||
    !cardNumber.trim() ||
    !cardExpiry.trim() ||
    !cardCvc.trim() ||
    checkoutResourceBlock.blocked ||
    previewLoading ||
    !preview ||
    Boolean(previewErrMsg);

  const prorationLine =
    preview != null
      ? t("packages.upgradeCheckoutProrationLine")
          .replace("{{remaining}}", String(preview.remaining_period_days))
          .replace("{{total}}", String(preview.total_period_days))
          .replace("{{amount}}", formatEuroFromCents(preview.prorated_charge_cents, locale))
      : null;
  const progressPercent = preview != null ? percentValue(preview.remaining_period_days, preview.total_period_days) : 0;
  const payNowLabel = preview != null ? `${formatEuroFromCents(preview.prorated_charge_cents, locale)} €` : "—";

  return (
    <div className="app-page">
      <div className="mx-auto max-w-3xl space-y-6">
        <PageHeader
          eyebrow={t("nav.packages")}
          title={t("packages.upgradeCheckoutTitle")}
          description={t("packages.upgradeCheckoutIntro")}
        />

        {checkoutResourceBlock.blocked ? (
          <Alert tone="warning" className="whitespace-pre-wrap leading-relaxed" role="alert">
            <p className="mb-2 font-semibold">{t("packages.planBlockedModalTitle")}</p>
            <p>{formatPlanResourceBlockMessage(checkoutResourceBlock, checkoutUsedGb, checkoutUsedKb, t)}</p>
          </Alert>
        ) : null}

        {previewErrMsg ? (
          <Alert tone="error" role="alert">{previewErrMsg}</Alert>
        ) : null}

        {previewLoading ? <div className="text-center text-sm text-[var(--color-muted)]">{t("common.loading")}</div> : null}

        <section className="app-surface p-6">
          <p className="text-sm font-medium text-[var(--color-muted)]">{t("packages.checkoutSummaryHeading")}</p>

          <div className="mt-4 space-y-4">
            <div className="flex justify-between gap-4">
              <span className="text-[var(--color-muted)]">{t("packages.checkoutChosenPlan")}</span>
              <span className="font-medium text-[var(--color-foreground)]">{plan.name}</span>
            </div>

            <div className="flex justify-between gap-4">
              <span className="text-[var(--color-muted)]">{t("packages.checkoutBillingCycle")}</span>
              <span className="font-medium text-[var(--color-foreground)]">{billedPhrase}</span>
            </div>

            <div className="flex justify-between gap-4">
              <span className="text-[var(--color-muted)]">{t("packages.checkoutPeriodLabel")}</span>
              <span className="text-right font-medium text-[var(--color-foreground)]">
                {fromLabel} - {toLabel}
              </span>
            </div>
          </div>

          <div className="mt-6">
            <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--color-card-muted)]">
              <div className="h-full bg-[var(--color-accent)]" style={{ width: `${progressPercent}%` }} />
            </div>
            <div className="mt-2 flex justify-between text-sm text-[var(--color-muted)]">
              <span>
                {preview != null ? `${preview.remaining_period_days} / ${preview.total_period_days} ${t("packages.upgradeCheckoutDaysRemaining")}` : "—"}
              </span>
              <span>{Math.round(progressPercent)}%</span>
            </div>
          </div>

          <div className="mt-6 rounded-2xl bg-[var(--color-card-strong)] p-5 text-[var(--color-on-primary)]">
            <p className="text-sm opacity-70">{t("packages.upgradeCheckoutPayNowLabel")}</p>
            <p className="mt-2 text-3xl font-semibold">{payNowLabel}</p>
            <p className="mt-2 text-sm opacity-70">{t("packages.upgradeCheckoutProrationShort")}</p>
            {prorationLine ? <p className="mt-3 text-sm opacity-70">{prorationLine}</p> : null}
          </div>
        </section>

        <form onSubmit={handleSubmit} className="app-surface p-6">
          <p className="text-sm font-medium text-[var(--color-muted)]">{t("packages.checkoutPaymentSection")}</p>

          <div className="mt-4 space-y-4">
            <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCardNumber")}</span>
              <input
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                  className="mt-1"
                autoComplete="cc-number"
                placeholder="4242 4242 4242 4242"
              />
            </label>

            <div className="grid grid-cols-2 gap-4">
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCardExpiry")}</span>
                <input
                  value={cardExpiry}
                  onChange={(e) => setCardExpiry(e.target.value)}
                  className="mt-1"
                  autoComplete="cc-exp"
                  placeholder="MM/YY"
                />
              </label>
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCardCvc")}</span>
                <input
                  value={cardCvc}
                  onChange={(e) => setCardCvc(e.target.value)}
                  className="mt-1"
                  autoComplete="cc-csc"
                  placeholder="CVC"
                />
              </label>
            </div>

            <div className="space-y-3 pt-2">
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutFullName")}</span>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="mt-1"
                  autoComplete="name"
                />
              </label>
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCompany")}</span>
                <input
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="mt-1"
                  autoComplete="organization"
                />
              </label>
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutAddress")}</span>
                <input
                  value={addressLine}
                  onChange={(e) => setAddressLine(e.target.value)}
                  className="mt-1"
                  autoComplete="street-address"
                />
              </label>
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutCountry")}</span>
                <input
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="mt-1"
                  autoComplete="country-name"
                />
              </label>
              <label className="block">
                <span className="text-sm text-[var(--color-muted)]">{t("packages.checkoutTaxId")}</span>
                <input
                  value={taxId}
                  onChange={(e) => setTaxId(e.target.value)}
                  className="mt-1"
                />
              </label>
            </div>

            <label className="app-surface-muted flex cursor-pointer items-start gap-2 p-4 text-sm text-[var(--color-muted)]">
              <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} className="mt-1" />
              <span>{t("packages.checkoutAcceptSimulated")}</span>
            </label>
          </div>

          {completeUpgradeMutation.isError ? (
            <Alert tone="error" className="mt-4">{getApiErrorMessage(completeUpgradeMutation.error) ?? t("common.errorGeneric")}</Alert>
          ) : null}

          <div className="mt-6 flex gap-3">
            <Button
              type="submit"
              disabled={submitDisabled}
              fullWidth
              size="lg"
            >
              {completeUpgradeMutation.isPending ? t("common.loading") : t("packages.upgradeCheckoutSubmit")}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="lg"
              onClick={() => navigate("/admin/csomagok")}
            >
              {t("common.cancel")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
