import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import {
  useBillingOverview,
  useCancelSubscriptionMutation,
  useDeleteServiceAccessMutation,
  useRestoreSubscriptionRenewalMutation,
  useUpdateSubscriptionMutation,
} from "../../billing/hooks/useBilling";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import { formatDateOnly } from "../../../utils/dateTimeFormatting";
import {
  formatPlanResourceBlockMessage,
  planResourceBlock,
  readBillingResourceUsage,
} from "../planEligibility";
import { useAuthenticatorStatus } from "../../settings/hooks/useAuthenticator";
import Alert from "../../../components/ui/Alert";
import PageHeader from "../../../components/ui/PageHeader";
import PackageCurrentPlanBanner from "../components/PackageCurrentPlanBanner";
import PackageCancellationSection from "../components/PackageCancellationSection";
import PackageExpandBanner from "../components/PackageExpandBanner";
import PackageExpansionModal from "../components/PackageExpansionModal";
import PackagePlanCard from "../components/PackagePlanCard";
import PackageStatusModals from "../components/PackageStatusModals";
import {
  FLEX_STORAGE_GB_BUNDLE,
  addonEntry,
  formatSubscriptionDateForBanner,
  getStoragePerGbCents,
  includedNumber,
  isFreePlan,
  isScheduledChange,
  localeTagForNumbers,
  sortPlans,
  tBannerBilledPeriod,
  trainingInitialFeeEuroForPlan,
  type BillingPeriod,
} from "../components/packageUtils";

export default function PackagesPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { data: settings } = useLocaleSettings({ enabled: user?.role === "owner" });
  const { data: billingOverview, isLoading: billingLoading, error: billingError } = useBillingOverview();
  const updateSubscriptionMutation = useUpdateSubscriptionMutation();
  const cancelSubscriptionMutation = useCancelSubscriptionMutation();
  const restoreSubscriptionRenewalMutation = useRestoreSubscriptionRenewalMutation();
  const deleteServiceAccessMutation = useDeleteServiceAccessMutation();
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

  const expansionOptions = useMemo(() => {
    const tag = localeTagForNumbers(locale);
    const formatTrainingCharsForExpansion = (value: number): string => {
      if (value >= 1_000_000 && value % 1_000_000 === 0) {
        const millions = value / 1_000_000;
        if (locale === "en") return `${millions} Million`;
        if (locale === "es") return `${millions} Millón`;
        return `${millions} Millió`;
      }
      return value.toLocaleString(tag);
    };
    const trainingAddon = addonEntry(catalog, "training_extra_500k");
    const question100Addon = addonEntry(catalog, "question_pack_100");
    const question500Addon = addonEntry(catalog, "question_pack_500");
    const trainChars = includedNumber(trainingAddon, "training_chars", 1000000);
    const trainCharsLabel = formatTrainingCharsForExpansion(trainChars);
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
        title: t("packages.expandTrainingTitle").replace("{{chars}}", trainCharsLabel),
        unitLabel: `${trainCharsLabel} ${t("traffic.expandCharactersUnit")}`,
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
      navigate(`/admin/pricing/checkout?plan=${encodeURIComponent(planCode)}&period=${selectedBillingPeriod}`);
      return;
    }
    if (isScheduledChange(currentPlanCode, planCode, currentBillingPeriod, selectedBillingPeriod)) {
      setPlanChangePending({ planCode, billingPeriod: selectedBillingPeriod });
      return;
    }
    navigate(
      `/admin/pricing/upgrade-checkout?plan=${encodeURIComponent(planCode)}&period=${selectedBillingPeriod}`
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

  const periodToLabel =
    billingOverview?.current_period_end_iso != null && billingOverview.current_period_end_iso !== ""
      ? formatDateOnly(billingOverview.current_period_end_iso, {
          locale,
          timezone: settings?.timezone,
          dateFormat: settings?.date_format,
          dateStyle: settings?.date_format ? undefined : "long",
        })
      : "—";
  const currentPlanName =
    catalog.find((e) => e.entry_type === "plan" && e.code === currentPlanCode)?.name ?? currentPlanCode;
  const scheduledPlanName =
    scheduledPlanCode != null ? catalog.find((e) => e.entry_type === "plan" && e.code === scheduledPlanCode)?.name ?? scheduledPlanCode : null;
  const scheduledPeriodRaw = String(subscription.scheduled_billing_period ?? "").toLowerCase();
  const scheduledBillingPeriod: BillingPeriod =
    scheduledPeriodRaw === "yearly" ? "yearly" : scheduledPeriodRaw === "quarterly" ? "quarterly" : "monthly";

  const trialEndLabel = formatSubscriptionDateForBanner(subscription.trial_ends_at, locale, settings?.timezone, settings?.date_format);
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
  const cancellationRequest =
    subscription.cancellation_request && typeof subscription.cancellation_request === "object"
      ? (subscription.cancellation_request as Record<string, unknown>)
      : null;
  const autoRenewal = subscription.auto_renewal == null ? cancellationRequest == null : Boolean(subscription.auto_renewal);
  const cancellationMutationError =
    deleteServiceAccessMutation.error ??
    restoreSubscriptionRenewalMutation.error ??
    cancelSubscriptionMutation.error;
  const cancellationError: string | null =
    cancellationMutationError &&
    typeof (cancellationMutationError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? ((cancellationMutationError as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? null)
      : cancellationMutationError
        ? t("common.errorGeneric")
        : null;

  const handleCancelSubscription = async (body: { reason_code: string; reason_text: string }) => {
    try {
      await cancelSubscriptionMutation.mutateAsync(body);
    } catch {
      /* axios error surfaced via mutation */
    }
  };

  const handleDeleteServiceAccess = async () => {
    try {
      await deleteServiceAccessMutation.mutateAsync();
      logout();
      navigate("/service-deleted", { replace: true });
    } catch {
      /* axios error surfaced via mutation */
    }
  };

  const handleRestoreSubscriptionRenewal = async () => {
    try {
      await restoreSubscriptionRenewalMutation.mutateAsync();
    } catch {
      /* axios error surfaced via mutation */
    }
  };

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

      {currentPlanCode !== "free" ? (
        <PackageCancellationSection
          activeKnowledgeBaseCount={usedKbCount}
          autoRenewal={autoRenewal}
          cancellationRequest={cancellationRequest}
          validUntilLabel={bannerValidityDate ?? periodToLabel}
          currentHost={typeof window !== "undefined" ? window.location.host : ""}
          locale={locale}
          t={t}
          cancelPending={cancelSubscriptionMutation.isPending}
          restorePending={restoreSubscriptionRenewalMutation.isPending}
          deletePending={deleteServiceAccessMutation.isPending}
          errorMessage={cancellationError}
          onCancel={(body) => void handleCancelSubscription(body)}
          onRestoreRenewal={() => void handleRestoreSubscriptionRenewal()}
          onDeleteAccess={() => void handleDeleteServiceAccess()}
          onOpenKnowledgeBases={() => navigate("/kb")}
        />
      ) : null}

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
              trainingInitialSubline={t("packages.trainingInitialSubline").replace(
                "{{euro}}",
                String(trainingInitialFeeEuroForPlan(plan.code, catalog))
              )}
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
            navigate(`/admin/pricing/addon-checkout?items=${encodeURIComponent(itemsParam)}`);
          }}
        />

      </div>
    </div>
  );
}
