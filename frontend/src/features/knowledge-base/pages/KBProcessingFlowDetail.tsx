import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { formatDateTime } from "../../../utils/dateTimeFormatting";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import ProcessingKeyValueTable from "../components/monitor/ProcessingKeyValueTable";
import ProcessingMonitorLiveBanner from "../components/monitor/ProcessingMonitorLiveBanner";
import ProcessingMonitorBreadcrumb from "../components/monitor/ProcessingMonitorBreadcrumb";
import ProcessingStatusBadge from "../components/monitor/ProcessingStatusBadge";
import ProcessingStepsTable from "../components/monitor/ProcessingStepsTable";
import { useProcessingMonitorBundle } from "../hooks/useProcessingMonitorBundle";
import { useMonitorRouteRefetch } from "../hooks/useMonitorRouteRefetch";
import { useProgressClock } from "../hooks/useProgressClock";
import { useKbList } from "../hooks/useKb";
import {
  buildItemCatalogFromRuns,
  buildPipelineTimelineCompact,
  deriveActiveProgress,
  deriveFlowProcessingDisplay,
  deriveFlowProgress,
  translateProcessingMonitorKey,
} from "../utils/processingMonitorUtils";

export default function KBProcessingFlowDetail() {
  const { uuid, itemId: rawItemId } = useParams();
  const itemId = rawItemId ? decodeURIComponent(rawItemId) : undefined;
  const navigate = useNavigate();
  const { t, locale } = useTranslation();
  const { data: settings } = useLocaleSettings();
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const kb = useMemo(() => kbList.find((item) => item.uuid === uuid), [kbList, uuid]);

  const { runsQuery, eventsQuery, referenceEventsQuery, issuesQuery, understandingQuery, isLive } =
    useProcessingMonitorBundle(uuid, { trainingItemId: itemId });
  useMonitorRouteRefetch(uuid);
  const progressNowMs = useProgressClock(isLive);

  useEffect(() => {
    if (kbLoading) return;
    if (!uuid) navigate("/kb", { replace: true });
  }, [kbLoading, navigate, uuid]);

  const catalog = useMemo(() => buildItemCatalogFromRuns(runsQuery.data?.items ?? []), [runsQuery.data?.items]);
  const meta = itemId ? catalog.get(itemId) : undefined;
  const title = meta?.title ?? itemId ?? t("kb.processingMonitor.unknownDocument");

  const steps = useMemo(
    () => buildPipelineTimelineCompact(eventsQuery.data?.items ?? [], understandingQuery.data?.steps ?? []),
    [eventsQuery.data?.items, understandingQuery.data?.steps],
  );

  const job = understandingQuery.data?.job;

  const activeProgress = useMemo(
    () => deriveActiveProgress(eventsQuery.data?.items ?? []),
    [eventsQuery.data?.items],
  );

  const flowProgress = useMemo(
    () =>
      deriveFlowProgress(
        eventsQuery.data?.items ?? [],
        issuesQuery.data?.items ?? [],
        understandingQuery.data?.steps ?? [],
        {
          referenceEvents: referenceEventsQuery.data?.items ?? eventsQuery.data?.items ?? [],
          currentItemId: itemId ?? null,
          nowMs: progressNowMs,
        },
      ),
    [
      eventsQuery.data?.items,
      issuesQuery.data?.items,
      understandingQuery.data?.steps,
      referenceEventsQuery.data?.items,
      itemId,
      progressNowMs,
    ],
  );

  const processingDisplay = useMemo(
    () =>
      deriveFlowProcessingDisplay(
        eventsQuery.data?.items ?? [],
        issuesQuery.data?.items ?? [],
        job?.status,
      ),
    [eventsQuery.data?.items, issuesQuery.data?.items, job?.status],
  );

  const chunkSummaryRows = useMemo(() => {
    const chunkCount = understandingQuery.data?.chunk_count;
    if (chunkCount == null) return [];
    return [
      {
        key: "chunk_count",
        labelKey: "chunk_count",
        value: String(chunkCount),
        group: "output" as const,
      },
    ];
  }, [understandingQuery.data?.chunk_count]);

  const error =
    eventsQuery.error || issuesQuery.error || understandingQuery.error
      ? getApiErrorMessage(eventsQuery.error ?? issuesQuery.error ?? understandingQuery.error)
      : null;

  const monitorUrl = `/kb/monitor/${uuid}`;

  return (
    <div className="app-page">
      <div className="app-page-container">
        <ProcessingMonitorBreadcrumb
          crumbs={[
            { label: t("kb.title"), to: "/kb" },
            { label: kb?.name ?? t("kb.processingMonitor.title"), to: monitorUrl },
            { label: title },
          ]}
        />
        <PageHeader
          eyebrow={t("kb.processingMonitor.flowDetailEyebrow")}
          title={title}
          description={t("kb.processingMonitor.flowDetailIntro")}
          actions={
            <Button variant="secondary" onClick={() => navigate(monitorUrl)}>
              {t("kb.processingMonitor.backToMonitor")}
            </Button>
          }
        />

        <ProcessingMonitorLiveBanner
          isLive={isLive}
          activeFlow={
            activeProgress
              ? {
                  activeModule: activeProgress.module,
                  activeStage: activeProgress.stage,
                  activeStep: activeProgress.step,
                  latestMessage: activeProgress.message,
                }
              : null
          }
          progress={flowProgress}
        />

        {error ? <Alert tone="error">{error}</Alert> : null}

        <section className="mb-6 grid gap-3 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 md:grid-cols-3">
          {flowProgress ? (
            <div className="md:col-span-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
                  {t("kb.processingMonitor.overallProgress")}
                </p>
                <p className="text-sm font-semibold text-[var(--color-foreground)]">
                  {t("kb.processingMonitor.percentComplete").replace("{{percent}}", String(flowProgress.percent))}
                </p>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[var(--color-card-muted)]">
                <div
                  className="h-full rounded-full bg-sky-600 transition-[width] duration-500 ease-out"
                  style={{ width: `${Math.max(flowProgress.percent, 2)}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-[var(--color-muted)]">
                {t("kb.processingMonitor.pipelineProgress")
                  .replace("{{completed}}", String(flowProgress.completedSteps))
                  .replace("{{total}}", String(flowProgress.totalSteps))}
                {flowProgress.batchTotal != null && flowProgress.batchDone != null
                  ? ` · ${t("kb.processingMonitor.batchProgress")
                      .replace("{{done}}", String(flowProgress.batchDone))
                      .replace("{{total}}", String(flowProgress.batchTotal))}`
                  : ""}
              </p>
            </div>
          ) : null}
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.table.type")}</p>
            <p className="mt-1 text-sm font-medium">{translateProcessingMonitorKey(t, meta?.inputType ?? "unknown", "inputType")}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.jobStatus")}</p>
            <div className="mt-1">
              <ProcessingStatusBadge
                status={processingDisplay.badgeStatus}
                label={translateProcessingMonitorKey(t, processingDisplay.flowStatus, "flowStatus")}
              />
              {processingDisplay.flowStatus !== "completed" &&
              processingDisplay.module &&
              processingDisplay.step ? (
                <p className="mt-1 text-sm font-medium text-[var(--color-foreground)]">
                  {translateProcessingMonitorKey(t, processingDisplay.module, "module")}
                  {" · "}
                  {translateProcessingMonitorKey(t, processingDisplay.step, "stepOrStage")}
                </p>
              ) : processingDisplay.flowStatus !== "completed" &&
                processingDisplay.source === "job" &&
                job?.status ? (
                <p className="mt-1 text-sm text-[var(--color-muted)]">
                  {translateProcessingMonitorKey(t, job.status, "jobStatus")}
                </p>
              ) : null}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.chunkCount")}</p>
            <p className="mt-1 text-sm font-medium">{understandingQuery.data?.chunk_count ?? "—"}</p>
          </div>
          {job?.error_message ? (
            <div className="md:col-span-3">
              <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.lastError")}</p>
              <p className="mt-1 text-sm text-red-700">{job.error_message}</p>
            </div>
          ) : null}
          {job?.completed_at ? (
            <div>
              <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.completedAt")}</p>
              <p className="mt-1 text-sm">
                {formatDateTime(job.completed_at, {
                  locale,
                  timezone: settings?.timezone,
                  dateFormat: settings?.date_format,
                  timeFormat: settings?.time_format,
                })}
              </p>
            </div>
          ) : null}
        </section>

        <section className="mb-6">
          <h2 className="mb-3 text-lg font-semibold">{t("kb.processingMonitor.stepsTitle")}</h2>
          {uuid && itemId ? (
            <ProcessingStepsTable
              kbUuid={uuid}
              itemId={itemId}
              steps={steps}
              issues={issuesQuery.data?.items ?? []}
              locale={locale}
              timezone={settings?.timezone}
              dateFormat={settings?.date_format}
              timeFormat={settings?.time_format}
            />
          ) : null}
        </section>

        {chunkSummaryRows.length ? (
          <ProcessingKeyValueTable
            title={t("kb.processingMonitor.chunkDataTitle")}
            rows={chunkSummaryRows}
            emptyLabel={t("kb.processingMonitor.emptyChunkData")}
          />
        ) : null}
      </div>
    </div>
  );
}
