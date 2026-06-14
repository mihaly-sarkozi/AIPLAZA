import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { formatDateTime } from "../../../utils/dateTimeFormatting";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import ProcessingStepSummaryPanel from "../components/monitor/ProcessingStepSummaryPanel";
import ProcessingMonitorBreadcrumb from "../components/monitor/ProcessingMonitorBreadcrumb";
import ProcessingStatusBadge from "../components/monitor/ProcessingStatusBadge";
import { useProcessingMonitorBundle } from "../hooks/useProcessingMonitorBundle";
import { useKbList } from "../hooks/useKb";
import {
  buildItemCatalogFromRuns,
  buildPipelineTimelineCompact,
  findStepRow,
  formatDurationMs,
  translateProcessingMonitorKey,
} from "../utils/processingMonitorUtils";
import { buildStepSummaryDisplay } from "../utils/stepSummaryDisplay";

export default function KBProcessingStepDetail() {
  const { uuid, itemId: rawItemId, module: rawModule, step: rawStep } = useParams();
  const itemId = rawItemId ? decodeURIComponent(rawItemId) : undefined;
  const module = rawModule ? decodeURIComponent(rawModule) : undefined;
  const step = rawStep ? decodeURIComponent(rawStep) : undefined;
  const navigate = useNavigate();
  const { t, locale } = useTranslation();
  const { data: settings } = useLocaleSettings();
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const kb = useMemo(() => kbList.find((item) => item.uuid === uuid), [kbList, uuid]);

  const { runsQuery, eventsQuery, understandingQuery } = useProcessingMonitorBundle(uuid, {
    trainingItemId: itemId,
  });

  useEffect(() => {
    if (kbLoading) return;
    if (!uuid) navigate("/kb", { replace: true });
  }, [kbLoading, navigate, uuid]);

  const catalog = useMemo(() => buildItemCatalogFromRuns(runsQuery.data?.items ?? []), [runsQuery.data?.items]);
  const title = itemId ? (catalog.get(itemId)?.title ?? itemId) : t("kb.processingMonitor.unknownDocument");

  const stepRow = useMemo(() => {
    if (!module || !step) return null;
    const timeline = buildPipelineTimelineCompact(
      eventsQuery.data?.items ?? [],
      understandingQuery.data?.steps ?? [],
    );
    const fromTimeline = timeline.find((row) => row.module === module && row.step === step && !row.isPending);
    if (fromTimeline) return fromTimeline;
    const fromEvents = findStepRow(eventsQuery.data?.items ?? [], module, step);
    return fromEvents;
  }, [eventsQuery.data?.items, module, step, understandingQuery.data?.steps]);

  const inputDisplay = useMemo(
    () => buildStepSummaryDisplay(step, stepRow?.inputSummary ?? {}, "input", t, locale),
    [locale, step, stepRow, t],
  );
  const outputDisplay = useMemo(
    () => buildStepSummaryDisplay(step, stepRow?.outputSummary ?? {}, "output", t, locale),
    [locale, step, stepRow, t],
  );

  const error = eventsQuery.error || understandingQuery.error ? getApiErrorMessage(eventsQuery.error ?? understandingQuery.error) : null;
  const monitorUrl = `/kb/monitor/${uuid}`;
  const flowUrl = itemId ? `/kb/monitor/${uuid}/flows/${encodeURIComponent(itemId)}` : monitorUrl;

  return (
    <div className="app-page">
      <div className="app-page-container">
        <ProcessingMonitorBreadcrumb
          crumbs={[
            { label: t("kb.title"), to: "/kb" },
            { label: kb?.name ?? t("kb.processingMonitor.title"), to: monitorUrl },
            { label: title, to: flowUrl },
            { label: step ? translateProcessingMonitorKey(t, step, "step") : t("kb.processingMonitor.stepDetail") },
          ]}
        />
        <PageHeader
          eyebrow={t("kb.processingMonitor.stepDetailEyebrow")}
          title={step ? translateProcessingMonitorKey(t, step, "step") : t("kb.processingMonitor.stepDetail")}
          description={t("kb.processingMonitor.stepDetailIntro")}
          actions={
            <Button variant="secondary" onClick={() => navigate(flowUrl)}>
              {t("kb.processingMonitor.backToFlow")}
            </Button>
          }
        />

        {error ? <Alert tone="error">{error}</Alert> : null}
        {!stepRow && !eventsQuery.isLoading ? <Alert tone="info">{t("kb.processingMonitor.stepNotFound")}</Alert> : null}

        {stepRow ? (
          <>
            <section className="mb-6 grid gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 md:grid-cols-4">
              <div>
                <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.table.module")}</p>
                <p className="mt-1 text-sm font-medium">{translateProcessingMonitorKey(t, stepRow.module, "module")}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.table.status")}</p>
                <p className="mt-1">
                  <ProcessingStatusBadge
                    status={stepRow.status}
                    label={translateProcessingMonitorKey(t, stepRow.status, "status")}
                  />
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.table.duration")}</p>
                <p className="mt-1 text-sm font-medium">{formatDurationMs(stepRow.durationMs, t)}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.table.time")}</p>
                <p className="mt-1 text-sm font-medium">
                  {formatDateTime(stepRow.createdAt, {
                    locale,
                    timezone: settings?.timezone,
                    dateFormat: settings?.date_format,
                    timeFormat: settings?.time_format,
                  })}
                </p>
              </div>
              {stepRow.message ? (
                <div className="md:col-span-4">
                  <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.message")}</p>
                  <p className="mt-1 text-sm text-red-700">{stepRow.message}</p>
                </div>
              ) : null}
              {stepRow.errorCode ? (
                <div className="md:col-span-4">
                  <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.errorCode")}</p>
                  <p className="mt-1 text-sm">{translateProcessingMonitorKey(t, stepRow.errorCode, "issue")}</p>
                </div>
              ) : null}
            </section>

            <div className="grid gap-4 lg:grid-cols-2">
              <ProcessingStepSummaryPanel
                title={t("kb.processingMonitor.inputTitle")}
                display={inputDisplay}
                emptyLabel={t("kb.processingMonitor.emptyInput")}
              />
              <ProcessingStepSummaryPanel
                title={t("kb.processingMonitor.outputTitle")}
                display={outputDisplay}
                emptyLabel={t("kb.processingMonitor.emptyOutput")}
              />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
