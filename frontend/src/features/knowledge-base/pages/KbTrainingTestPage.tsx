import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { getApiErrorMessage, isDuplicateContentError } from "../../../utils/getApiErrorMessage";
import { useKbList } from "../hooks/useKb";
import { useSubmitTextTrainingMutation, useTrainingBatch } from "../hooks/useKbTraining";
import {
  getTrainingFailureMessage,
  getTrainingProgress,
  getTrainingStatusLabel,
  isTrainingActive,
} from "../utils/trainingProgress";

export default function KbTrainingTestPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const trainable = useMemo(() => kbList.filter((kb) => kb.can_train), [kbList]);

  const [kbUuid, setKbUuid] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [activeBatchId, setActiveBatchId] = useState<string | undefined>();
  const [submitNotice, setSubmitNotice] = useState<string | null>(null);

  const submitMutation = useSubmitTextTrainingMutation({
    onSuccess: (result) => {
      setSubmitNotice(null);
      setActiveBatchId(result.batchId);
      toast.success(t("kb.trainedSuccess"));
    },
    onError: (error) => {
      if (isDuplicateContentError(error)) {
        const detail = getApiErrorMessage(error) ?? t("kb.errorDuplicateContent");
        setSubmitNotice(`${t("chat.trainingAborted")} ${detail}`);
        return;
      }
      setSubmitNotice(null);
      toast.error(getApiErrorMessage(error) ?? t("chat.textTrainingStartError"));
    },
  });

  const batchQuery = useTrainingBatch(activeBatchId, {
    refetchInterval: ({ state }) => (isTrainingActive(state.data?.status) ? 1500 : false),
  });
  const activeBatch = batchQuery.data;
  const progress = useMemo(() => getTrainingProgress(activeBatch), [activeBatch]);

  const onSubmit = () => {
    const text = content.trim();
    if (!kbUuid || !text || submitMutation.isPending) return;
    setSubmitNotice(null);
    submitMutation.mutate({
      kbUuid,
      content: text,
      title: title.trim() || undefined,
    });
  };

  return (
    <div className="app-page">
      <div className="app-page-container max-w-2xl">
        <PageHeader
          eyebrow="kb_ingest"
          title="Szöveges tanítás teszt"
          description="Csak a POST /kb/{id}/training/text és GET /kb/training/batches/{id} végpontokhoz."
        />

        <div className="mt-6 space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] p-5">
          <label className="block space-y-1">
            <span className="text-sm font-medium text-[var(--color-foreground)]">Tudásbázis</span>
            <select
              className="w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
              value={kbUuid}
              disabled={kbLoading || submitMutation.isPending}
              onChange={(event) => setKbUuid(event.target.value)}
            >
              <option value="">{kbLoading ? t("common.loading") : "Válassz tudásbázist…"}</option>
              {trainable.map((kb) => (
                <option key={kb.uuid} value={kb.uuid}>
                  {kb.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium text-[var(--color-foreground)]">Cím (opcionális)</span>
            <input
              type="text"
              className="w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
              value={title}
              disabled={submitMutation.isPending}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Teszt cím"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-sm font-medium text-[var(--color-foreground)]">Szöveg</span>
            <textarea
              className="min-h-40 w-full rounded-md border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
              value={content}
              disabled={submitMutation.isPending}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Ide írd a tanító szöveget…"
            />
          </label>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="rounded-md bg-[var(--color-primary)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              disabled={!kbUuid || !content.trim() || submitMutation.isPending}
              onClick={onSubmit}
            >
              {submitMutation.isPending ? t("common.loading") : t("kb.trainWithText")}
            </button>
            <button
              type="button"
              className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm"
              onClick={() => navigate("/kb")}
            >
              {t("common.back")}
            </button>
          </div>

          {submitNotice ? (
            <p className="text-sm text-[var(--color-muted)]" role="status">
              {submitNotice}
            </p>
          ) : null}
        </div>

        {activeBatch ? (
          <div className="mt-6 space-y-3 rounded-xl border border-[var(--color-border)] p-5">
            <div className="text-sm text-[var(--color-muted)]">Batch ID: {activeBatch.id}</div>
            <div className="text-sm">
              Státusz: <strong>{getTrainingStatusLabel(activeBatch, t)}</strong> ({activeBatch.status})
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[var(--color-border)]/40">
              <div
                className="h-full bg-[var(--color-primary)] transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            {activeBatch.events.length > 0 ? (
              <ul className="max-h-48 space-y-1 overflow-y-auto text-xs text-[var(--color-muted)]">
                {activeBatch.events.map((event) => (
                  <li key={event.id}>
                    [{event.event_type}] {event.message}
                  </li>
                ))}
              </ul>
            ) : null}
            {!isTrainingActive(activeBatch.status) && activeBatch.status !== "completed" ? (
              <p className="text-sm text-red-600">
                {getTrainingFailureMessage(activeBatch, t) ?? t("chat.trainingFailed")}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
