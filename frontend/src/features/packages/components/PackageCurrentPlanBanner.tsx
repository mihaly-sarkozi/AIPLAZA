import { tPlanBillingParen, type BillingPeriod } from "./packageUtils";

type PackageCurrentPlanBannerProps = {
  currentPlanName: string;
  currentPlanCode: string;
  currentBillingPeriod: BillingPeriod;
  bannerValidityDate: string | null;
  scheduledPlanCode: string | null;
  scheduledPlanName: string | null;
  scheduledBillingPeriod: BillingPeriod;
  selectedBillingPeriod: BillingPeriod;
  t: (key: string) => string;
  onSelectBillingPeriod: (period: BillingPeriod) => void;
};

export default function PackageCurrentPlanBanner({
  currentPlanName,
  currentPlanCode,
  currentBillingPeriod,
  bannerValidityDate,
  scheduledPlanCode,
  scheduledPlanName,
  scheduledBillingPeriod,
  selectedBillingPeriod,
  t,
  onSelectBillingPeriod,
}: PackageCurrentPlanBannerProps) {
  return (
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
        <div role="group" aria-label={t("packages.billingLabel")} className="flex w-full flex-wrap gap-2 md:w-auto">
          <SegmentButton period="monthly" label={t("packages.segmentMonthly")} selected={selectedBillingPeriod} onSelect={onSelectBillingPeriod} />
          <SegmentButton period="quarterly" label={t("packages.segmentQuarterly")} badge={t("packages.segmentSaveQuarterly")} selected={selectedBillingPeriod} onSelect={onSelectBillingPeriod} />
          <SegmentButton period="yearly" label={t("packages.segmentYearly")} badge={t("packages.segmentSaveYearly")} selected={selectedBillingPeriod} onSelect={onSelectBillingPeriod} />
        </div>
      </div>
    </div>
  );
}

function SegmentButton({
  period,
  label,
  badge,
  selected,
  onSelect,
}: {
  period: BillingPeriod;
  label: string;
  badge?: string | null;
  selected: BillingPeriod;
  onSelect: (period: BillingPeriod) => void;
}) {
  const active = selected === period;
  return (
    <button
      type="button"
      onClick={() => onSelect(period)}
      className={`min-w-[96px] rounded-lg px-4 py-2.5 text-sm font-semibold transition ${
        active
          ? "bg-[var(--color-card-muted)] text-[var(--color-foreground)] border border-[var(--color-border)] shadow-sm"
          : "bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
      }`}
    >
      <span className="flex items-center justify-center gap-1.5 leading-tight text-center">
        <span>{label}</span>
        {badge ? <span className="text-xs font-semibold tabular-nums text-current">{badge}</span> : null}
      </span>
    </button>
  );
}
