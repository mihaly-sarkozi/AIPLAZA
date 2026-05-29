import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import api from "../../../api/axiosClient";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { queryKeys } from "../../../queryKeys";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import {
  useInfiniteIngestRuns,
  useKbList,
  type KbItem,
} from "../hooks/useKb";
import {
  ACTIVE_RUN_STATUSES,
  buildTrainingRows,
  formatInteger,
  formatTimestamp,
  getItemProcessingPreview,
  getRunProcessingPreview,
  getStatusBadgeClass,
  getStatusLabel,
} from "./ingestLogHelpers";

function filenameFromContentDisposition(value: string | undefined): string | null {
  if (!value) return null;
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(value);
  if (encoded?.[1]) return decodeURIComponent(encoded[1]);
  const plain = /filename="?([^";]+)"?/i.exec(value);
  return plain?.[1] ?? null;
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export default function KBIngest() {
  const { t, locale } = useTranslation();
  const { uuid } = useParams();
  const navigate = useNavigate();
  const { data: settings } = useLocaleSettings();
  const queryClient = useQueryClient();
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const [downloadSourceId, setDownloadSourceId] = useState<string | null>(null);
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const kb = useMemo(() => kbList.find((item) => item.uuid === uuid), [kbList, uuid]);

  const runsQuery = useInfiniteIngestRuns(uuid, {
    refetchInterval: ({ state }) => {
      const runs = state.data?.pages.flatMap((page) => page.items) ?? [];
      return runs.some((run) => ACTIVE_RUN_STATUSES.has(run.status)) ? 2000 : 5000;
    },
  });

  useEffect(() => {
    if (kbLoading) return;
    if (!uuid || !kb) {
      navigate("/kb", { replace: true });
    }
  }, [kb, kbLoading, navigate, uuid]);

  const listError = runsQuery.error ? getApiErrorMessage(runsQuery.error) : null;
  const runs = useMemo(() => runsQuery.data?.pages.flatMap((page) => page.items) ?? [], [runsQuery.data]);
  const latestPage = runsQuery.data?.pages[0];
  const trainingKindLabels = useMemo(
    () => ({
      file: t("kb.trainLogTypeFile"),
      text: t("kb.trainLogTypeText"),
      url: t("kb.trainLogTypeUrl"),
      unknown: t("kb.trainLogTypeUnknown"),
    }),
    [t]
  );
  const rows = useMemo(() => buildTrainingRows(runs, trainingKindLabels), [runs, trainingKindLabels]);
  const processingPreviewLabels = useMemo(
    () => ({
      noData: t("kb.trainLogProcessingNoData"),
      processed: t("kb.trainLogProcessingProcessed"),
      sentence: t("kb.trainLogProcessingSentence"),
      character: t("kb.trainLogProcessingCharacter"),
    }),
    [t]
  );
  const activeRunCount = runs.filter((run) => ACTIVE_RUN_STATUSES.has(run.status)).length;
  const summary = latestPage?.summary;

  useEffect(() => {
    if (!uuid || !summary) return;
    const trainingCharCount = Number(summary.total_char_count ?? 0);
    if (!Number.isFinite(trainingCharCount)) return;
    queryClient.setQueryData<KbItem[]>(queryKeys.kb, (previous) => {
      if (!previous) return previous;
      return previous.map((item) =>
        item.uuid === uuid
          ? {
              ...item,
              storage_metrics: {
                ...(item.storage_metrics ?? {}),
                training_char_count: Math.max(0, trainingCharCount),
              },
            }
          : item
      );
    });
  }, [queryClient, summary, summary?.total_char_count, uuid]);

  const navigateToKbList = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.kb });
    navigate("/kb");
  };

  const downloadTrainingMaterial = async (sourceId: string | null, fallbackName: string) => {
    if (!sourceId) {
      toast.error(t("kb.trainLogDownloadUnavailable"));
      return;
    }
    setDownloadSourceId(sourceId);
    try {
      const response = await api.get(`/knowledge/sources/${encodeURIComponent(sourceId)}/download`, {
        responseType: "blob",
      });
      const filename = filenameFromContentDisposition(response.headers["content-disposition"]) || fallbackName || sourceId;
      downloadBlob(filename, response.data);
    } catch {
      toast.error(t("kb.trainLogDownloadError"));
    } finally {
      setDownloadSourceId(null);
    }
  };

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting) && runsQuery.hasNextPage && !runsQuery.isFetchingNextPage) {
          runsQuery.fetchNextPage();
        }
      },
      { rootMargin: "320px" }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [runsQuery]);

  return (
    <div className="app-page">
      <div className="app-page-container">
        <PageHeader
          eyebrow={t("kb.trainLogTitle")}
          title={kb ? kb.name : t("kb.trainLogTitle")}
          description={t("kb.trainLogPageIntro")}
          actions={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={navigateToKbList}>
                {t("kb.title")}
              </Button>
            </div>
          }
        />

        {listError ? <Alert tone="error">{listError}</Alert> : null}

        <section className="space-y-6">
          <dl className="grid grid-cols-3 gap-x-3 gap-y-2 rounded-2xl bg-[var(--color-card-muted)]/60 px-3 py-2 md:px-4">
            <div className="min-w-0">
              <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{t("kb.trainLogSummaryRuns")}</dt>
              <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{formatInteger(summary?.total_run_count ?? rows.length)}</dd>
            </div>
            <div className="min-w-0">
              <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{t("kb.trainLogSummaryChars")}</dt>
              <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{formatInteger(summary?.total_char_count ?? 0)}</dd>
            </div>
            <div className="min-w-0">
              <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{t("kb.trainLogSummarySentences")}</dt>
              <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{formatInteger(summary?.total_sentence_count ?? 0)}</dd>
              {activeRunCount > 0 ? (
                <dd className="mt-0.5 truncate text-[10px] text-[var(--color-muted)]">
                  {t("kb.trainLogActiveRuns").replace("{{count}}", String(activeRunCount))}
                </dd>
              ) : null}
            </div>
          </dl>

          <section>
            <div className="app-table-wrap">
              <div className="app-table-head hidden grid-cols-[1fr_0.8fr_1.1fr_1fr_1fr_1.4fr_2.5rem] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid">
                <div>{t("kb.trainLogTime")}</div>
                <div>{t("kb.trainLogStatus")}</div>
                <div>{t("kb.trainLogProcessing")}</div>
                <div>{t("kb.trainLogTrainer")}</div>
                <div>{t("kb.trainLogType")}</div>
                <div>{t("kb.trainLogContentSource")}</div>
                <div className="sr-only">{t("kb.trainLogDownload")}</div>
              </div>

              {!runsQuery.isLoading && !rows.length ? (
                <Alert tone="info">{t("kb.trainLogEmpty")}</Alert>
              ) : null}

              {rows.length ? (
                <div className="divide-y divide-[var(--color-border)]">
                  {rows.map((row) => {
                    const detailUrl = row.itemId
                      ? `/kb/ingest/${uuid}/runs/${row.runId}?item=${encodeURIComponent(row.itemId)}`
                      : `/kb/ingest/${uuid}/runs/${row.runId}`;
                    return (
                      <div
                        key={`${row.runId}:${row.itemId ?? "run"}`}
                        className="grid cursor-pointer gap-3 px-5 py-4 transition-colors hover:bg-[var(--color-primary)]/5 md:grid-cols-[1fr_0.8fr_1.1fr_1fr_1fr_1.4fr_2.5rem] md:items-center md:gap-4"
                        onClick={() => navigate(detailUrl)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            navigate(detailUrl);
                          }
                        }}
                        tabIndex={0}
                      >
                        <div className="text-sm text-[var(--color-foreground)]">
                          {formatTimestamp(row.timestamp, {
                            locale,
                            timezone: settings?.timezone,
                            dateFormat: settings?.date_format,
                            timeFormat: settings?.time_format,
                          })}
                        </div>
                        <div>
                            <span
                              className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusBadgeClass(row.status)}`}
                            >
                              {getStatusLabel(row.status)}
                            </span>
                        </div>
                        <div className="text-sm text-[var(--color-muted)]">
                          {row.itemId
                            ? getItemProcessingPreview(
                                runs.find((run) => run.id === row.runId)?.items.find((item) => item.id === row.itemId) ??
                                  null,
                                processingPreviewLabels
                              )
                            : getRunProcessingPreview(runs.find((run) => run.id === row.runId) ?? null, processingPreviewLabels)}
                        </div>
                        <div className="text-sm text-[var(--color-foreground)]">{row.createdByLabel}</div>
                        <div className="text-sm text-[var(--color-muted)]">{row.kindLabel}</div>
                        <div>
                          <div className="font-medium text-[var(--color-foreground)]">{row.title}</div>
                          {row.preview && row.preview !== row.title ? (
                            <div className="mt-1 text-sm text-[var(--color-muted)]">{row.preview}</div>
                          ) : null}
                        </div>
                        <div className="flex md:justify-end">
                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-border)] text-[var(--color-muted)] transition hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] disabled:cursor-not-allowed disabled:opacity-45"
                            onClick={(event) => {
                              event.stopPropagation();
                              downloadTrainingMaterial(row.sourceId, row.title);
                            }}
                            onKeyDown={(event) => event.stopPropagation()}
                            disabled={!row.sourceId || downloadSourceId === row.sourceId}
                            aria-label={t("kb.trainLogDownload")}
                            title={t("kb.trainLogDownload")}
                          >
                            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                              <path
                                d="M12 4v10m0 0 4-4m-4 4-4-4M5 20h14"
                                stroke="currentColor"
                                strokeWidth="1.8"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                              />
                            </svg>
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : null}

              <div ref={loadMoreRef} className="py-6 text-center text-sm text-[var(--color-muted)]">
                {runsQuery.isFetchingNextPage ? t("kb.trainLogLoadingMore") : null}
              </div>
            </div>
          </section>
        </section>
      </div>
    </div>
  );
}
