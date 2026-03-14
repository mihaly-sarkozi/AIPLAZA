import { useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { ProcessProgressOverlay } from "../../../components/ProcessProgressOverlay";
import {
  useKbList,
  useKbTrainingLog,
  useKbTrainTextMutation,
  useKbTrainFileMutation,
  useDeleteKbTrainingPointMutation,
  type KbTrainingLogEntry,
  type PiiDecisionItem,
} from "../hooks/useKb";

type PiiMatchItem = {
  index: number;
  value: string;
  type: string;
  context_before: string;
  context_after: string;
};

const ACCEPT_TRAIN = ".txt,.pdf,.docx";

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function isTxt(file: File): boolean {
  return file.name.toLowerCase().endsWith(".txt");
}

/** Mondatok száma: . ! ? \n alapján */
function countSentences(text: string): number {
  if (!text?.trim()) return 0;
  const parts = text.split(/(?<=[.!?])\s+|\n+/);
  return parts.filter((p) => p.trim().length > 0).length;
}

function readTxtFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve((r.result as string) ?? "");
    r.onerror = () => reject(new Error("Could not read file"));
    r.readAsText(file, "utf-8");
  });
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === "object" && "response" in error) {
    const res = (error as { response?: { data?: { detail?: string } } }).response;
    const detail = res?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return fallback;
}

export default function KBTrain() {
  const { t } = useTranslation();
  const { uuid } = useParams();
  const [content, setContent] = useState("");
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadDragOver, setUploadDragOver] = useState(false);
  const [contentDragOver, setContentDragOver] = useState(false);
  const [logModalOpen, setLogModalOpen] = useState(false);
  const [viewEntry, setViewEntry] = useState<KbTrainingLogEntry | null>(null);
  const [piiConfirmOpen, setPiiConfirmOpen] = useState(false);
  const [piiConfirmPayload, setPiiConfirmPayload] = useState<{
    type: "text" | "file";
    uuid: string;
    content?: string;
    file?: File;
    matches: PiiMatchItem[];
  } | null>(null);
  const [piiDecisions, setPiiDecisions] = useState<Record<number, "delete" | "mask" | "keep">>({});
  const [processingTotalSentences, setProcessingTotalSentences] = useState<number | null>(null);

  const { data: kbList = [] } = useKbList();
  const currentKb = uuid ? kbList.find((k) => k.uuid === uuid) : null;
  const kbName = currentKb?.name ?? "";
  const { data: logEntries = [], isLoading: logLoading } = useKbTrainingLog(uuid);
  const trainTextMutation = useKbTrainTextMutation();
  const trainFileMutation = useKbTrainFileMutation();
  const deletePointMutation = useDeleteKbTrainingPointMutation();

  const trainWithFile = useCallback(
    async (file: File, confirmPii = false, piiDecisionsList?: PiiDecisionItem[]) => {
      if (!uuid) return;
      if (isTxt(file)) {
        try {
          const text = await readTxtFile(file);
          setProcessingTotalSentences(countSentences(text));
        } catch {
          setProcessingTotalSentences(null);
        }
      } else {
        setProcessingTotalSentences(null);
      }
      const formData = new FormData();
      formData.append("file", file);
      trainFileMutation.mutate(
        { uuid, formData, confirm_pii: confirmPii, pii_decisions: piiDecisionsList },
        {
          onSuccess: (data: { masked?: boolean; pii_replaced_with_dots?: boolean }) => {
            if (data?.pii_replaced_with_dots) {
              toast.success(t("kb.piiDeletedMessage"));
            } else if (data?.masked) {
              toast.success(t("kb.piiMaskedMessage"));
            } else {
              toast.success(t("kb.trainedSuccess"));
            }
            setPiiConfirmOpen(false);
            setPiiConfirmPayload(null);
            setPiiDecisions({});
          },
          onError: (err: unknown) => {
            const ax = err as { response?: { status?: number; data?: { detail?: { requires_pii_confirmation?: boolean; matches?: PiiMatchItem[] } } } };
            const detail = ax.response?.data?.detail;
            if (ax.response?.status === 409 && detail?.requires_pii_confirmation) {
              const matches = (detail.matches || []) as PiiMatchItem[];
              setPiiConfirmPayload({ type: "file", uuid, file, matches });
              setPiiDecisions({});
              setPiiConfirmOpen(true);
              return;
            }
            toast.error(getApiErrorMessage(err, t("kb.errorUpdate")));
          },
          onSettled: () => setProcessingTotalSentences(null),
        }
      );
    },
    [uuid, trainFileMutation, t]
  );

  const applyFile = useCallback(
    async (file: File) => {
      if (isTxt(file)) {
        try {
          const text = await readTxtFile(file);
          setContent(text);
          setUploadModalOpen(false);
        } catch {
          toast.error(t("kb.errorUpdate"));
        }
      } else {
        await trainWithFile(file);
        setUploadModalOpen(false);
      }
    },
    [trainWithFile, t]
  );

  const handleUploadModalDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setUploadDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) applyFile(f);
  };

  const handleContentDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setContentDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (!f) return;
    if (isTxt(f)) {
      readTxtFile(f)
        .then((text) => setContent(text))
        .catch(() => toast.error(t("kb.errorUpdate")));
    } else {
      trainWithFile(f).catch(() => {});
    }
  };

  const trainText = (piiDecisionsList?: PiiDecisionItem[]) => {
    if (!uuid) return;
    if (!content.trim()) {
      toast.error(t("kb.noContentError"));
      return;
    }
    setProcessingTotalSentences(countSentences(content));
    trainTextMutation.mutate(
      { uuid, title: "", content, confirm_pii: !!piiDecisionsList?.length, pii_decisions: piiDecisionsList },
      {
        onSuccess: (data: { masked?: boolean; pii_replaced_with_dots?: boolean }) => {
          if (data?.pii_replaced_with_dots) {
            toast.success(t("kb.piiDeletedMessage"));
          } else if (data?.masked) {
            toast.success(t("kb.piiMaskedMessage"));
          } else {
            toast.success(t("kb.trainedSuccess"));
          }
          setContent("");
          setPiiConfirmOpen(false);
          setPiiConfirmPayload(null);
          setPiiDecisions({});
        },
        onError: (err: unknown) => {
          const ax = err as { response?: { status?: number; data?: { detail?: { requires_pii_confirmation?: boolean; matches?: PiiMatchItem[] } } } };
          const detail = ax.response?.data?.detail;
          if (ax.response?.status === 409 && detail?.requires_pii_confirmation) {
            const matches = (detail.matches || []) as PiiMatchItem[];
            setPiiConfirmPayload({ type: "text", uuid, content, matches });
            setPiiDecisions({});
            setPiiConfirmOpen(true);
            return;
          }
          toast.error(getApiErrorMessage(err, t("kb.errorUpdate")));
        },
        onSettled: () => setProcessingTotalSentences(null),
      }
    );
  };

  const confirmPiiAndTrain = async () => {
    if (!piiConfirmPayload) return;
    const decisionsList: PiiDecisionItem[] = piiConfirmPayload.matches.map((m) => ({
      index: m.index,
      decision: piiDecisions[m.index] ?? "mask",
    }));
    if (piiConfirmPayload.type === "text") {
      const cnt = piiConfirmPayload.content ?? "";
      setProcessingTotalSentences(countSentences(cnt));
      trainTextMutation.mutate(
        {
          uuid: piiConfirmPayload.uuid,
          title: "",
          content: piiConfirmPayload.content ?? "",
          confirm_pii: true,
          pii_decisions: decisionsList,
        },
        {
          onSuccess: (data: { masked?: boolean; pii_replaced_with_dots?: boolean }) => {
            if (data?.pii_replaced_with_dots) {
              toast.success(t("kb.piiDeletedMessage"));
            } else if (data?.masked) {
              toast.success(t("kb.piiMaskedMessage"));
            } else {
              toast.success(t("kb.trainedSuccess"));
            }
            setContent("");
            setPiiConfirmOpen(false);
            setPiiConfirmPayload(null);
            setPiiDecisions({});
          },
          onError: (err) => toast.error(getApiErrorMessage(err, t("kb.errorUpdate"))),
          onSettled: () => setProcessingTotalSentences(null),
        }
      );
    } else {
      await trainWithFile(piiConfirmPayload.file!, true, decisionsList);
    }
  };

  const deleteEntry = (entry: KbTrainingLogEntry) => {
    if (!uuid || !window.confirm(t("kb.trainLogDeleteConfirm"))) return;
    deletePointMutation.mutate(
      { uuid, pointId: entry.point_id },
      {
        onSuccess: () => toast.success(t("kb.trainedSuccess")),
        onError: (err) => toast.error(getApiErrorMessage(err, t("kb.errorUpdate"))),
      }
    );
  };

  const isProcessing =
    trainTextMutation.isPending || trainFileMutation.isPending;

  return (
    <div className="p-6 min-h-full bg-[var(--color-background)]">
      <ProcessProgressOverlay
        isActive={isProcessing}
        label={t("kb.processing")}
        subLabel={piiConfirmOpen ? t("kb.processingTextCleaning") : undefined}
        totalSentences={processingTotalSentences}
      />
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <h1 className="text-xl sm:text-2xl font-bold text-[var(--color-foreground)] uppercase tracking-wide">
          {kbName || t("kb.trainPageTitle")}
        </h1>
        <button
          type="button"
          onClick={() => setLogModalOpen(true)}
          className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] px-4 py-2 rounded text-sm hover:bg-[var(--color-button-hover)]"
        >
          {t("kb.trainLogTitle")}
        </button>
      </div>

      <section>
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg">
          <textarea
            rows={10}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onDragOver={(e) => {
              e.preventDefault();
              setContentDragOver(true);
            }}
            onDragLeave={() => setContentDragOver(false)}
            onDrop={handleContentDrop}
            className={`w-full p-3 rounded bg-[var(--color-input-bg)] border text-[var(--color-foreground)] resize-y text-sm ${
              contentDragOver ? "border-[var(--color-primary)] ring-1 ring-[var(--color-primary)]" : "border-[var(--color-border)]"
            }`}
            placeholder={t("kb.trainContentPlaceholder")}
          />
          <div className="flex flex-wrap items-center justify-end gap-3">
            <button
              type="button"
              onClick={() => setUploadModalOpen(true)}
              className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] px-4 py-2 rounded text-sm hover:bg-[var(--color-button-hover)]"
            >
              {t("kb.trainFileUploadButton")}
            </button>
            <button
              type="button"
              className="bg-[var(--color-primary)] text-[var(--color-on-primary)] px-4 py-2 rounded text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              onClick={trainText}
              disabled={trainTextMutation.isPending}
            >
              {trainTextMutation.isPending ? t("kb.processing") : t("kb.trainWithText")}
            </button>
          </div>
        </div>
      </section>

      {/* Tanítási napló modal – gombbal előhívva */}
      {logModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={() => setLogModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="log-modal-title"
        >
          <div
            className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg shadow-xl max-w-4xl w-full max-h-[85vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-[var(--color-border)] flex justify-between items-center shrink-0">
              <h2 id="log-modal-title" className="text-lg font-bold text-[var(--color-foreground)]">
                {t("kb.trainLogTitle")}
              </h2>
              <button
                type="button"
                onClick={() => setLogModalOpen(false)}
                className="p-1 rounded hover:bg-[var(--color-button-hover)] text-[var(--color-foreground)]"
                aria-label="Bezárás"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="overflow-auto flex-1 min-h-0">
              {logLoading ? (
                <div className="p-4 text-[var(--color-muted)] text-sm">{t("kb.processing")}</div>
              ) : logEntries.length === 0 ? (
                <div className="p-4 text-[var(--color-muted)] text-sm">{t("kb.trainLogEmpty")}</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--color-border)] bg-[var(--color-table-head)]">
                        <th className="text-left p-3 text-[var(--color-label)]">{t("kb.trainLogWho")}</th>
                        <th className="text-left p-3 text-[var(--color-label)]">{t("kb.trainLogWhen")}</th>
                        <th className="text-left p-3 text-[var(--color-label)]">{t("kb.trainLogWhat")}</th>
                        <th className="text-right p-3 text-[var(--color-label)] w-32"> </th>
                      </tr>
                    </thead>
                    <tbody>
                      {logEntries.map((entry) => (
                        <tr
                          key={entry.point_id}
                          className="border-b border-[var(--color-border)] last:border-b-0 hover:bg-[var(--color-button-hover)]/30"
                        >
                          <td className="p-3 text-[var(--color-foreground)]">
                            {entry.user_display || "—"}
                          </td>
                          <td className="p-3 text-[var(--color-muted)]">
                            {formatDateTime(entry.created_at)}
                          </td>
                          <td className="p-3 text-[var(--color-foreground)] max-w-xs truncate" title={entry.title}>
                            {entry.title}
                          </td>
                          <td className="p-3 text-right">
                            <button
                              type="button"
                              onClick={() => setViewEntry(entry)}
                              className="text-[var(--color-primary)] hover:underline mr-2"
                            >
                              {t("kb.trainLogView")}
                            </button>
                            <button
                              type="button"
                              onClick={() => deleteEntry(entry)}
                              disabled={deletePointMutation.isPending}
                              className="text-red-600 dark:text-red-400 hover:underline disabled:opacity-50"
                            >
                              {t("kb.trainLogDelete")}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Feltöltés felugró: fájl választás vagy drag-and-drop → tartalomba vagy közvetlen tanítás */}
      {uploadModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={() => setUploadModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="upload-modal-title"
        >
          <div
            className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg shadow-xl max-w-md w-full overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-[var(--color-border)] flex justify-between items-center">
              <h3 id="upload-modal-title" className="font-semibold text-[var(--color-foreground)]">
                {t("kb.trainUploadModalTitle")}
              </h3>
              <button
                type="button"
                onClick={() => setUploadModalOpen(false)}
                className="p-1 rounded hover:bg-[var(--color-button-hover)] text-[var(--color-foreground)]"
                aria-label="Bezárás"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4">
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition ${
                  uploadDragOver ? "border-[var(--color-primary)] bg-[var(--color-table-head)]" : "border-[var(--color-border)]"
                }`}
                onDragOver={(e) => { e.preventDefault(); setUploadDragOver(true); }}
                onDragLeave={() => setUploadDragOver(false)}
                onDrop={handleUploadModalDrop}
              >
                <p className="text-sm text-[var(--color-muted)] mb-4">
                  {t("kb.trainUploadModalDrop")}
                </p>
                <input
                  type="file"
                  accept={ACCEPT_TRAIN}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) applyFile(f);
                    e.target.value = "";
                  }}
                  className="block w-full text-sm text-[var(--color-foreground)] file:mr-2 file:py-2 file:px-3 file:rounded file:border-0 file:bg-[var(--color-primary)] file:text-[var(--color-on-primary)]"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: személyes adat – felhasználói döntés soronként (Törlés/Maszkolás/Megtartás) */}
      {piiConfirmOpen && piiConfirmPayload && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={() => {
            setPiiConfirmOpen(false);
            setPiiConfirmPayload(null);
            setPiiDecisions({});
          }}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-[var(--color-border)] shrink-0">
              <h3 className="font-semibold text-[var(--color-foreground)]">
                {t("kb.piiReviewTitle")}
              </h3>
            </div>
            <div className="overflow-y-auto flex-1 min-h-0 p-4 space-y-4">
              {piiConfirmPayload.matches.map((m) => (
                <div
                  key={m.index}
                  className="border border-[var(--color-border)] rounded-lg p-3 bg-[var(--color-input-bg)]"
                >
                  <div className="text-sm text-[var(--color-foreground)] mb-2 font-mono break-words">
                    <span className="text-[var(--color-muted)]">{m.context_before}</span>
                    <strong className="font-bold text-[var(--color-primary)]">{m.value}</strong>
                    <span className="text-[var(--color-muted)]">{m.context_after}</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {piiDecisions[m.index] == null ? (
                      <>
                        <button
                          type="button"
                          onClick={() => setPiiDecisions((prev) => ({ ...prev, [m.index]: "delete" }))}
                          className="px-3 py-1.5 rounded text-sm border border-red-500/50 text-red-600 dark:text-red-400 hover:bg-red-500/10"
                        >
                          {t("kb.piiReviewDelete")}
                        </button>
                        <button
                          type="button"
                          onClick={() => setPiiDecisions((prev) => ({ ...prev, [m.index]: "mask" }))}
                          className="px-3 py-1.5 rounded text-sm border border-[var(--color-border)] text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)]"
                        >
                          {t("kb.piiReviewMask")}
                        </button>
                        <button
                          type="button"
                          onClick={() => setPiiDecisions((prev) => ({ ...prev, [m.index]: "keep" }))}
                          className="px-3 py-1.5 rounded text-sm border border-[var(--color-border)] text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)]"
                        >
                          {t("kb.piiReviewKeep")}
                        </button>
                      </>
                    ) : (
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-[var(--color-muted)]">
                          {piiDecisions[m.index] === "delete"
                            ? t("kb.piiReviewActionDelete")
                            : piiDecisions[m.index] === "mask"
                              ? t("kb.piiReviewActionMask")
                              : t("kb.piiReviewActionKeep")}
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            setPiiDecisions((prev) => {
                              const next = { ...prev };
                              delete next[m.index];
                              return next;
                            })
                          }
                          className="px-2 py-1 rounded text-sm border border-[var(--color-border)] text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)]"
                        >
                          {t("kb.piiReviewBack")}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="p-4 border-t border-[var(--color-border)] flex flex-wrap justify-between gap-3 shrink-0">
              <button
                type="button"
                onClick={() => {
                  setPiiConfirmOpen(false);
                  setPiiConfirmPayload(null);
                  setPiiDecisions({});
                }}
                className="px-4 py-2 rounded border border-[var(--color-border)] text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)]"
              >
                {t("kb.piiReviewCancel")}
              </button>
              <button
                type="button"
                onClick={confirmPiiAndTrain}
                disabled={
                  piiConfirmPayload.matches.some((m) => piiDecisions[m.index] == null) ||
                  (piiConfirmPayload.type === "text" ? trainTextMutation.isPending : trainFileMutation.isPending)
                }
                className="bg-[var(--color-primary)] text-[var(--color-on-primary)] px-4 py-2 rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {piiConfirmPayload.type === "text" && trainTextMutation.isPending
                  ? t("kb.processing")
                  : piiConfirmPayload.type === "file" && trainFileMutation.isPending
                    ? t("kb.processing")
                    : t("kb.piiReviewTrain")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: tanítási anyag megtekintése */}
      {viewEntry && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={() => setViewEntry(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-[var(--color-border)] flex justify-between items-start">
              <div>
                <p className="text-sm text-[var(--color-muted)]">
                  {viewEntry.user_display} · {formatDateTime(viewEntry.created_at)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setViewEntry(null)}
                className="p-1 rounded hover:bg-[var(--color-button-hover)] text-[var(--color-foreground)]"
                aria-label="Bezárás"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              <pre className="whitespace-pre-wrap text-sm text-[var(--color-foreground)] font-sans">
                {viewEntry.content || "—"}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
