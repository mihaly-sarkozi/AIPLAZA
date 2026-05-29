import type { BillingCatalogEntry } from "../../billing/hooks/useBilling";
import type { SettingsDateFormat, SettingsTimezone } from "../../../api/services/settingsService";
import { formatDateOnly } from "../../../utils/dateTimeFormatting";

export const PLAN_ORDER = ["free", "starter", "growth", "business"] as const;
export const FLEX_STORAGE_GB_BUNDLE = 5;

const PLAN_RANK: Record<string, number> = { free: 0, starter: 1, growth: 2, business: 3 };
const BILLING_PERIOD_RANK: Record<string, number> = { monthly: 1, quarterly: 2, yearly: 3 };

export type BillingPeriod = "monthly" | "quarterly" | "yearly";

export function isPlanDowngrade(fromCode: string, toCode: string): boolean {
  return (PLAN_RANK[toCode] ?? 0) < (PLAN_RANK[fromCode] ?? 0);
}

export function isBillingPeriodDowngrade(fromPeriod: string, toPeriod: string): boolean {
  return (BILLING_PERIOD_RANK[toPeriod] ?? 1) < (BILLING_PERIOD_RANK[fromPeriod] ?? 1);
}

export function isScheduledChange(fromCode: string, toCode: string, fromPeriod: string, toPeriod: string): boolean {
  return isPlanDowngrade(fromCode, toCode) || (fromCode === toCode && isBillingPeriodDowngrade(fromPeriod, toPeriod));
}

export function sortPlans(entries: BillingCatalogEntry[]): BillingCatalogEntry[] {
  const copy = [...entries];
  copy.sort((a, b) => {
    const ia = PLAN_ORDER.indexOf(a.code as (typeof PLAN_ORDER)[number]);
    const ib = PLAN_ORDER.indexOf(b.code as (typeof PLAN_ORDER)[number]);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
  return copy;
}

export function localeTagForNumbers(locale: string): string {
  if (locale === "es") return "es-ES";
  if (locale === "en") return "en-GB";
  return "hu-HU";
}

export function formatTrainingCharsLabel(chars: number): string {
  if (chars >= 1_000_000 && chars % 1_000_000 === 0) return `${chars / 1_000_000}M`;
  if (chars >= 1000 && chars % 1000 === 0) return `${chars / 1000}k`;
  return String(chars);
}

export function billingDiscountPercent(period: string): number {
  const p = (period || "monthly").toLowerCase();
  if (p === "quarterly") return 7;
  if (p === "yearly") return 15;
  return 0;
}

export function discountedMonthlyCents(priceCents: number, period: string): number {
  const d = billingDiscountPercent(period);
  if (d <= 0) return priceCents;
  return Math.round((Number(priceCents) * (100 - d)) / 100);
}

export function flooredMonthlyEuroAfterDiscount(priceCents: number, selectedPeriod: string): number {
  const monthlyDiscCents = discountedMonthlyCents(priceCents, selectedPeriod);
  return Math.floor(Number(monthlyDiscCents) / 100);
}

export function formatEuroLocaleFromCents(cents: number, locale: string): string {
  const value = Number(cents) / 100;
  const tag = localeTagForNumbers(locale);
  const whole = Math.round(value * 100) % 100 === 0;
  return value.toLocaleString(tag, whole ? { maximumFractionDigits: 0 } : { minimumFractionDigits: 1, maximumFractionDigits: 2 });
}

export function getStoragePerGbCents(catalog: BillingCatalogEntry[]): number {
  const row = catalog.find((entry) => entry.entry_type === "addon" && entry.code === "extra_storage_gb");
  return row ? Number(row.price_cents) : 500;
}

export function addonEntry(catalog: BillingCatalogEntry[], code: string): BillingCatalogEntry | null {
  return catalog.find((item) => item.entry_type === "addon" && item.code === code) ?? null;
}

export function includedNumber(entry: BillingCatalogEntry | null, key: string, fallback: number): number {
  const value = entry?.included?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

export function getTrainingInitialAddonInfo(catalog: BillingCatalogEntry[]): { euro: number; chars: number } {
  const row = catalog.find((entry) => entry.entry_type === "addon" && entry.code === "training_initial_500k");
  const euro = row ? Math.floor(Number(row.price_cents) / 100) : 29;
  const raw = row?.included && typeof row.included === "object" ? (row.included as Record<string, unknown>).training_chars : null;
  const chars = raw != null && raw !== "" ? Number(raw) : 1000000;
  return { euro, chars: Number.isFinite(chars) ? chars : 1000000 };
}

export function trainingInitialFeeEuroForPlan(planCode: string, catalog: BillingCatalogEntry[]): number {
  const normalized = String(planCode || "").toLowerCase();
  if (normalized === "growth") return 89;
  if (normalized === "business") return 489;
  return getTrainingInitialAddonInfo(catalog).euro;
}

export function planCardFeatureSections(entry: BillingCatalogEntry, t: (key: string) => string) {
  const inc = entry.included ?? {};
  const meta = entry.metadata ?? {};
  const beforeUsers: string[] = [];
  if (inc.knowledge_bases != null) beforeUsers.push(t("packages.lineKbs").replace("{{count}}", String(inc.knowledge_bases)));
  if (inc.storage_gb != null) beforeUsers.push(t("packages.lineStorage").replace("{{count}}", String(inc.storage_gb)));
  if (inc.questions_monthly != null) beforeUsers.push(t("packages.lineQuestions").replace("{{count}}", String(inc.questions_monthly)));
  const training = Number(inc.training_chars ?? 0);
  if (training > 0) {
    let line = t("packages.lineTraining").replace("{{size}}", formatTrainingCharsLabel(training));
    const note = typeof meta.training_note === "string" && meta.training_note.trim() ? meta.training_note.trim() : null;
    if (entry.code === "free" && note) line += ` ${note}`;
    beforeUsers.push(line);
  }
  const usersLine = Object.prototype.hasOwnProperty.call(inc, "max_users")
    ? inc.max_users == null
      ? t("packages.lineUsersUnlimited")
      : t("packages.lineUsersCount").replace("{{count}}", String(inc.max_users))
    : null;
  const trial = Number(inc.trial_days ?? 0);
  const afterUsers = trial > 0 ? [t("packages.lineTrial").replace("{{count}}", String(trial))] : [];
  const translatedTagline = t(`packages.planTagline_${entry.code}`);
  const tagline =
    translatedTagline !== `packages.planTagline_${entry.code}`
      ? translatedTagline
      : typeof meta.description === "string" && meta.description.trim()
        ? meta.description.trim()
        : null;
  return { beforeUsers, usersLine, afterUsers, tagline };
}

export function paidPriceDisplay(plan: BillingCatalogEntry, period: string, t: (key: string) => string) {
  const listM = Math.floor(Number(plan.price_cents) / 100);
  const effM = flooredMonthlyEuroAfterDiscount(plan.price_cents, period);
  const monthEuro = period === "monthly" ? listM : effM;
  if (period === "monthly") return { monthEuro, listPeriodEuro: null, subline: t("packages.billedMonthlyShort") };
  if (period === "quarterly") {
    return { monthEuro, listPeriodEuro: listM * 3, subline: t("packages.billedQuarterly").replace("{{total}}", String(effM * 3)) };
  }
  return { monthEuro, listPeriodEuro: listM * 12, subline: t("packages.billedYearly").replace("{{total}}", String(effM * 12)) };
}

export function isFreePlan(plan: BillingCatalogEntry): boolean {
  return plan.code === "free" || plan.price_cents === 0;
}

export function paidCtaLabel(
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

export function tBannerBilledPeriod(period: BillingPeriod, t: (key: string) => string): string {
  if (period === "monthly") return t("packages.bannerBilledMonthly");
  if (period === "yearly") return t("packages.bannerBilledYearly");
  return t("packages.bannerBilledQuarterly");
}

export function tPlanBillingParen(period: BillingPeriod, t: (key: string) => string): string {
  if (period === "monthly") return t("packages.planBillingParenMonthly");
  if (period === "yearly") return t("packages.planBillingParenYearly");
  return t("packages.planBillingParenQuarterly");
}

export function formatSubscriptionDateForBanner(
  iso: unknown,
  localeOrDateLocaleTag: string,
  timezone?: SettingsTimezone | string,
  dateFormat?: SettingsDateFormat
): string | null {
  if (iso == null || iso === "") return null;
  const date = new Date(String(iso));
  if (Number.isNaN(date.getTime())) return null;
  const locale = localeOrDateLocaleTag === "en-GB" ? "en" : localeOrDateLocaleTag === "es-ES" ? "es" : "hu";
  return formatDateOnly(iso, { locale, timezone, dateFormat, dateStyle: dateFormat ? undefined : "long" });
}
