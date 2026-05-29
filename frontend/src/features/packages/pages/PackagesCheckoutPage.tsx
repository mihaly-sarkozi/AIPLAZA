import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview, useUpdateSubscriptionMutation, type BillingCatalogEntry } from "../../billing/hooks/useBilling";
import { formatPlanResourceBlockMessage, planResourceBlock, readBillingResourceUsage } from "../planEligibility";
import { patchBillingSettings } from "../../../api/services/settingsService";
import { EU_COUNTRIES, isValidEuVatId, isValidPostalCode, normalizeEuVatId, normalizePostalCode } from "./checkoutOptions";
import { checkoutCustomerTypeFromSettings, hasSavedCheckoutBillingDetails, type BillingCustomerType } from "./checkoutBillingDetails";
import { SavedBillingDetailsSummary } from "./SavedBillingDetailsSummary";
import { useBillingSettings, useLocaleSettings } from "../../settings/hooks/useSettings";
import { formatDateOnly } from "../../../utils/dateTimeFormatting";
import { trainingInitialFeeEuroForPlan } from "../components/packageUtils";

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
  const { data: settings } = useBillingSettings();
  const { data: localeSettings } = useLocaleSettings();
  const updateSubscriptionMutation = useUpdateSubscriptionMutation();

  const planCode = (searchParams.get("plan") ?? "").toLowerCase();
  const rawPeriod = (searchParams.get("period") ?? "quarterly").toLowerCase();
  const billingPeriod: BillingPeriod = VALID_PERIODS.includes(rawPeriod as BillingPeriod) ? (rawPeriod as BillingPeriod) : "quarterly";

  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");
  const [fullName, setFullName] = useState("");
  const [customerType, setCustomerType] = useState<BillingCustomerType>("company");
  const [company, setCompany] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [taxId, setTaxId] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [billingDetailsEditing, setBillingDetailsEditing] = useState(true);
  const [billingDetailsPrefilled, setBillingDetailsPrefilled] = useState(false);

  const catalog = useMemo(() => billingOverview?.catalog ?? [], [billingOverview?.catalog]);
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
    const trainingInitialFeeEuro = trainingInitialFeeEuroForPlan(plan.code, catalog);
    const dueNowEuro = (periodTotalEuro ?? monthEuro) + trainingInitialFeeEuro;
    return { monthEuro, periodTotalEuro, trainingInitialFeeEuro, dueNowEuro };
  }, [plan, billingPeriod, catalog]);

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
  const hasSavedBillingDetails = hasSavedCheckoutBillingDetails(settings);
  const billingDetailsLocked = hasSavedBillingDetails && !billingDetailsEditing;

  useEffect(() => {
    if (!settings || billingDetailsPrefilled) return;
    const savedCustomerType = checkoutCustomerTypeFromSettings(settings);
    setCustomerType(savedCustomerType);
    setCompany(savedCustomerType === "company" ? settings.billing_company_name ?? "" : "");
    setFullName(savedCustomerType === "private" ? settings.billing_full_name ?? "" : user?.name ?? "");
    setAddressLine(settings.billing_address_line ?? "");
    setPostalCode(normalizePostalCode(settings.billing_postal_code ?? ""));
    setCity(settings.billing_city ?? "");
    setCountry(settings.billing_country ?? "");
    setTaxId(normalizeEuVatId(settings.billing_tax_id ?? ""));
    setBillingDetailsEditing(!hasSavedCheckoutBillingDetails(settings));
    setBillingDetailsPrefilled(true);
  }, [billingDetailsPrefilled, settings, user?.name]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!plan || !acceptTerms || currentPlanCode !== "free") return;
    if (!isValidPostalCode(postalCode) || (customerType === "company" && !isValidEuVatId(country, taxId))) return;
    const { usedGb, usedKbCount } = readBillingResourceUsage(billingOverview?.usage as Record<string, unknown> | undefined);
    const block = planResourceBlock(plan, usedGb, usedKbCount, false);
    if (block.blocked) return;
    try {
      await patchBillingSettings({
        billing_customer_type: customerType,
        billing_full_name: fullName,
        billing_company_name: customerType === "company" ? company : "",
        billing_tax_id: customerType === "company" ? normalizeEuVatId(taxId) : "",
        billing_address_line: addressLine,
        billing_postal_code: postalCode,
        billing_city: city,
        billing_country: country,
      });
      const res = await updateSubscriptionMutation.mutateAsync({ plan_code: plan.code, billing_period: billingPeriod });
      navigate("/admin/pricing", { state: { checkoutComplete: true, message: res.message, status: res.status } });
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
          onClick={() => navigate("/admin/pricing")}
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
          onClick={() => navigate("/admin/pricing")}
        >
          {t("packages.checkoutBackToPackages")}
        </button>
      </div>
    );
  }

  const startIso = billingOverview?.current_period_start_iso ?? "";
  const endIso = billingOverview?.current_period_end_iso ?? "";
  const fromLabel = startIso
    ? formatDateOnly(startIso, {
        locale,
        timezone: localeSettings?.timezone,
        dateFormat: localeSettings?.date_format,
        dateStyle: localeSettings?.date_format ? undefined : "long",
      })
    : "—";
  const toLabel = endIso
    ? formatDateOnly(endIso, {
        locale,
        timezone: localeSettings?.timezone,
        dateFormat: localeSettings?.date_format,
        dateStyle: localeSettings?.date_format ? undefined : "long",
      })
    : "—";

  const { usedGb: checkoutUsedGb, usedKbCount: checkoutUsedKb } = readBillingResourceUsage(
    billingOverview?.usage as Record<string, unknown> | undefined
  );
  const checkoutResourceBlock = planResourceBlock(plan, checkoutUsedGb, checkoutUsedKb, false);

  const submitDisabled =
    !acceptTerms ||
    updateSubscriptionMutation.isPending ||
    (!billingDetailsLocked &&
      (!fullName.trim() ||
        !country.trim() ||
        !isValidPostalCode(postalCode) ||
        !city.trim() ||
        !addressLine.trim() ||
        (customerType === "company" && (!company.trim() || !isValidEuVatId(country, taxId))))) ||
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
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutTrainingInitialFee")}</span>{" "}
            <span className="font-medium tabular-nums">{summary.trainingInitialFeeEuro} €</span>
          </p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.checkoutDueNowTotal")}</span>{" "}
            <span className="font-semibold tabular-nums">{summary.dueNowEuro} €</span>
          </p>
          <p className="text-[var(--color-muted)] text-xs leading-relaxed pt-1">
            {t("packages.checkoutPeriodWindow")
              .replace("{{from}}", fromLabel)
              .replace("{{to}}", toLabel)}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <h2 className="text-sm font-semibold">{t("packages.checkoutBillingSection")}</h2>
          {billingDetailsLocked && settings ? (
            <SavedBillingDetailsSummary settings={settings} onEdit={() => setBillingDetailsEditing(true)} />
          ) : (
          <div className="space-y-3">
            <fieldset className="rounded-xl border border-[var(--color-border)] p-3">
              <legend className="px-1 text-xs font-medium text-[var(--color-muted)]">{t("packages.checkoutCustomerType")}</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="billing_customer_type"
                    checked={customerType === "company"}
                    onChange={() => setCustomerType("company")}
                    className="mr-1 shrink-0"
                    style={{ width: "auto" }}
                  />
                  <span className="relative -top-[3px]">{t("packages.checkoutCustomerTypeCompany")}</span>
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="billing_customer_type"
                    checked={customerType === "private"}
                    onChange={() => setCustomerType("private")}
                    className="mr-1 shrink-0"
                    style={{ width: "auto" }}
                  />
                  <span className="relative -top-[3px]">{t("packages.checkoutCustomerTypePrivate")}</span>
                </label>
              </div>
            </fieldset>
            <label className="block text-xs text-[var(--color-muted)]">
              {customerType === "company" ? t("packages.checkoutRepresentativeName") : t("packages.checkoutFullName")}
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="name"
              />
            </label>
            {customerType === "company" ? (
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCompanyRequired")}
                <input
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="organization"
                />
              </label>
            ) : null}
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutCountry")}
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="country-name"
              >
                <option value="">{t("packages.checkoutCountrySelectPlaceholder")}</option>
                {EU_COUNTRIES.map((item) => (
                  <option key={item.code} value={item.code} disabled={item.disabled}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutPostalCode")}
                <input
                  value={postalCode}
                  onChange={(e) => setPostalCode(normalizePostalCode(e.target.value))}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="postal-code"
                  inputMode="numeric"
                  maxLength={5}
                />
                <span className="mt-1 block text-[11px] text-[var(--color-muted)]">{t("packages.checkoutPostalCodeHint")}</span>
              </label>
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCity")}
                <input
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="address-level2"
                />
              </label>
            </div>
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutLocality")}
              <input
                value={addressLine}
                onChange={(e) => setAddressLine(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="street-address"
              />
            </label>
            {customerType === "company" ? (
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutTaxIdRequired")}
                <input
                  value={taxId}
                  onChange={(e) => setTaxId(normalizeEuVatId(e.target.value))}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                />
                <span className="mt-1 block text-[11px] text-[var(--color-muted)]">{t("packages.checkoutTaxIdFormatHint")}</span>
              </label>
            ) : null}
          </div>
          )}

          <h2 className="text-sm font-semibold pt-2">{t("packages.checkoutPaymentSection")}</h2>
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

          <label className="flex items-start gap-3 text-sm pt-2 cursor-pointer text-left">
            <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} className="mt-1 shrink-0" style={{ width: "auto" }} />
            <span className="relative top-px ml-[3px]">{t("packages.checkoutAcceptSimulated")}</span>
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
              onClick={() => navigate("/admin/pricing")}
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
