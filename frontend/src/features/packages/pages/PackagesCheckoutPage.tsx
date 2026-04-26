import { useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview, useUpdateSubscriptionMutation, type BillingCatalogEntry } from "../../billing/hooks/useBilling";
import { formatPlanResourceBlockMessage, planResourceBlock, readBillingResourceUsage } from "../planEligibility";

const VALID_PERIODS = ["monthly", "quarterly", "yearly"] as const;
type BillingPeriod = (typeof VALID_PERIODS)[number];

function isFreePlan(plan: BillingCatalogEntry): boolean {
  return plan.code === "free" || plan.price_cents === 0;
}

function billingDiscountPercent(period: string): number {
  const p = (period || "monthly").toLowerCase();
  if (p === "quarterly") return 7;
  if (p === "yearly") return 15;
  return 0;
}

function discountedMonthlyCents(priceCents: number, period: string): number {
  const d = billingDiscountPercent(period);
  if (d <= 0) return priceCents;
  return Math.round((Number(priceCents) * (100 - d)) / 100);
}

function flooredMonthlyEuroAfterDiscount(priceCents: number, selectedPeriod: string): number {
  const monthlyDiscCents = discountedMonthlyCents(priceCents, selectedPeriod);
  return Math.floor(Number(monthlyDiscCents) / 100);
}

export default function PackagesCheckoutPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading } = useBillingOverview();
  const updateSubscriptionMutation = useUpdateSubscriptionMutation();

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

  const summary = useMemo(() => {
    if (!plan) return null;
    const listM = Math.floor(Number(plan.price_cents) / 100);
    const effM = flooredMonthlyEuroAfterDiscount(plan.price_cents, billingPeriod);
    const monthEuro = billingPeriod === "monthly" ? listM : effM;
    let periodTotalEuro: number | null = null;
    if (billingPeriod === "quarterly") periodTotalEuro = effM * 3;
    if (billingPeriod === "yearly") periodTotalEuro = effM * 12;
    return { monthEuro, periodTotalEuro };
  }, [plan, billingPeriod]);

  const billedPhrase =
    billingPeriod === "monthly"
      ? t("packages.bannerBilledMonthly")
      : billingPeriod === "yearly"
        ? t("packages.bannerBilledYearly")
        : t("packages.bannerBilledQuarterly");

  const checkoutTotalPeriodAdverb =
    billingPeriod === "quarterly"
      ? t("packages.checkoutTotalAdverbQuarterly")
      : billingPeriod === "yearly"
        ? t("packages.checkoutTotalAdverbYearly")
        : "";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!plan || !acceptTerms || currentPlanCode !== "free") return;
    const { usedGb, usedKbCount } = readBillingResourceUsage(billingOverview?.usage as Record<string, unknown> | undefined);
    const block = planResourceBlock(plan, usedGb, usedKbCount, false);
    if (block.blocked) return;
    try {
      const res = await updateSubscriptionMutation.mutateAsync({ plan_code: plan.code, billing_period: billingPeriod });
      navigate("/admin/csomagok", { state: { checkoutComplete: true, message: res.message, status: res.status } });
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

  if (isLoading) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  if (currentPlanCode !== "free") {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.checkoutOnlyFromFree")}</p>
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

  if (!plan || !summary) {
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

  const tag = locale === "es" ? "es-ES" : locale === "en" ? "en-GB" : "hu-HU";
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
    updateSubscriptionMutation.isPending ||
    !fullName.trim() ||
    !cardNumber.trim() ||
    !cardExpiry.trim() ||
    !cardCvc.trim() ||
    checkoutResourceBlock.blocked;

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="max-w-xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-center">{t("packages.checkoutTitle")}</h1>

        {checkoutResourceBlock.blocked ? (
          <div
            className="rounded-xl border border-amber-600/40 bg-amber-500/10 p-4 text-sm text-[var(--color-foreground)] leading-relaxed whitespace-pre-wrap"
            role="alert"
          >
            <p className="font-semibold text-amber-950 dark:text-amber-100 mb-2">{t("packages.planBlockedModalTitle")}</p>
            <p>{formatPlanResourceBlockMessage(checkoutResourceBlock, checkoutUsedGb, checkoutUsedKb, t)}</p>
          </div>
        ) : null}

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-sm space-y-2">
          <p className="font-medium">{t("packages.checkoutSummaryHeading")}</p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutChosenPlan")}</span>{" "}
            <span className="font-medium">{plan.name}</span>
          </p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutBillingCycle")}</span>{" "}
            <span className="font-medium">{billedPhrase}</span>
          </p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutAmountHint")}</span>{" "}
            <span className="font-medium tabular-nums">
              {summary.monthEuro} € / {t("packages.perMonthSuffix")}
              {summary.periodTotalEuro != null && checkoutTotalPeriodAdverb
                ? ` · ${summary.periodTotalEuro} € / ${checkoutTotalPeriodAdverb}`
                : ""}
            </span>
          </p>
          <p className="text-[var(--color-muted)] text-xs leading-relaxed pt-1">
            {t("packages.checkoutPeriodWindow")
              .replace("{{from}}", fromLabel)
              .replace("{{to}}", toLabel)}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <h2 className="text-sm font-semibold">{t("packages.checkoutPaymentSection")}</h2>
          <div className="space-y-3">
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutCardNumber")}
              <input
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="cc-number"
                placeholder="4242 4242 4242 4242"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCardExpiry")}
                <input
                  value={cardExpiry}
                  onChange={(e) => setCardExpiry(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="cc-exp"
                  placeholder="MM/YY"
                />
              </label>
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCardCvc")}
                <input
                  value={cardCvc}
                  onChange={(e) => setCardCvc(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="cc-csc"
                  placeholder="CVC"
                />
              </label>
            </div>
          </div>

          <h2 className="text-sm font-semibold pt-2">{t("packages.checkoutBillingSection")}</h2>
          <div className="space-y-3">
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutFullName")}
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="name"
              />
            </label>
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutCompany")}
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="organization"
              />
            </label>
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutAddress")}
              <input
                value={addressLine}
                onChange={(e) => setAddressLine(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="street-address"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCountry")}
                <input
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="country-name"
                />
              </label>
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutTaxId")}
                <input
                  value={taxId}
                  onChange={(e) => setTaxId(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                />
              </label>
            </div>
          </div>

          <label className="flex gap-2 items-start text-sm pt-2 cursor-pointer">
            <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} className="mt-1" />
            <span>{t("packages.checkoutAcceptSimulated")}</span>
          </label>

          {updateSubscriptionMutation.isError ? (
            <p className="text-sm text-red-600 dark:text-red-400">{t("common.errorGeneric")}</p>
          ) : null}

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="submit"
              disabled={submitDisabled}
              className="rounded-lg px-4 py-2.5 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-semibold disabled:opacity-50"
            >
              {updateSubscriptionMutation.isPending ? t("common.loading") : t("packages.checkoutSubmit")}
            </button>
            <button
              type="button"
              className="rounded-lg px-4 py-2.5 border border-[var(--color-border)] text-sm"
              onClick={() => navigate("/admin/csomagok")}
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
