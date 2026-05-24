import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview, useUpdateSubscriptionMutation } from "../../billing/hooks/useBilling";
import {
  formatPlanResourceBlockMessage,
  planResourceBlock,
  readBillingResourceUsage,
} from "../planEligibility";
import { useAuthenticatorStatus } from "../../settings/hooks/useAuthenticator";
import Alert from "../../../components/ui/Alert";
import PageHeader from "../../../components/ui/PageHeader";
import PackageCurrentPlanBanner from "../components/PackageCurrentPlanBanner";
import PackageExpandBanner from "../components/PackageExpandBanner";
import PackageExpansionModal from "../components/PackageExpansionModal";
import PackagePlanCard from "../components/PackagePlanCard";
import PackageStatusModals from "../components/PackageStatusModals";
import {
  FLEX_STORAGE_GB_BUNDLE,
  addonEntry,
  formatSubscriptionDateForBanner,
  getStoragePerGbCents,
  getTrainingInitialAddonInfo,
  includedNumber,
  isFreePlan,
  isScheduledChange,
  localeTagForNumbers,
  sortPlans,
  tBannerBilledPeriod,
  type BillingPeriod,
} from "../components/packageUtils";

export default function PackagesPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading: billingLoading, error: billingError } = useBillingOverview();
  const updateSubscriptionMutation = useUpdateSubscriptionMutation();
  const [bannerExpandModalOpen, setBannerExpandModalOpen] = useState(false);
  const [trainingQuantity, setTrainingQuantity] = useState(0);
  const [storageQuantity, setStorageQuantity] = useState(0);
  const [question100Quantity, setQuestion100Quantity] = useState(0);
  const [question500Quantity, setQuestion500Quantity] = useState(0);
  const [selectedBillingPeriod, setSelectedBillingPeriod] = useState<BillingPeriod>("quarterly");
  const [planChangePending, setPlanChangePending] = useState<{ planCode: string; billingPeriod: BillingPeriod } | null>(null);
  const [planChangeSuccess, setPlanChangeSuccess] = useState<{ message: string; status: string } | null>(null);
  const [resourceBlockMessage, setResourceBlockMessage] = useState<string | null>(null);
  const [showAuthenticatorRequiredModal, setShowAuthenticatorRequiredModal] = useState(false);
  const authenticatorStatusQuery = useAuthenticatorStatus();

  const billingErrMsg =
    billingError && typeof (billingError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (billingError as { response?: { data?: { detail?: string } } }).response!.data!.detail
      : billingError
        ? t("common.errorGeneric")
        : null;
  const billingMutationError = updateSubscriptionMutation.error ? t("common.errorGeneric") : null;
  const displayError = billingErrMsg ?? billingMutationError;

  const catalog = useMemo(() => billingOverview?.catalog ?? [], [billingOverview?.catalog]);
  const planEntries = useMemo(() => catalog.filter((item) => item.entry_type === "plan"), [catalog]);
  const paidPlans = useMemo(() => sortPlans(planEntries.filter((p) => !isFreePlan(p))), [planEntries]);

  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");
  const { usedGb: usedStorageGb, usedKbCount } = readBillingResourceUsage(
    billingOverview?.usage as Record<string, unknown> | undefined
  );
  const scheduledPlanCode = subscription.scheduled_plan_code != null ? String(subscription.scheduled_plan_code) : null;
  const rawBillingPeriod = String(subscription.billing_period ?? "monthly").toLowerCase();
  const currentBillingPeriod: BillingPeriod =
    rawBillingPeriod === "monthly" || rawBillingPeriod === "quarterly" || rawBillingPeriod === "yearly"
      ? rawBillingPeriod
      : "monthly";

  const trainingInitialSubline = useMemo(() => {
    const a = getTrainingInitialAddonInfo(catalog);
    return t("packages.trainingInitialSubline").replace("{{euro}}", String(a.euro));
  }, [catalog, t]);

  const expansionOptions = useMemo(() => {
    const tag = localeTagForNumbers(locale);
    const trainingAddon = addonEntry(catalog, "training_extra_500k");
    const question100Addon = addonEntry(catalog, "question_pack_100");
    const question500Addon = addonEntry(catalog, "question_pack_500");
    const trainChars = includedNumber(trainingAddon, "training_chars", 500000);
    const perGbCents = getStoragePerGbCents(catalog);
    const storageBundleCents = FLEX_STORAGE_GB_BUNDLE * perGbCents;
    const question100Count = includedNumber(question100Addon, "questions", 100);
    const question500Count = includedNumber(question500Addon, "questions", 500);
    const trainingUnitPriceCents = trainingAddon ? Number(trainingAddon.price_cents) : 2900;
    const question100PriceCents = question100Addon ? Number(question100Addon.price_cents) : 120;
    const question500PriceCents = question500Addon ? Number(question500Addon.price_cents) : 500;
    return [
      {
        addonCode: "training_extra_500k",
        checkoutQuantity: trainingQuantity,
        title: t("packages.expandTrainingTitle").replace("{{chars}}", trainChars.toLocaleString(tag)),
        unitLabel: `${trainChars.toLocaleString(tag)} ${t("traffic.expandCharactersUnit")}`,
        unitPriceCents: trainingUnitPriceCents,
        quantity: trainingQuantity,
        setQuantity: setTrainingQuantity,
        totalCents: trainingUnitPriceCents * trainingQuantity,
      },
      {
        addonCode: "extra_storage_gb",
        checkoutQuantity: storageQuantity * FLEX_STORAGE_GB_BUNDLE,
        title: t("packages.expandStorageTitle").replace("{{gb}}", String(FLEX_STORAGE_GB_BUNDLE)),
        unitLabel: `${FLEX_STORAGE_GB_BUNDLE.toLocaleString(tag)} GB`,
        unitPriceCents: storageBundleCents,
        priceSuffix: `/ ${t("packages.perMonthSuffix")}`,
        quantity: storageQuantity,
        setQuantity: setStorageQuantity,
        totalCents: storageBundleCents * storageQuantity,
      },
      {
        addonCode: "question_pack_100",
        checkoutQuantity: question100Quantity,
        title: t("packages.expandQuestionsTitle").replace("{{count}}", String(question100Count)),
        unitLabel: t("packages.expandQuestionsTitle").replace("{{count}}", String(question100Count)).toLowerCase(),
        unitPriceCents: question100PriceCents,
        quantity: question100Quantity,
        setQuantity: setQuestion100Quantity,
        totalCents: question100PriceCents * question100Quantity,
      },
      {
        addonCode: "question_pack_500",
        checkoutQuantity: question500Quantity,
        title: t("packages.expandQuestionsTitle").replace("{{count}}", String(question500Count)),
        unitLabel: t("packages.expandQuestionsTitle").replace("{{count}}", String(question500Count)).toLowerCase(),
        unitPriceCents: question500PriceCents,
        quantity: question500Quantity,
        setQuantity: setQuestion500Quantity,
        totalCents: question500PriceCents * question500Quantity,
      },
    ];
  }, [catalog, locale, question100Quantity, question500Quantity, storageQuantity, t, trainingQuantity]);
  const selectedExpansionItems = expansionOptions.filter((item) => item.checkoutQuantity > 0);
  const expansionTotalPriceCents = expansionOptions.reduce((sum, item) => sum + item.totalCents, 0);
  const checkoutItemsParam = selectedExpansionItems
    .map((item) => `${item.addonCode}:${item.checkoutQuantity}`)
    .join(",");
  useEffect(() => {
    if (!bannerExpandModalOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setBannerExpandModalOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bannerExpandModalOpen]);

  useEffect(() => {
    if (!planChangePending && !planChangeSuccess && !resourceBlockMessage) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (resourceBlockMessage) setResourceBlockMessage(null);
      else if (planChangeSuccess) setPlanChangeSuccess(null);
      else if (planChangePending && !updateSubscriptionMutation.isPending) setPlanChangePending(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [planChangePending, planChangeSuccess, resourceBlockMessage, updateSubscriptionMutation.isPending]);

  useEffect(() => {
    const st = location.state as {
      checkoutComplete?: boolean;
      addonCheckoutComplete?: boolean;
      upgradeCheckoutComplete?: boolean;
      message?: string;
      status?: string;
    } | null;
    const msg = st?.message;
    const ok =
      (st?.checkoutComplete || st?.addonCheckoutComplete || st?.upgradeCheckoutComplete) &&
      typeof msg === "string" &&
      msg.length > 0;
    if (ok && msg) {
      setPlanChangeSuccess({ message: msg, status: st.status ?? "updated" });
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  const handleSwitchToPlan = (planCode: string) => {
    const target = catalog.find((e) => e.entry_type === "plan" && e.code === planCode);
    if (!target) return;
    const isTargetCurrent = planCode === currentPlanCode;
    const block = planResourceBlock(target, usedStorageGb, usedKbCount, isTargetCurrent);
    if (block.blocked) {
      setResourceBlockMessage(formatPlanResourceBlockMessage(block, usedStorageGb, usedKbCount, t));
      return;
    }
    if (currentPlanCode === "free") {
      if (!authenticatorStatusQuery.data?.enabled) {
        setShowAuthenticatorRequiredModal(true);
        return;
      }
      navigate(`/admin/csomagok/fizetes?plan=${encodeURIComponent(planCode)}&period=${selectedBillingPeriod}`);
      return;
    }
    if (isScheduledChange(currentPlanCode, planCode, currentBillingPeriod, selectedBillingPeriod)) {
      setPlanChangePending({ planCode, billingPeriod: selectedBillingPeriod });
      return;
    }
    navigate(
      `/admin/csomagok/felfele-fizetes?plan=${encodeURIComponent(planCode)}&period=${selectedBillingPeriod}`
    );
  };

  const confirmPlanChange = async () => {
    if (!planChangePending) return;
    try {
      const res = await updateSubscriptionMutation.mutateAsync({
        plan_code: planChangePending.planCode,
        billing_period: planChangePending.billingPeriod,
      });
      setPlanChangePending(null);
      setPlanChangeSuccess({ message: res.message, status: res.status });
    } catch {
      /* hiba a mutáción */
    }
  };

  const dateLocaleTag = localeTagForNumbers(locale);
  const periodToLabel =
    billingOverview?.current_period_end_iso != null && billingOverview.current_period_end_iso !== ""
      ? new Date(`${billingOverview.current_period_end_iso}T12:00:00`).toLocaleDateString(dateLocaleTag, { dateStyle: "long" })
      : "—";
  const currentPlanName =
    catalog.find((e) => e.entry_type === "plan" && e.code === currentPlanCode)?.name ?? currentPlanCode;
  const scheduledPlanName =
    scheduledPlanCode != null ? catalog.find((e) => e.entry_type === "plan" && e.code === scheduledPlanCode)?.name ?? scheduledPlanCode : null;
  const scheduledPeriodRaw = String(subscription.scheduled_billing_period ?? "").toLowerCase();
  const scheduledBillingPeriod: BillingPeriod =
    scheduledPeriodRaw === "yearly" ? "yearly" : scheduledPeriodRaw === "quarterly" ? "quarterly" : "monthly";

  const trialEndLabel = formatSubscriptionDateForBanner(subscription.trial_ends_at, dateLocaleTag);
  const bannerValidityDate =
    currentPlanCode === "free"
      ? trialEndLabel ?? (periodToLabel !== "—" ? periodToLabel : null)
      : periodToLabel !== "—"
        ? periodToLabel
        : null;

  const pendingTargetPlan = planChangePending
    ? catalog.find((e) => e.entry_type === "plan" && e.code === planChangePending.planCode) ?? null
    : null;
  const pendingBilledPhrase =
    planChangePending != null ? tBannerBilledPeriod(planChangePending.billingPeriod, t) : "";
  const pendingIsDowngrade =
    planChangePending != null
      ? isScheduledChange(currentPlanCode, planChangePending.planCode, currentBillingPeriod, planChangePending.billingPeriod)
      : false;

  const showBannerExpandButton = currentPlanCode !== "free";

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)]">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (billingLoading) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  return (
    <div className="app-page text-[var(--color-foreground)]">
      <div className="w-full max-w-6xl mx-auto mb-6 px-2">
        <PageHeader
          eyebrow={t("nav.packages")}
          title={t("nav.packages")}
        />
      </div>

      <PackageCurrentPlanBanner
        currentPlanName={currentPlanName}
        currentPlanCode={currentPlanCode}
        currentBillingPeriod={currentBillingPeriod}
        bannerValidityDate={bannerValidityDate}
        scheduledPlanCode={scheduledPlanCode}
        scheduledPlanName={scheduledPlanName}
        scheduledBillingPeriod={scheduledBillingPeriod}
        selectedBillingPeriod={selectedBillingPeriod}
        t={t}
        onSelectBillingPeriod={setSelectedBillingPeriod}
      />

      {displayError && (
        <Alert tone="error" className="mb-4">
          {displayError}
        </Alert>
      )}

      <div className="w-full max-w-6xl mx-auto space-y-10">
        <div className="grid gap-4 md:grid-cols-3 md:items-stretch">
          {paidPlans.map((plan) => (
            <PackagePlanCard
              key={plan.code}
              plan={plan}
              featured={plan.code === "growth"}
              currentPlanCode={currentPlanCode}
              scheduledPlanCode={scheduledPlanCode}
              selectedBillingPeriod={selectedBillingPeriod}
              currentBillingPeriod={currentBillingPeriod}
              pending={updateSubscriptionMutation.isPending}
              resourceBlocked={planResourceBlock(plan, usedStorageGb, usedKbCount, plan.code === currentPlanCode).blocked}
              trainingInitialSubline={trainingInitialSubline}
              t={t}
              onSwitch={handleSwitchToPlan}
            />
          ))}
        </div>

        {showBannerExpandButton ? (
          <PackageExpandBanner expansionOptions={expansionOptions} locale={locale} t={t} onOpen={() => setBannerExpandModalOpen(true)} />
        ) : null}

        <PackageStatusModals
          planChangePending={planChangePending}
          planChangeSuccess={planChangeSuccess}
          resourceBlockMessage={resourceBlockMessage}
          showAuthenticatorRequiredModal={showAuthenticatorRequiredModal}
          pendingTargetPlan={pendingTargetPlan}
          pendingBilledPhrase={pendingBilledPhrase}
          pendingIsDowngrade={pendingIsDowngrade}
          updatePending={updateSubscriptionMutation.isPending}
          t={t}
          onClosePending={() => setPlanChangePending(null)}
          onConfirmPlanChange={() => void confirmPlanChange()}
          onCloseSuccess={() => setPlanChangeSuccess(null)}
          onCloseResourceBlock={() => setResourceBlockMessage(null)}
          onCloseAuthenticatorRequired={() => setShowAuthenticatorRequiredModal(false)}
          onOpenSettings={() => {
            setShowAuthenticatorRequiredModal(false);
            navigate("/admin/settings");
          }}
        />

        <PackageExpansionModal
          open={bannerExpandModalOpen}
          expansionOptions={expansionOptions}
          selectedExpansionItemsCount={selectedExpansionItems.length}
          expansionTotalPriceCents={expansionTotalPriceCents}
          checkoutItemsParam={checkoutItemsParam}
          locale={locale}
          t={t}
          onClose={() => setBannerExpandModalOpen(false)}
          onCheckout={(itemsParam) => {
            setBannerExpandModalOpen(false);
            navigate(`/admin/csomagok/bovites-fizetes?items=${encodeURIComponent(itemsParam)}`);
          }}
        />

      </div>
    </div>
  );
}
