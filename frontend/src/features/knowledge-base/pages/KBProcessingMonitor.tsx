import { useEffect, useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { formatDateTime } from "../../../utils/dateTimeFormatting";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import ProcessingMonitorLiveBanner from "../components/monitor/ProcessingMonitorLiveBanner";
import ProcessingMonitorBreadcrumb from "../components/monitor/ProcessingMonitorBreadcrumb";
import ProcessingStatusBadge from "../components/monitor/ProcessingStatusBadge";
import { useProcessingMonitorBundle } from "../hooks/useProcessingMonitorBundle";
import { useMonitorRouteRefetch } from "../hooks/useMonitorRouteRefetch";
import { useProgressClock } from "../hooks/useProgressClock";
import { useKbList } from "../hooks/useKb";
import {
  buildFlowSummaries,
  countOpenBlockingIssues,
  deriveFlowProgress,
  resolveFlowItemId,
  translateProcessingMonitorKey,
} from "../utils/processingMonitorUtils";
import { countActiveFlows } from "../utils/processingMonitorPolling";

export default function KBProcessingMonitor() {
  const { uuid } = useParams();
  const navigate = useNavigate();
  const { t, locale } = useTranslation();
  const { data: settings } = useLocaleSettings();
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const kb = useMemo(() => kbList.find((item) => item.uuid === uuid), [kbList, uuid]);

  useEffect(() => {
    if (kbLoading) return;
    if (!uuid || !kb) {
      navigate("/kb", { replace: true });
    }
  }, [kb, kbLoading, navigate, uuid]);

  const { runsQuery, eventsQuery, issuesQuery, metricsQuery, isLive } = useProcessingMonitorBundle(uuid);
  useMonitorRouteRefetch(uuid);
  const progressNowMs = useProgressClock(isLive);

  const flows = useMemo(() => {
    const runs = runsQuery.data?.items ?? [];
    const events = eventsQuery.data?.items ?? [];
    const issues = issuesQuery.data?.items ?? [];
    return buildFlowSummaries(runs, events, issues, { nowMs: progressNowMs });
  }, [eventsQuery.data?.items, issuesQuery.data?.items, progressNowMs, runsQuery.data?.items]);

  const activeFlowCount = useMemo(
    () => countActiveFlows(runsQuery.data?.items ?? [], eventsQuery.data?.items ?? []),
    [runsQuery.data?.items, eventsQuery.data?.items],
  );

  const primaryActiveFlow = useMemo(
    () => flows.find((flow) => flow.status === "running") ?? null,
    [flows],
  );

  const primaryFlowProgress = useMemo(() => {
    if (!primaryActiveFlow) return null;
    const allEvents = eventsQuery.data?.items ?? [];
    const itemEvents = allEvents.filter(
      (event) => resolveFlowItemId(event) === primaryActiveFlow.itemId,
    );
    return deriveFlowProgress(itemEvents, issuesQuery.data?.items ?? [], [], {
      referenceEvents: allEvents,
      currentItemId: primaryActiveFlow.itemId,
      nowMs: progressNowMs,
    });
  }, [primaryActiveFlow, eventsQuery.data?.items, issuesQuery.data?.items, progressNowMs]);

  const blockingIssueCount = useMemo(
    () => countOpenBlockingIssues(issuesQuery.data?.items ?? []),
    [issuesQuery.data?.items],
  );

  const error =
    runsQuery.error || eventsQuery.error || issuesQuery.error
      ? getApiErrorMessage(runsQuery.error ?? eventsQuery.error ?? issuesQuery.error)
      : null;
  const loading = runsQuery.isLoading || eventsQuery.isLoading;

  return (
    <div className="app-page">
      <div className="app-page-container">
        <ProcessingMonitorBreadcrumb
          crumbs={[
            { label: t("kb.title"), to: "/kb" },
            { label: kb?.name ?? t("kb.processingMonitor.title") },
          ]}
        />
        <PageHeader
          eyebrow={t("kb.processingMonitor.eyebrow")}
          title={kb?.name ?? t("kb.processingMonitor.title")}
          description={t("kb.processingMonitor.intro")}
          actions={
            <Button variant="secondary" onClick={() => navigate("/kb")}>
              {t("kb.processingMonitor.backToList")}
            </Button>
          }
        />

        <ProcessingMonitorLiveBanner
          isLive={isLive}
          activeFlowCount={activeFlowCount}
          activeFlow={primaryActiveFlow}
          progress={primaryFlowProgress}
        />

        {error ? <Alert tone="error">{error}</Alert> : null}

        <section className="mb-6 grid grid-cols-2 gap-3 rounded-2xl bg-[var(--color-card-muted)]/60 px-4 py-3 md:grid-cols-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.metrics.flows")}</p>
            <p className="text-lg font-semibold">{flows.length}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.metrics.chunks")}</p>
            <p className="text-lg font-semibold">{metricsQuery.data?.chunks_total ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.metrics.openIssues")}</p>
            <p className="text-lg font-semibold">{blockingIssueCount}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{t("kb.processingMonitor.metrics.failedDocs")}</p>
            <p className="text-lg font-semibold">{metricsQuery.data?.documents_failed ?? "—"}</p>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold text-[var(--color-foreground)]">{t("kb.processingMonitor.flowListTitle")}</h2>
          {loading ? <p className="text-sm text-[var(--color-muted)]">{t("common.loading")}</p> : null}
          {!loading && !flows.length ? <Alert tone="info">{t("kb.processingMonitor.emptyFlows")}</Alert> : null}
          {flows.length ? (
            <div className="app-table-wrap">
              <div className="app-table-head hidden grid-cols-[1.6fr_0.8fr_0.8fr_0.7fr_0.7fr_1fr_2rem] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid">
                <div>{t("kb.processingMonitor.table.document")}</div>
                <div>{t("kb.processingMonitor.table.type")}</div>
                <div>{t("kb.processingMonitor.table.status")}</div>
                <div>{t("kb.processingMonitor.table.steps")}</div>
                <div>{t("kb.processingMonitor.table.issues")}</div>
                <div>{t("kb.processingMonitor.table.lastRun")}</div>
                <div className="sr-only">{t("kb.processingMonitor.table.details")}</div>
              </div>
              <div className="divide-y divide-[var(--color-border)]">
                {flows.map((flow) => {
                  const detailUrl = `/kb/monitor/${uuid}/flows/${encodeURIComponent(flow.itemId)}`;
                  const progressLabel =
                    flow.status === "running" && flow.progressPercent != null
                      ? t("kb.processingMonitor.percentComplete").replace(
                          "{{percent}}",
                          String(flow.progressPercent),
                        )
                      : flow.status !== "completed" && flow.activeModule && flow.activeStep
                        ? [
                            translateProcessingMonitorKey(t, flow.activeModule, "module"),
                            translateProcessingMonitorKey(t, flow.activeStep, "stepOrStage"),
                          ]
                            .filter(Boolean)
                            .join(" · ")
                        : null;
                  return (
                    <Link
                      key={flow.itemId}
                      to={detailUrl}
                      className="grid grid-cols-1 gap-2 px-5 py-4 transition hover:bg-[var(--color-card-muted)]/50 md:grid-cols-[1.6fr_0.8fr_0.8fr_0.7fr_0.7fr_1fr_2rem] md:items-center md:gap-4"
                    >
                      <div>
                        <p className="font-medium text-[var(--color-foreground)]">{flow.title}</p>
                        {progressLabel ? (
                          <p className="mt-1 text-xs font-medium text-sky-800">{progressLabel}</p>
                        ) : null}
                        {flow.latestMessage && !progressLabel ? (
                          <p className="mt-1 line-clamp-2 text-xs text-[var(--color-muted)]">{flow.latestMessage}</p>
                        ) : null}
                      </div>
                      <div className="text-sm text-[var(--color-muted)]">
                        {translateProcessingMonitorKey(t, flow.inputType, "inputType")}
                      </div>
                      <div>
                        <ProcessingStatusBadge
                          status={flow.status}
                          label={translateProcessingMonitorKey(t, flow.status, "flowStatus")}
                        />
                      </div>
                      <div className="text-sm text-[var(--color-muted)]">
                        {flow.progressTotalSteps != null && flow.status === "running"
                          ? `${flow.completedSteps}/${flow.progressTotalSteps}`
                          : `${flow.completedSteps}/${flow.completedSteps + flow.failedSteps || flow.completedSteps}`}
                      </div>
                      <div className="text-sm text-[var(--color-muted)]">{flow.openIssues}</div>
                      <div className="text-sm text-[var(--color-muted)]">
                        {flow.lastEventAt
                          ? formatDateTime(flow.lastEventAt, {
                              locale,
                              timezone: settings?.timezone,
                              dateFormat: settings?.date_format,
                              timeFormat: settings?.time_format,
                            })
                          : "—"}
                      </div>
                      <div className="text-[var(--color-primary)] md:text-right">→</div>
                    </Link>
                  );
                })}
              </div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
