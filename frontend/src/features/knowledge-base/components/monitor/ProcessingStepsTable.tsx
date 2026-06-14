import { Link } from "react-router-dom";

import type { ProcessingIssueSummary } from "../../../../api/services/kb/kbProcessingApi";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../api/services/settingsService";
import { useTranslation } from "../../../../i18n";
import { formatDateTime } from "../../../../utils/dateTimeFormatting";
import type { ProcessingStepRow } from "../../utils/processingMonitorUtils";
import {
  formatDurationMs,
  getOpenIssuesForStep,
  translateProcessingMonitorKey,
} from "../../utils/processingMonitorUtils";
import ProcessingStatusBadge from "./ProcessingStatusBadge";
import ProcessingStepIssueHint from "./ProcessingStepIssueHint";

type ProcessingStepsTableProps = {
  kbUuid: string;
  itemId: string;
  steps: ProcessingStepRow[];
  issues?: ProcessingIssueSummary[];
  locale: string;
  timezone?: SettingsTimezone | string;
  dateFormat?: SettingsDateFormat;
  timeFormat?: SettingsTimeFormat;
};

function stageSubtitle(
  t: (key: string) => string,
  step: ProcessingStepRow,
): string | null {
  const moduleLabel = translateProcessingMonitorKey(t, step.module, "module");
  const stageLabel = translateProcessingMonitorKey(t, step.stage, "stage");
  const stepLabel = translateProcessingMonitorKey(t, step.step, "step");
  if (!stageLabel || stageLabel === moduleLabel || stageLabel === stepLabel) {
    return null;
  }
  return stageLabel;
}

function displayStatus(step: ProcessingStepRow, stepIssues: ProcessingIssueSummary[]): string {
  if (step.isPending) return "pending";
  return step.status;
}

function statusLabel(
  t: (key: string) => string,
  step: ProcessingStepRow,
  stepIssues: ProcessingIssueSummary[],
): string {
  const status = displayStatus(step, stepIssues);
  if (status === "completed" && stepIssues.length === 0) {
    return t("kb.processingMonitor.stepCompletedOk");
  }
  return translateProcessingMonitorKey(t, status, "status");
}

export default function ProcessingStepsTable({
  kbUuid,
  itemId,
  steps,
  issues = [],
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
      <div className="app-table-head hidden grid-cols-[1.1fr_1.3fr_1fr_0.8fr_1fr_2rem] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid">
        <div>{t("kb.processingMonitor.table.module")}</div>
        <div>{t("kb.processingMonitor.table.step")}</div>
        <div>{t("kb.processingMonitor.table.status")}</div>
        <div>{t("kb.processingMonitor.table.duration")}</div>
        <div>{t("kb.processingMonitor.table.time")}</div>
        <div className="sr-only">{t("kb.processingMonitor.table.details")}</div>
      </div>
      <div className="divide-y divide-[var(--color-border)]">
        {steps.map((step, index) => {
          const detailUrl = `/kb/monitor/${kbUuid}/flows/${encodeURIComponent(itemId)}/steps/${encodeURIComponent(step.module)}/${encodeURIComponent(step.step)}`;
          const moduleLabel = translateProcessingMonitorKey(t, step.module, "module");
          const stepLabel = translateProcessingMonitorKey(t, step.step, "step");
          const subtitle = stageSubtitle(t, step);
          const prevModule = index > 0 ? steps[index - 1].module : null;
          const isNewModule = step.module !== prevModule;
          const stepIssues = getOpenIssuesForStep(issues, step);
          const rowClass = [
            "grid grid-cols-1 gap-2 px-5 py-4 md:grid-cols-[1.1fr_1.3fr_1fr_0.8fr_1fr_2rem] md:items-center md:gap-4",
            step.isPending ? "bg-[var(--color-card-muted)]/30 opacity-80" : "transition hover:bg-[var(--color-card-muted)]/50",
            isNewModule && index > 0 ? "border-t-2 border-[var(--color-border)]" : "",
          ]
            .filter(Boolean)
            .join(" ");

          const content = (
            <>
              <div>
                <p className="text-sm font-medium text-[var(--color-foreground)]">{moduleLabel}</p>
                {subtitle ? <p className="text-xs text-[var(--color-muted)]">{subtitle}</p> : null}
              </div>
              <div className="text-sm text-[var(--color-foreground)]">{stepLabel}</div>
              <div className="flex items-center gap-2">
                <ProcessingStatusBadge
                  status={displayStatus(step, stepIssues)}
                  label={statusLabel(t, step, stepIssues)}
                />
                {stepIssues.length ? <ProcessingStepIssueHint issues={stepIssues} t={t} /> : null}
              </div>
              <div className="text-sm text-[var(--color-muted)]">{formatDurationMs(step.durationMs, t)}</div>
              <div className="text-sm text-[var(--color-muted)]">
                {step.createdAt
                  ? formatDateTime(step.createdAt, { locale, timezone, dateFormat, timeFormat })
                  : "—"}
              </div>
              <div className="text-[var(--color-primary)] md:text-right">{step.isPending ? "" : "→"}</div>
            </>
          );

          if (step.isPending) {
            return (
              <div key={step.key} className={rowClass} aria-disabled="true">
                {content}
              </div>
            );
          }

          return (
            <Link key={step.key} to={detailUrl} className={rowClass}>
              {content}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
