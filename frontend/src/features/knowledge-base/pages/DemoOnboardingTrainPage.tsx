import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage, isDuplicateContentError } from "../../../utils/getApiErrorMessage";
import {
  useCreateFileIngestMutation,
  useCreateTextIngestMutation,
  useIngestRun,
  useKbList,
} from "../hooks/useKb";
import {
  getTrainingFailureMessage,
  getTrainingProgress,
  getTrainingRunRefetchInterval,
  getTrainingStatusDetail,
  isTrainingActive,
} from "../utils/trainingProgress";

/** Chat üres állapotával megegyező szöveg- és gombstílus */
const ONBOARDING_MUTED_TEXT = "text-center max-w-md text-[var(--color-muted)] text-sm";
const ONBOARDING_GHOST_BTN =
  "text-xs px-2.5 py-1 rounded-md border border-[var(--color-border)] hover:bg-[var(--color-border)]/20 disabled:opacity-50 disabled:cursor-not-allowed";
export default function DemoOnboardingTrainPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const { data: kbListData = [], isLoading: kbLoading } = useKbList();
  const trainable = kbListData.filter((k) => k.can_train);
  const kbUuid = trainable[0]?.uuid ?? "";

  const [statusText, setStatusText] = useState("");
  const [statusKind, setStatusKind] = useState<"error" | "success" | "info">("info");
  const [showTrainModal, setShowTrainModal] = useState(false);
  const [trainTab, setTrainTab] = useState<"file" | "text">("file");
  const [selectedTrainFile, setSelectedTrainFile] = useState<File | null>(null);
  const [dragOverTrainFile, setDragOverTrainFile] = useState(false);
  const [textTrainValue, setTextTrainValue] = useState("");
  const [showTrainingProgressModal, setShowTrainingProgressModal] = useState(false);
  const [showTrainingDoneModal, setShowTrainingDoneModal] = useState(false);
  const [activeTrainingRunId, setActiveTrainingRunId] = useState<string | undefined>(undefined);
  const fileRef = useRef<HTMLInputElement>(null);
  const createTextMutation = useCreateTextIngestMutation();
  const createFileMutation = useCreateFileIngestMutation();
  const activeTrainingRunQuery = useIngestRun(activeTrainingRunId, {
    refetchInterval: ({ state }) => getTrainingRunRefetchInterval(state.data?.status),
  });
  const activeTrainingRun = activeTrainingRunQuery.data;
  const trainingProgress = useMemo(() => getTrainingProgress(activeTrainingRun), [activeTrainingRun]);
  const loading =
    createTextMutation.isPending || createFileMutation.isPending || isTrainingActive(activeTrainingRun?.status);
  const trainingStatusDetail = useMemo(() => getTrainingStatusDetail(activeTrainingRun, t), [activeTrainingRun, t]);

  useEffect(() => {
    if (user?.tenant_demo_mode && user.tenant_kb_has_training === true) {
      navigate("/chat", { replace: true });
    }
  }, [user, navigate]);

  useEffect(() => {
    if (kbLoading) return;
    if (!kbUuid) {
      setStatusKind("info");
      setStatusText(t("onboarding.noTrainableKb"));
      return;
    }
    setStatusKind("info");
    setStatusText("");
  }, [kbLoading, kbUuid, t]);

  const runAfterSuccess = useCallback(() => {
    setStatusKind("success");
    setStatusText(t("kb.trainedSuccess"));
    if (user) {
      setUser({ ...user, tenant_kb_has_training: true });
    }
  }, [setUser, t, user]);

  const onCloseTrainingDone = () => {
    setShowTrainingDoneModal(false);
    navigate("/chat", { replace: true });
  };

  useEffect(() => {
    if (!activeTrainingRunId || !activeTrainingRun) return;
    if (isTrainingActive(activeTrainingRun.status)) {
      setShowTrainingProgressModal(true);
      return;
    }

    setShowTrainingProgressModal(false);
    if (activeTrainingRun.status === "completed") {
      runAfterSuccess();
      setShowTrainingDoneModal(true);
    } else {
      setStatusKind("error");
      setStatusText(getTrainingFailureMessage(activeTrainingRun, t) ?? t("chat.trainingFailed"));
    }
    setActiveTrainingRunId(undefined);
  }, [activeTrainingRun, activeTrainingRunId, runAfterSuccess, t]);

  const onOpenTrainModal = () => {
    if (loading || !kbUuid) return;
    setTrainTab("file");
    setSelectedTrainFile(null);
    setTextTrainValue("");
    setShowTrainModal(true);
  };

  const onSelectTrainingFile = (file: File | null) => {
    if (!file || loading || !kbUuid) return;
    setStatusKind("info");
    setStatusText(`${t("kb.trainFileSelected")} ${file.name}`);
    setShowTrainingDoneModal(false);
    createFileMutation.mutate(
      { kbUuid, files: [file] },
      {
        onSuccess: (run) => {
          setActiveTrainingRunId(run.id);
          setShowTrainingProgressModal(true);
          setShowTrainModal(false);
          setSelectedTrainFile(null);
          if (fileRef.current) fileRef.current.value = "";
        },
        onError: (error) => {
          setStatusKind("error");
          setStatusText(getApiErrorMessage(error) ?? "A fájlos tanítás indítása sikertelen.");
        },
      }
    );
    if (fileRef.current) fileRef.current.value = "";
  };

  const onSubmitTextTraining = () => {
    const raw = textTrainValue.trim();
    if (!raw || loading || !kbUuid) return;
    setShowTrainingDoneModal(false);
    createTextMutation.mutate(
      {
        kbUuid,
        text: textTrainValue,
      },
      {
        onSuccess: (run) => {
          setActiveTrainingRunId(run.id);
          setShowTrainingProgressModal(true);
          setShowTrainModal(false);
          setTextTrainValue("");
          setStatusText("");
        },
        onError: (error) => {
          if (isDuplicateContentError(error)) {
            const detail = getApiErrorMessage(error) ?? t("kb.errorDuplicateContent");
            setStatusKind("info");
            setStatusText(`${t("chat.trainingAborted")} ${detail}`);
            return;
          }
          setStatusKind("error");
          setStatusText(getApiErrorMessage(error) ?? "A szöveges tanítás indítása sikertelen.");
        },
      }
    );
  };

  return (
    <div className="flex-1 min-h-0 flex flex-col bg-[var(--color-background)] text-[var(--color-foreground)]">
      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
        className="hidden"
        onChange={(e) => setSelectedTrainFile(e.target.files?.[0] ?? null)}
      />
      <div className="flex-1 min-h-0 flex items-center justify-center px-4">
        <div className="w-full max-w-md flex flex-col items-center gap-3">
          {kbUuid ? <div className={ONBOARDING_MUTED_TEXT}>{t("onboarding.trainPageIntro")}</div> : null}

          {kbUuid ? (
            <button
              type="button"
              onClick={onOpenTrainModal}
              disabled={loading}
              className={ONBOARDING_GHOST_BTN}
            >
              {t("nav.train")}
            </button>
          ) : null}

          {statusText ? (
            <p
              className={`text-sm text-center max-w-md ${
                statusKind === "error"
                  ? "text-red-600"
                  : statusKind === "success"
                    ? "text-green-700 dark:text-green-400"
                    : "text-[var(--color-muted)]"
              }`}
            >
              {statusText}
            </p>
          ) : null}

          {!kbLoading && !kbUuid ? (
            <button type="button" onClick={() => navigate("/kb")} className={`mt-1 ${ONBOARDING_GHOST_BTN}`}>
              {t("onboarding.openKb")}
            </button>
          ) : null}
        </div>
      </div>

      {showTrainModal ? (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center px-4">
          <div className="w-full max-w-lg rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-4">
            <div className="mb-3 flex items-center gap-2">
              <button
                type="button"
                onClick={() => setTrainTab("file")}
                className={`h-10 px-3 rounded text-sm border ${
                  trainTab === "file"
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)]"
                    : "border-[var(--color-border)]"
                }`}
              >
                {t("kb.trainFileUploadButton")}
              </button>
              <button
                type="button"
                onClick={() => setTrainTab("text")}
                className={`h-10 px-3 rounded text-sm border ${
                  trainTab === "text"
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)]"
                    : "border-[var(--color-border)]"
                }`}
              >
                {t("kb.trainWithText")}
              </button>
            </div>
            {trainTab === "file" ? (
              <div
                className={`w-full min-h-[160px] rounded-lg border-2 border-dashed p-4 flex flex-col items-center justify-center gap-3 ${
                  dragOverTrainFile ? "border-[var(--color-primary)]" : "border-[var(--color-border)]"
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOverTrainFile(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setDragOverTrainFile(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOverTrainFile(false);
                  setSelectedTrainFile(e.dataTransfer?.files?.[0] ?? null);
                }}
              >
                <div className="text-sm text-[var(--color-muted)] text-center">
                  Húzd ide a fájlt vagy válassz a gombbal.
                </div>
                {selectedTrainFile ? (
                  <div className="text-xs text-[var(--color-muted)]">{selectedTrainFile.name}</div>
                ) : null}
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="text-xs px-2.5 py-1 rounded-md border border-[var(--color-border)] hover:bg-[var(--color-border)]/20 disabled:opacity-50"
                >
                  Fájl feltöltése
                </button>
              </div>
            ) : (
              <textarea
                value={textTrainValue}
                onChange={(e) => setTextTrainValue(e.target.value)}
                className="chat-question-input w-full min-h-[160px] border border-[var(--color-border)] rounded-lg p-3 bg-[var(--color-background)]"
                placeholder="Írj be mondatokat vagy bekezdéseket..."
              />
            )}
            {trainTab === "file" ? (
              <div className="mt-3 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowTrainModal(false)}
                  className="px-4 py-2 rounded border border-[var(--color-border)]"
                >
                  Vissza
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const f = selectedTrainFile;
                    setShowTrainModal(false);
                    if (f) onSelectTrainingFile(f);
                  }}
                  disabled={!selectedTrainFile}
                  className="px-4 py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)] disabled:opacity-50"
                >
                  {t("nav.train")}
                </button>
              </div>
            ) : (
              <div className="mt-3 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowTrainModal(false)}
                  className="px-4 py-2 rounded border border-[var(--color-border)]"
                >
                  Vissza
                </button>
                <button
                  type="button"
                  onClick={onSubmitTextTraining}
                  disabled={!textTrainValue.trim() || loading}
                  className="px-4 py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)] disabled:opacity-50"
                >
                  {t("nav.train")}
                </button>
              </div>
            )}
          </div>
        </div>
      ) : null}

      {showTrainingProgressModal ? (
        <div className="fixed inset-0 z-[75] bg-black/40 backdrop-blur-[1px] flex items-center justify-center px-4">
          <div className="w-full max-w-xs rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-6 text-center">
            <div className="relative mx-auto h-24 w-24">
              <div className="absolute inset-0 rounded-full border-4 border-[var(--color-border)]" />
              <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-[var(--color-primary)] animate-spin" />
              <div className="absolute inset-0 flex items-center justify-center text-lg font-bold">{trainingProgress}%</div>
            </div>
            <div className="mt-4 text-sm font-medium">{t("nav.train")}</div>
            {trainingStatusDetail ? <div className="mt-1 text-xs text-[var(--color-muted)]">{trainingStatusDetail}</div> : null}
            <div className="mt-3 h-1.5 w-full rounded-full bg-[var(--color-border)] overflow-hidden">
              <div
                className="h-full bg-[var(--color-primary)] transition-all duration-150"
                style={{ width: `${trainingProgress}%` }}
              />
            </div>
          </div>
        </div>
      ) : null}

      {showTrainingDoneModal ? (
        <div className="fixed inset-0 z-[80] bg-black/40 flex items-center justify-center px-4">
          <div className="w-full max-w-sm rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-5 text-center">
            <div className="text-base font-semibold text-[var(--color-foreground)]">A tanítás befejeződött.</div>
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                type="button"
                onClick={onCloseTrainingDone}
                className="px-4 py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)]"
              >
                Bezárás
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
