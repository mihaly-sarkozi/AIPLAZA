import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import {
  useBillingOverview,
  useUpdateSubscriptionMutation,
  type BillingCatalogEntry,
} from "../../billing/hooks/useBilling";
import {
  formatPlanResourceBlockMessage,
  planResourceBlock,
  readBillingResourceUsage,
} from "../planEligibility";
import { useAuthenticatorStatus } from "../../settings/hooks/useAuthenticator";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";

const PLAN_ORDER = ["free", "starter", "growth", "business"] as const;

const PLAN_RANK: Record<string, number> = { free: 0, starter: 1, growth: 2, business: 3 };
const BILLING_PERIOD_RANK: Record<string, number> = { monthly: 1, quarterly: 2, yearly: 3 };

function isPlanDowngrade(fromCode: string, toCode: string): boolean {
  return (PLAN_RANK[toCode] ?? 0) < (PLAN_RANK[fromCode] ?? 0);
}

function isBillingPeriodDowngrade(fromPeriod: string, toPeriod: string): boolean {
  return (BILLING_PERIOD_RANK[toPeriod] ?? 1) < (BILLING_PERIOD_RANK[fromPeriod] ?? 1);
}

function isScheduledChange(fromCode: string, toCode: string, fromPeriod: string, toPeriod: string): boolean {
  return isPlanDowngrade(fromCode, toCode) || (fromCode === toCode && isBillingPeriodDowngrade(fromPeriod, toPeriod));
}

function sortPlans(entries: BillingCatalogEntry[]): BillingCatalogEntry[] {
  const copy = [...entries];
  copy.sort((a, b) => {
    const ia = PLAN_ORDER.indexOf(a.code as (typeof PLAN_ORDER)[number]);
    const ib = PLAN_ORDER.indexOf(b.code as (typeof PLAN_ORDER)[number]);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  return copy;
}

function localeTagForNumbers(locale: string): string {
  if (locale === "es") return "es-ES";
  if (locale === "en") return "en-GB";
  return "hu-HU";
}

function formatTrainingCharsLabel(chars: number): string {
  if (chars >= 1_000_000 && chars % 1_000_000 === 0) return `${chars / 1_000_000}M`;
  if (chars >= 1000 && chars % 1000 === 0) return `${chars / 1000}k`;
  return String(chars);
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

const FLEX_STORAGE_GB_BUNDLE = 5;

function formatEuroLocaleFromCents(cents: number, locale: string): string {
  const value = Number(cents) / 100;
  const tag = localeTagForNumbers(locale);
  const whole = Math.round(value * 100) % 100 === 0;
  return value.toLocaleString(tag, whole ? { maximumFractionDigits: 0 } : { minimumFractionDigits: 1, maximumFractionDigits: 2 });
}

function getStoragePerGbCents(catalog: BillingCatalogEntry[]): number {
  const row = catalog.find((e) => e.entry_type === "addon" && e.code === "extra_storage_gb");
  return row ? Number(row.price_cents) : 500;
}

function addonEntry(catalog: BillingCatalogEntry[], code: string): BillingCatalogEntry | null {
  return catalog.find((item) => item.entry_type === "addon" && item.code === code) ?? null;
}

function includedNumber(entry: BillingCatalogEntry | null, key: string, fallback: number): number {
  const value = entry?.included?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function getTrainingInitialAddonInfo(catalog: BillingCatalogEntry[]): { euro: number; chars: number } {
  const row = catalog.find((e) => e.entry_type === "addon" && e.code === "training_initial_500k");
  const euro = row ? Math.floor(Number(row.price_cents) / 100) : 49;
  const raw = row?.included && typeof row.included === "object" ? (row.included as Record<string, unknown>).training_chars : null;
  const chars = raw != null && raw !== "" ? Number(raw) : 500000;
  return { euro, chars: Number.isFinite(chars) ? chars : 500000 };
}

/** Csomag sorai: a leírás (tagline) külön, a felhasználó sor után jön a bővíthetőség gomb helye. */
function planCardFeatureSections(entry: BillingCatalogEntry, t: (key: string) => string): {
  beforeUsers: string[];
  usersLine: string | null;
  afterUsers: string[];
  tagline: string | null;
} {
  const inc = entry.included ?? {};
  const meta = entry.metadata ?? {};
  const beforeUsers: string[] = [];

  if (inc.knowledge_bases != null) {
    beforeUsers.push(t("packages.lineKbs").replace("{{count}}", String(inc.knowledge_bases)));
  }
  if (inc.storage_gb != null) {
    beforeUsers.push(t("packages.lineStorage").replace("{{count}}", String(inc.storage_gb)));
  }
  if (inc.questions_monthly != null) {
    beforeUsers.push(t("packages.lineQuestions").replace("{{count}}", String(inc.questions_monthly)));
  }
  const training = Number(inc.training_chars ?? 0);
  if (training > 0) {
    const size = formatTrainingCharsLabel(training);
    let line = t("packages.lineTraining").replace("{{size}}", size);
    const note = typeof meta.training_note === "string" && meta.training_note.trim() ? meta.training_note.trim() : null;
    if (entry.code === "free" && note) {
      line += ` ${note}`;
    }
    beforeUsers.push(line);
  }

  let usersLine: string | null = null;
  if (Object.prototype.hasOwnProperty.call(inc, "max_users")) {
    const mu = inc.max_users;
    usersLine = mu == null ? t("packages.lineUsersUnlimited") : t("packages.lineUsersCount").replace("{{count}}", String(mu));
  }

  const afterUsers: string[] = [];
  const trial = Number(inc.trial_days ?? 0);
  if (trial > 0) {
    afterUsers.push(t("packages.lineTrial").replace("{{count}}", String(trial)));
  }

  const translatedTagline = t(`packages.planTagline_${entry.code}`);
  const tagline =
    translatedTagline !== `packages.planTagline_${entry.code}`
      ? translatedTagline
      : typeof meta.description === "string" && meta.description.trim()
        ? meta.description.trim()
        : null;

  return { beforeUsers, usersLine, afterUsers, tagline };
}

function paidPriceDisplay(
  plan: BillingCatalogEntry,
  period: string,
  t: (key: string) => string
): { monthEuro: number; listPeriodEuro: number | null; subline: string | null } {
  const listM = Math.floor(Number(plan.price_cents) / 100);
  const effM = flooredMonthlyEuroAfterDiscount(plan.price_cents, period);
  const monthEuro = period === "monthly" ? listM : effM;
  if (period === "monthly") {
    return { monthEuro, listPeriodEuro: null, subline: t("packages.billedMonthlyShort") };
  }
  if (period === "quarterly") {
    return { monthEuro, listPeriodEuro: listM * 3, subline: t("packages.billedQuarterly").replace("{{total}}", String(effM * 3)) };
  }
  return { monthEuro, listPeriodEuro: listM * 12, subline: t("packages.billedYearly").replace("{{total}}", String(effM * 12)) };
}

function isFreePlan(plan: BillingCatalogEntry): boolean {
  return plan.code === "free" || plan.price_cents === 0;
}

function paidCtaLabel(
  planCode: string,
  isScheduledHere: boolean,
  samePlanAndCycle: boolean,
  isCurrent: boolean,
  pending: boolean,
  t: (key: string) => string
): string {
  if (pending) return t("common.loading");
  if (isScheduledHere) return t("packages.ctaScheduled");
  if (samePlanAndCycle) return t("packages.ctaActivePlan");
  if (isCurrent) return t("packages.ctaChangeCycle");
  if (planCode === "starter") return t("packages.ctaPickStarter");
  if (planCode === "growth") return t("packages.ctaPickGrowth");
  if (planCode === "business") return t("packages.ctaPickBusiness");
  return t("packages.ctaPickFallback");
}

type BillingPeriod = "monthly" | "quarterly" | "yearly";

function tBannerBilledPeriod(period: BillingPeriod, t: (key: string) => string): string {
  if (period === "monthly") return t("packages.bannerBilledMonthly");
  if (period === "yearly") return t("packages.bannerBilledYearly");
  return t("packages.bannerBilledQuarterly");
}

function tPlanBillingParen(period: BillingPeriod, t: (key: string) => string): string {
  if (period === "monthly") return t("packages.planBillingParenMonthly");
  if (period === "yearly") return t("packages.planBillingParenYearly");
  return t("packages.planBillingParenQuarterly");
}

function formatSubscriptionDateForBanner(iso: unknown, dateLocaleTag: string): string | null {
  if (iso == null || iso === "") return null;
  const d = new Date(String(iso));
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(dateLocaleTag, { dateStyle: "long" });
}

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
  const changeQuantity = (setter: (value: number) => void, current: number, delta: number) => {
    setter(Math.max(0, Math.min(99, current + delta)));
  };

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
    ? catalog.find((e) => e.entry_type === "plan" && e.code === planChangePending.planCode)
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

  const segmentBtn = (period: BillingPeriod, label: string, badge: string | null) => {
    const active = selectedBillingPeriod === period;
    return (
      <button
        type="button"
        onClick={() => setSelectedBillingPeriod(period)}
        className={`min-w-[96px] rounded-xl px-4 py-2 text-sm font-medium transition ${
          active
            ? "bg-[var(--color-card)] text-[var(--color-foreground)] shadow-sm"
            : "text-[var(--color-muted)] hover:text-[var(--color-foreground)]"
        }`}
      >
        <span className="flex items-center justify-center gap-1.5 leading-tight text-center">
          <span>{label}</span>
          {badge ? (
            <span
              className={`text-xs font-semibold tabular-nums ${
                active ? "text-[var(--color-muted)]" : "text-[var(--color-accent-foreground)]"
              }`}
            >
              {badge}
            </span>
          ) : null}
        </span>
      </button>
    );
  };

  const renderPlanCard = (plan: BillingCatalogEntry, opts: { featured?: boolean }) => {
    const featured = opts.featured ?? false;
    const isCurrent = plan.code === currentPlanCode;
    const showPaidCurrentHighlight = isCurrent && currentPlanCode !== "free";
    const isScheduledHere = scheduledPlanCode != null && plan.code === scheduledPlanCode && plan.code !== currentPlanCode;
    const samePlanAndCycle = isCurrent && selectedBillingPeriod === currentBillingPeriod;
    const { beforeUsers, usersLine, afterUsers, tagline } = planCardFeatureSections(plan, t);
    const pending = updateSubscriptionMutation.isPending;
    const switchDisabled = pending || isScheduledHere || samePlanAndCycle;
    const resourceBlock = planResourceBlock(plan, usedStorageGb, usedKbCount, isCurrent);

    const borderClass = featured
      ? "border border-emerald-200 bg-emerald-50 ring-1 ring-emerald-200"
      : showPaidCurrentHighlight
        ? "border-2 border-[var(--color-primary)] bg-[var(--color-background)] ring-1 ring-[var(--color-primary)]/20"
        : "border border-[var(--color-border)] bg-[var(--color-background)]";

    const padClass = "p-4";

    const bulletRow = (line: string) => (
      <li key={`${plan.code}-${line}`} className="leading-snug pl-0 flex gap-2">
        <span className="text-[var(--color-muted)] shrink-0">·</span>
        <span>{line}</span>
      </li>
    );

    return (
      <div
        key={plan.code}
        className={`flex flex-col rounded-xl overflow-hidden ${borderClass}`}
      >
        <div className={`flex flex-col flex-1 ${padClass}`}>
          <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
            <div className="min-w-0 flex-1">
              <h3 className="font-semibold leading-tight text-lg">{plan.name}</h3>
              {tagline ? <p className="text-sm text-[var(--color-muted)] mt-1 leading-snug">{tagline}</p> : null}
            </div>
            <div className="flex flex-col items-end gap-1 shrink-0">
              {featured ? (
                <span className="text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                  {t("packages.badgePopular")}
                </span>
              ) : null}
              {isScheduledHere ? (
                <span className="text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-900 dark:text-amber-200">
                  {t("packages.badgeScheduled")}
                </span>
              ) : null}
              {resourceBlock.blocked ? (
                <span className="text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-neutral-500/25 text-neutral-900 dark:text-neutral-200">
                  {t("packages.planNotSelectableBadge")}
                </span>
              ) : null}
            </div>
          </div>

        <div className="mb-4">
          {(() => {
            const { monthEuro, listPeriodEuro, subline } = paidPriceDisplay(plan, selectedBillingPeriod, t);
            return (
              <>
                <div className="flex items-baseline gap-1 flex-wrap">
                  <span className="font-bold tabular-nums text-3xl">{monthEuro}</span>
                  <span className="font-medium text-[var(--color-muted)] text-base">
                    {t("packages.euroSymbol")}
                  </span>
                  <span className="text-[var(--color-muted)] text-base">
                    / {t("packages.perMonthSuffix")}
                  </span>
                </div>
                {subline ? (
                  <p className="text-xs text-[var(--color-muted)] mt-1.5 leading-snug">
                    {subline}
                    {listPeriodEuro != null ? (
                      <span className="ml-2 font-semibold text-red-600 line-through decoration-red-600 dark:text-red-400 dark:decoration-red-400">
                        {listPeriodEuro} {t("packages.euroSymbol")}
                      </span>
                    ) : null}
                  </p>
                ) : null}
                <p className="text-sm font-medium text-[var(--color-foreground)] mt-1.5 leading-snug rounded-md px-2 py-1.5 bg-neutral-400/55 dark:bg-neutral-600">
                  {trainingInitialSubline}
                </p>
              </>
            );
          })()}
        </div>

        <ul className="text-sm text-[var(--color-foreground)] space-y-2 flex-1">
          {beforeUsers.map(bulletRow)}
          {usersLine ? bulletRow(usersLine) : null}
        </ul>

        {afterUsers.length > 0 ? (
          <ul className="text-sm text-[var(--color-foreground)] space-y-2 mb-4">{afterUsers.map(bulletRow)}</ul>
        ) : null}

        <div className="mt-[10px]">
          {samePlanAndCycle ? (
            <p className="mt-auto w-full py-2.5 text-sm font-semibold text-center text-[var(--color-foreground)]">
              {t("packages.badgeCurrentPlan")}
            </p>
          ) : (
            <>
              {resourceBlock.blocked && !switchDisabled ? (
                <p className="text-xs text-amber-900/90 dark:text-amber-200/95 leading-snug mb-2">{t("packages.planNotSelectableHint")}</p>
              ) : null}

              <button
                type="button"
                onClick={() => handleSwitchToPlan(plan.code)}
                disabled={switchDisabled}
                className={`mt-auto w-full rounded-lg px-4 py-2.5 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed ${
                  resourceBlock.blocked && !switchDisabled
                    ? "border-2 border-amber-600/60 bg-amber-500/10 text-amber-950 dark:text-amber-100 hover:bg-amber-500/15"
                    : featured
                      ? "bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)]"
                      : "bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)]"
                }`}
              >
                {resourceBlock.blocked && !switchDisabled
                  ? t("packages.planNotSelectableCta")
                  : paidCtaLabel(plan.code, isScheduledHere, samePlanAndCycle, isCurrent, pending, t)}
              </button>
            </>
          )}
        </div>
        </div>
      </div>
    );
  };

  return (
    <div className="app-page text-[var(--color-foreground)]">
      <div className="w-full max-w-6xl mx-auto mb-6 px-2">
        <PageHeader
          eyebrow={t("nav.packages")}
          title={t("nav.packages")}
        />
      </div>

      <div className="w-full max-w-6xl mx-auto mb-6 grid gap-4 px-2 md:grid-cols-2">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-sm leading-relaxed">
          <div className="space-y-1.5 min-w-0">
              <p className="font-normal text-[var(--color-foreground)]">
                <span className="text-[var(--color-muted)]">{t("packages.yourPlanBannerLabel")}</span>{" "}
                <span className="font-semibold text-[var(--color-foreground)]">{currentPlanName}</span>
                {currentPlanCode === "free" ? (
                  <span className="text-[var(--color-muted)]"> {t("packages.planBillingParenFree")}</span>
                ) : (
                  <span className="text-[var(--color-muted)]"> {tPlanBillingParen(currentBillingPeriod, t)}</span>
                )}
              </p>
              {bannerValidityDate != null ? (
                <p className="font-normal text-[var(--color-muted)]">
                  <span>{t("packages.yourPlanBannerValidityPrefix")}</span>
                  <span className="font-semibold text-[var(--color-foreground)]">{bannerValidityDate}</span>
                  <span>{t("packages.yourPlanBannerValiditySuffix")}</span>
                </p>
              ) : null}
              {scheduledPlanCode != null && scheduledPlanName != null ? (
                <p className="font-normal mt-2 pt-2 border-t border-[var(--color-border)] text-[var(--color-muted)]">
                  <span>{t("packages.yourPlanBannerScheduledLead")}</span>{" "}
                  <span className="font-semibold text-[var(--color-foreground)]">{scheduledPlanName}</span>
                  <span> {tPlanBillingParen(scheduledBillingPeriod, t)}</span>
                </p>
              ) : null}
          </div>
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-end">
          <div className="md:text-right">
            <p className="text-sm font-normal text-[var(--color-muted)]">{t("packages.billingLabel")}</p>
          </div>
          <div
            role="group"
            aria-label={t("packages.billingLabel")}
            className="flex w-full flex-wrap rounded-2xl bg-[var(--color-card-muted)] p-1 md:w-auto"
          >
            {segmentBtn("monthly", t("packages.segmentMonthly"), null)}
            {segmentBtn("quarterly", t("packages.segmentQuarterly"), t("packages.segmentSaveQuarterly"))}
            {segmentBtn("yearly", t("packages.segmentYearly"), t("packages.segmentSaveYearly"))}
          </div>
        </div>
      </div>

      {displayError && (
        <Alert tone="error" className="mb-4">
          {displayError}
        </Alert>
      )}

      <div className="w-full max-w-6xl mx-auto space-y-10">
        <div className="grid gap-4 md:grid-cols-3 md:items-stretch">
          {paidPlans.map((plan) => renderPlanCard(plan, { featured: plan.code === "growth" }))}
        </div>

        {showBannerExpandButton ? (
          <div className="mx-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-sm leading-relaxed">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="font-semibold text-[var(--color-foreground)]">{t("packages.bannerExpandModalTitle")}</p>
                <p className="mt-1 text-xs text-[var(--color-muted)]">{t("packages.planChangeTimingNotice")}</p>
                <p className="mt-2 text-xs leading-relaxed text-[var(--color-muted)]">
                  {expansionOptions
                    .map((item) => {
                      const price = `${formatEuroLocaleFromCents(item.unitPriceCents, locale)} € ${t("packages.taxSuffix")}`;
                      return `${item.title}: ${price}${item.priceSuffix ? ` ${item.priceSuffix}` : ""}`;
                    })
                    .join(" · ")}
                </p>
              </div>
              <Button type="button" onClick={() => setBannerExpandModalOpen(true)} className="shrink-0 self-start sm:self-center">
                {t("packages.bannerExpandCta")}
              </Button>
            </div>
          </div>
        ) : null}

        {planChangePending ? (
          <div
            className="fixed inset-0 z-[85] flex items-center justify-center p-4 bg-black/40"
            role="presentation"
            onClick={() => {
              if (!updateSubscriptionMutation.isPending) setPlanChangePending(null);
            }}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="packages-change-confirm-title"
              className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl max-w-md w-full shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-4 py-4 border-b border-[var(--color-border)]">
                <h2 id="packages-change-confirm-title" className="text-base font-semibold text-[var(--color-foreground)]">
                  {t("packages.changeConfirmTitle")}
                </h2>
              </div>
              <div className="px-4 py-4 text-sm text-[var(--color-foreground)] leading-relaxed">
                <p>
                  {t("packages.changeConfirmIntro")
                    .replace("{{plan}}", pendingTargetPlan?.name ?? planChangePending.planCode)
                    .replace("{{billed}}", pendingBilledPhrase)
                    .replace(
                      "{{when}}",
                      pendingIsDowngrade ? t("packages.changeConfirmWhenScheduled") : t("packages.changeConfirmWhenImmediate")
                    )}
                </p>
              </div>
              <div className="px-4 pb-4 flex flex-wrap gap-2 justify-end">
                <button
                  type="button"
                  className="rounded-lg px-3 py-2 text-sm font-medium border border-[var(--color-border)] text-[var(--color-foreground)] hover:bg-[var(--color-border)]/25 disabled:opacity-50"
                  disabled={updateSubscriptionMutation.isPending}
                  onClick={() => setPlanChangePending(null)}
                >
                  {t("packages.changeConfirmCancel")}
                </button>
                <button
                  type="button"
                  className="rounded-lg px-3 py-2 text-sm font-semibold bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90 disabled:opacity-50"
                  disabled={updateSubscriptionMutation.isPending}
                  onClick={() => void confirmPlanChange()}
                >
                  {updateSubscriptionMutation.isPending ? t("common.loading") : t("packages.changeConfirmOk")}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {planChangeSuccess ? (
          <div
            className="fixed inset-0 z-[85] flex items-center justify-center p-4 bg-black/40"
            role="presentation"
            onClick={() => setPlanChangeSuccess(null)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="packages-change-success-title"
              className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl max-w-md w-full shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-4 py-4 border-b border-[var(--color-border)]">
                <h2 id="packages-change-success-title" className="text-base font-semibold text-[var(--color-foreground)]">
                  {t("packages.changeSuccessTitle")}
                </h2>
              </div>
              <div className="px-4 py-4 text-sm text-[var(--color-foreground)] leading-relaxed whitespace-pre-wrap">
                {planChangeSuccess.message}
              </div>
              <div className="px-4 pb-4 flex justify-end">
                <button
                  type="button"
                  className="rounded-lg px-3 py-2 text-sm font-semibold bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
                  onClick={() => setPlanChangeSuccess(null)}
                >
                  {t("packages.changeSuccessClose")}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {resourceBlockMessage ? (
          <div
            className="fixed inset-0 z-[86] flex items-center justify-center p-4 bg-black/40"
            role="presentation"
            onClick={() => setResourceBlockMessage(null)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="packages-resource-block-title"
              className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl max-w-md w-full shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-4 py-4 border-b border-[var(--color-border)]">
                <h2 id="packages-resource-block-title" className="text-base font-semibold text-[var(--color-foreground)]">
                  {t("packages.planBlockedModalTitle")}
                </h2>
              </div>
              <div className="px-4 py-4 text-sm text-[var(--color-foreground)] leading-relaxed whitespace-pre-wrap">
                {resourceBlockMessage}
              </div>
              <div className="px-4 pb-4 flex justify-end">
                <button
                  type="button"
                  className="rounded-lg px-3 py-2 text-sm font-semibold bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
                  onClick={() => setResourceBlockMessage(null)}
                >
                  {t("packages.changeSuccessClose")}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {showAuthenticatorRequiredModal ? (
          <div
            className="fixed inset-0 z-[87] flex items-center justify-center p-4 bg-black/40"
            role="presentation"
            onClick={() => setShowAuthenticatorRequiredModal(false)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="packages-authenticator-required-title"
              className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl max-w-md w-full shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-4 py-4 border-b border-[var(--color-border)]">
                <h2 id="packages-authenticator-required-title" className="text-base font-semibold text-[var(--color-foreground)]">
                  Authenticator szükséges az előfizetéshez
                </h2>
              </div>
              <div className="px-4 py-4 text-sm text-[var(--color-foreground)] leading-relaxed">
                <p>
                  A próbaidőszak alatt a kétfaktoros hitelesítés opcionális, de előfizetés indításához kötelező a Google
                  Authenticator aktiválása.
                </p>
              </div>
              <div className="px-4 pb-4 flex flex-wrap justify-end gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setShowAuthenticatorRequiredModal(false)}
                >
                  Később
                </Button>
                <Button
                  type="button"
                  onClick={() => {
                    setShowAuthenticatorRequiredModal(false);
                    navigate("/admin/settings");
                  }}
                >
                  Authenticator beállítása
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {bannerExpandModalOpen ? (
          <div
            className="fixed inset-0 z-[83] flex items-center justify-center p-4 bg-black/40"
            role="presentation"
            onClick={() => setBannerExpandModalOpen(false)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="packages-banner-expand-title"
              className="w-full max-w-2xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-[var(--color-muted)]">{t("packages.bannerExpandCta")}</p>
                  <h2 id="packages-banner-expand-title" className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">
                    {t("traffic.expandModalTitle")}
                  </h2>
                </div>
                <button
                  type="button"
                  className="rounded-lg px-2 py-1 text-sm text-[var(--color-muted)] hover:bg-[var(--color-card-muted)] hover:text-[var(--color-foreground)]"
                  onClick={() => setBannerExpandModalOpen(false)}
                >
                  {t("common.close")}
                </button>
              </div>

              <div className="mt-5 grid gap-2">
                {expansionOptions.map((item) => (
                  <div key={item.addonCode} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2.5">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-[var(--color-foreground)]">{item.title}</p>
                        <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                          {t("traffic.expandUnitPrice")
                            .replace("{{unit}}", item.unitLabel)
                            .replace("{{price}}", `${formatEuroLocaleFromCents(item.unitPriceCents, locale)} €`)}
                          {item.priceSuffix ? ` ${item.priceSuffix}` : ""}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-4">
                        <div className="flex items-center rounded-lg border border-[var(--color-border)]">
                          <button type="button" className="px-2 py-1 text-sm" onClick={() => changeQuantity(item.setQuantity, item.quantity, -1)}>
                            -
                          </button>
                          <span className="min-w-8 px-2 text-center text-sm tabular-nums">{item.quantity}</span>
                          <button type="button" className="px-2 py-1 text-sm" onClick={() => changeQuantity(item.setQuantity, item.quantity, 1)}>
                            +
                          </button>
                        </div>
                        <span className="min-w-24 text-right text-sm font-medium text-[var(--color-foreground)]">
                          {formatEuroLocaleFromCents(item.totalCents, locale)} € {t("packages.taxSuffix")}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}

                <p className="px-1 text-xs text-[var(--color-muted)]">{t("traffic.expandOtherOptionsHint")}</p>

                <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card-muted)] px-3 py-2.5">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-[var(--color-muted)]">{t("traffic.expandTotal")}</span>
                    <span className="text-lg font-semibold text-[var(--color-foreground)]">
                      {formatEuroLocaleFromCents(expansionTotalPriceCents, locale)} € {t("packages.taxSuffix")}
                    </span>
                  </div>
                  <Button
                    type="button"
                    fullWidth
                    className="mt-3"
                    disabled={selectedExpansionItems.length === 0}
                    onClick={() => {
                      setBannerExpandModalOpen(false);
                      navigate(`/admin/csomagok/bovites-fizetes?items=${encodeURIComponent(checkoutItemsParam)}`);
                    }}
                  >
                    {t("traffic.expandPay")}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ) : null}

      </div>
    </div>
  );
}
