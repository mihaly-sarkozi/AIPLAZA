import { Link } from "react-router-dom";

import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../../api/services/settingsService";
import { useTranslation } from "../../../../i18n";
import { formatDateTime } from "../../../../utils/dateTimeFormatting";
import type { ProcessingStepRow } from "../../utils/processingMonitorUtils";
import { formatDurationMs } from "../../utils/processingMonitorUtils";
import ProcessingStatusBadge from "./ProcessingStatusBadge";

type ProcessingStepsTableProps = {
  kbUuid: string;
  itemId: string;
  steps: ProcessingStepRow[];
  locale: string;
  timezone?: SettingsTimezone | string;
  dateFormat?: SettingsDateFormat;
  timeFormat?: SettingsTimeFormat;
};

function translateKey(t: (key: string) => string, prefix: string, value: string): string {
  const translated = t(`${prefix}.${value}`);
  if (translated !== `${prefix}.${value}`) return translated;
  return value.replace(/_/g, " ");
}

export default function ProcessingStepsTable({
  kbUuid,
  itemId,
  steps,
  locale,
  timezone,
  dateFormat,
  timeFormat,
}: ProcessingStepsTableProps) {
  const { t } = useTranslation();

  if (!steps.length) {
    return <p className="text-sm text-[var(--color-muted)]">{t("kb.processingMonitor.emptySteps")}</p>;
  }

  return (
    <div className="app-table-wrap">
      <div className="app-table-head hidden grid-cols-[1.2fr_1.2fr_0.8fr_0.8fr_1fr_2rem] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid">
        <div>{t("kb.processingMonitor.table.module")}</div>
        <div>{t("kb.processingMonitor.table.step")}</div>
        <div>{t("kb.processingMonitor.table.status")}</div>
        <div>{t("kb.processingMonitor.table.duration")}</div>
        <div>{t("kb.processingMonitor.table.time")}</div>
        <div className="sr-only">{t("kb.processingMonitor.table.details")}</div>
      </div>
      <div className="divide-y divide-[var(--color-border)]">
        {steps.map((step) => {
          const detailUrl = `/kb/monitor/${kbUuid}/flows/${encodeURIComponent(itemId)}/steps/${encodeURIComponent(step.module)}/${encodeURIComponent(step.step)}`;
          return (
            <Link
              key={step.key}
              to={detailUrl}
              className="grid grid-cols-1 gap-2 px-5 py-4 transition hover:bg-[var(--color-card-muted)]/50 md:grid-cols-[1.2fr_1.2fr_0.8fr_0.8fr_1fr_2rem] md:items-center md:gap-4"
            >
              <div>
                <p className="text-sm font-medium text-[var(--color-foreground)]">
                  {translateKey(t, "kb.processingMonitor.modules", step.module)}
                </p>
                <p className="text-xs text-[var(--color-muted)]">{translateKey(t, "kb.processingMonitor.stages", step.stage)}</p>
              </div>
              <div className="text-sm text-[var(--color-foreground)]">
                {translateKey(t, "kb.processingMonitor.steps", step.step)}
              </div>
              <div>
                <ProcessingStatusBadge
                  status={step.status}
                  label={translateKey(t, "kb.processingMonitor.statuses", step.status)}
                />
              </div>
              <div className="text-sm text-[var(--color-muted)]">{formatDurationMs(step.durationMs, t)}</div>
              <div className="text-sm text-[var(--color-muted)]">
                {formatDateTime(step.createdAt, { locale, timezone, dateFormat, timeFormat })}
              </div>
              <div className="text-[var(--color-primary)] md:text-right">→</div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
