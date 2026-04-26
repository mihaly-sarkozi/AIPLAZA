import { useEffect, useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useIngestRuns, useKbList, useReprocessIngestItemMutation } from "../hooks/useKb";
import {
  ACTIVE_RUN_STATUSES,
  buildTrainingRows,
  formatTimestamp,
  getItemProcessingPreview,
  getRunProcessingPreview,
  getStatusBadgeClass,
  getStatusLabel,
} from "./ingestLogHelpers";

export default function KBIngest() {
  const { uuid } = useParams();
  const navigate = useNavigate();
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const kb = useMemo(() => kbList.find((item) => item.uuid === uuid), [kbList, uuid]);
  const reprocessMutation = useReprocessIngestItemMutation({
    onSuccess: () => {
      toast.success("Az újrafeldolgozás elindult. A státusz hamarosan frissül.");
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error) ?? "Az újrafeldolgozás indítása sikertelen.");
    },
  });

  const runsQuery = useIngestRuns(uuid, {
    refetchInterval: ({ state }) => {
      const runs = state.data ?? [];
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
  const rows = useMemo(() => buildTrainingRows(runsQuery.data ?? []), [runsQuery.data]);
  const activeRunCount = runsQuery.data?.filter((run) => ACTIVE_RUN_STATUSES.has(run.status)).length ?? 0;
  const completedItemCount =
    runsQuery.data?.reduce((sum, run) => sum + run.completed_count + run.duplicate_count, 0) ?? 0;
  const failedItemCount =
    runsQuery.data?.reduce((sum, run) => sum + run.failed_count + run.rejected_count, 0) ?? 0;

  return (
    <div className="app-page">
      <div className="app-page-container">
        <PageHeader
          eyebrow="Tanítási napló"
          title={kb ? `${kb.name} - tanítások` : "Tanítási napló"}
          description="Itt csak a napló és az állapotok látszanak. Az egyes rekordokra kattintva megnyílik a külön részletező oldal."
          actions={
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => navigate("/kb")}>
                Tudástárak
              </Button>
              {uuid ? (
                <Button variant="ghost" onClick={() => runsQuery.refetch()}>
                  Frissítés
                </Button>
              ) : null}
            </div>
          }
        />

        {listError ? <Alert tone="error">{listError}</Alert> : null}

        <section className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <div className="app-surface p-4">
              <div className="text-sm text-[var(--color-muted)]">Összes futás</div>
              <div className="mt-2 text-2xl font-semibold">{runsQuery.data?.length ?? 0}</div>
            </div>
            <div className="app-surface p-4">
              <div className="text-sm text-[var(--color-muted)]">Aktív futás</div>
              <div className="mt-2 text-2xl font-semibold">{activeRunCount}</div>
            </div>
            <div className="app-surface p-4">
              <div className="text-sm text-[var(--color-muted)]">Sikeres rekord</div>
              <div className="mt-2 text-2xl font-semibold">{completedItemCount}</div>
            </div>
            <div className="app-surface p-4">
              <div className="text-sm text-[var(--color-muted)]">Hibás rekord</div>
              <div className="mt-2 text-2xl font-semibold">{failedItemCount}</div>
            </div>
          </div>

          <div className="app-surface p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-[var(--color-muted)]">Tanítási rekordok</p>
                <h2 className="mt-1 text-xl font-semibold">Olvasható napló</h2>
              </div>
            </div>

            {!runsQuery.isLoading && !rows.length ? (
              <div className="mt-4">
                <Alert tone="info">Ehhez a tudástárhoz még nincs tanítási rekord.</Alert>
              </div>
            ) : null}

            {rows.length ? (
              <div className="mt-4 overflow-x-auto">
                <table className="min-w-full border-separate border-spacing-0 text-sm">
                  <thead>
                    <tr className="text-left text-[var(--color-muted)]">
                      <th className="border-b border-[var(--color-border)] px-4 py-3 font-medium">Timestamp</th>
                      <th className="border-b border-[var(--color-border)] px-4 py-3 font-medium">Státusz</th>
                      <th className="border-b border-[var(--color-border)] px-4 py-3 font-medium">Feldolgozás</th>
                      <th className="border-b border-[var(--color-border)] px-4 py-3 font-medium">Tanítás típusa</th>
                      <th className="border-b border-[var(--color-border)] px-4 py-3 font-medium">Tartalom / forrás</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => {
                      const detailUrl = row.itemId
                        ? `/kb/ingest/${uuid}/runs/${row.runId}?item=${encodeURIComponent(row.itemId)}`
                        : `/kb/ingest/${uuid}/runs/${row.runId}`;
                      const isReprocessing = row.itemId ? reprocessMutation.isPending && reprocessMutation.variables?.itemId === row.itemId : false;
                      return (
                        <tr
                          key={`${row.runId}:${row.itemId ?? "run"}`}
                          className="cursor-pointer transition-colors hover:bg-[var(--color-primary)]/5"
                          onClick={() => navigate(detailUrl)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              navigate(detailUrl);
                            }
                          }}
                          tabIndex={0}
                        >
                          <td className="border-b border-[var(--color-border)] px-4 py-3 align-top whitespace-nowrap">
                            {formatTimestamp(row.timestamp)}
                          </td>
                          <td className="border-b border-[var(--color-border)] px-4 py-3 align-top">
                            <span
                              className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusBadgeClass(row.status)}`}
                            >
                              {getStatusLabel(row.status)}
                            </span>
                          </td>
                          <td className="border-b border-[var(--color-border)] px-4 py-3 align-top text-[var(--color-muted)]">
                            {row.itemId
                              ? getItemProcessingPreview(
                                  runsQuery.data?.find((run) => run.id === row.runId)?.items.find((item) => item.id === row.itemId) ??
                                    null
                                )
                              : getRunProcessingPreview(runsQuery.data?.find((run) => run.id === row.runId) ?? null)}
                          </td>
                          <td className="border-b border-[var(--color-border)] px-4 py-3 align-top whitespace-nowrap">
                            {row.kindLabel}
                          </td>
                          <td className="border-b border-[var(--color-border)] px-4 py-3 align-top">
                            <div className="font-medium text-[var(--color-foreground)]">{row.title}</div>
                            <div className="mt-1 text-[var(--color-muted)]">{row.preview}</div>
                            {row.itemId && uuid ? (
                              <div className="mt-3">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  disabled={isReprocessing}
                                  onClick={(event) => {
                                    event.preventDefault();
                                    event.stopPropagation();
                                    reprocessMutation.mutate({ itemId: row.itemId!, kbUuid: uuid });
                                  }}
                                >
                                  {isReprocessing ? "Újrafeldolgozás..." : "Újrafeldolgozás"}
                                </Button>
                              </div>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
