import type { BillingCatalogEntry } from "../../billing/hooks/useBilling";
import { paidCtaLabel, paidPriceDisplay, planCardFeatureSections, type BillingPeriod } from "./packageUtils";

type PackagePlanCardProps = {
  plan: BillingCatalogEntry;
  featured: boolean;
  currentPlanCode: string;
  scheduledPlanCode: string | null;
  selectedBillingPeriod: BillingPeriod;
  currentBillingPeriod: BillingPeriod;
  pending: boolean;
  resourceBlocked: boolean;
  trainingInitialSubline: string;
  t: (key: string) => string;
  onSwitch: (planCode: string) => void;
};

export default function PackagePlanCard({
  plan,
  featured,
  currentPlanCode,
  scheduledPlanCode,
  selectedBillingPeriod,
  currentBillingPeriod,
  pending,
  resourceBlocked,
  trainingInitialSubline,
  t,
  onSwitch,
}: PackagePlanCardProps) {
  const isCurrent = plan.code === currentPlanCode;
  const showPaidCurrentHighlight = isCurrent && currentPlanCode !== "free";
  const isScheduledHere = scheduledPlanCode != null && plan.code === scheduledPlanCode && plan.code !== currentPlanCode;
  const samePlanAndCycle = isCurrent && selectedBillingPeriod === currentBillingPeriod;
  const { beforeUsers, usersLine, afterUsers, tagline } = planCardFeatureSections(plan, t);
  const switchDisabled = pending || isScheduledHere || samePlanAndCycle;
  const borderClass = showPaidCurrentHighlight
    ? "border-2 border-[var(--color-primary)] bg-[var(--color-background)] ring-1 ring-[var(--color-primary)]/20 dark:bg-neutral-700"
    : featured
      ? "package-plan-card-featured border border-emerald-200 bg-emerald-50 ring-1 ring-emerald-200"
      : "border border-[var(--color-border)] bg-[var(--color-background)]";
  const bulletRow = (line: string) => (
    <li key={`${plan.code}-${line}`} className="leading-snug pl-0 flex gap-2">
      <span className="text-[var(--color-muted)] shrink-0">·</span>
      <span>{line}</span>
    </li>
  );
  const { monthEuro, listPeriodEuro, subline } = paidPriceDisplay(plan, selectedBillingPeriod, t);

  return (
    <div className={`flex flex-col rounded-xl overflow-hidden ${borderClass}`}>
      <div className="flex flex-col flex-1 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold leading-tight text-lg">{plan.name}</h3>
            {tagline ? <p className="text-sm text-[var(--color-muted)] mt-1 leading-snug">{tagline}</p> : null}
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            {featured ? <Badge className="package-plan-card-featured-badge bg-emerald-100 text-emerald-700">{t("packages.badgePopular")}</Badge> : null}
            {samePlanAndCycle ? <Badge className="bg-orange-500 text-white">{t("packages.badgeCurrentPlan")}</Badge> : null}
            {isScheduledHere ? <Badge className="bg-amber-500/20 text-amber-900 dark:text-amber-200">{t("packages.badgeScheduled")}</Badge> : null}
            {resourceBlocked ? <Badge className="bg-neutral-500/25 text-neutral-900 dark:text-neutral-200">{t("packages.planNotSelectableBadge")}</Badge> : null}
          </div>
        </div>

        <div className="mb-4">
          <div className="flex items-baseline gap-1 flex-wrap">
            <span className="font-bold tabular-nums text-3xl">{monthEuro}</span>
            <span className="font-medium text-[var(--color-muted)] text-base">{t("packages.euroSymbol")}</span>
            <span className="text-[var(--color-muted)] text-base">/ {t("packages.perMonthSuffix")}</span>
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
        </div>

        <ul className="text-sm text-[var(--color-foreground)] space-y-2 flex-1">
          {beforeUsers.map(bulletRow)}
          {usersLine ? bulletRow(usersLine) : null}
        </ul>
        {afterUsers.length > 0 ? <ul className="text-sm text-[var(--color-foreground)] space-y-2 mb-4">{afterUsers.map(bulletRow)}</ul> : null}

        <div className="mt-[10px]">
          {!samePlanAndCycle ? (
            <>
              {resourceBlocked && !switchDisabled ? (
                <p className="text-xs text-amber-900/90 dark:text-amber-200/95 leading-snug mb-2">{t("packages.planNotSelectableHint")}</p>
              ) : null}
              <button
                type="button"
                onClick={() => onSwitch(plan.code)}
                disabled={switchDisabled}
                className={`mt-auto w-full rounded-lg px-4 py-2.5 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed ${
                  resourceBlocked && !switchDisabled
                    ? "border-2 border-amber-600/60 bg-amber-500/10 text-amber-950 dark:text-amber-100 hover:bg-amber-500/15"
                    : "bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)]"
                }`}
              >
                {resourceBlocked && !switchDisabled
                  ? t("packages.planNotSelectableCta")
                  : paidCtaLabel(plan.code, isScheduledHere, samePlanAndCycle, isCurrent, pending, t)}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function Badge({ children, className }: { children: string; className: string }) {
  return <span className={`text-xs font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ${className}`}>{children}</span>;
}
