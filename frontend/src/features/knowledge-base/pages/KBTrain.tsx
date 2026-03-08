import { useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { useKbTrainTextMutation, useKbTrainFileMutation } from "../hooks/useKb";

export default function KBTrain() {
  const { t } = useTranslation();
  const { uuid } = useParams();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const trainTextMutation = useKbTrainTextMutation();
  const trainFileMutation = useKbTrainFileMutation();

  const trainText = () => {
    if (!uuid) return;
    trainTextMutation.mutate(
      { uuid, title, content },
      {
        onSuccess: () => toast.success(t("kb.trainedSuccess")),
        onError: () => toast.error(t("kb.errorUpdate")),
      }
    );
  };

  const trainFile = () => {
    if (!uuid) return;
    if (!file) {
      toast.error(t("kb.noFileSelected"));
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    trainFileMutation.mutate(
      { uuid, formData },
      {
        onSuccess: () => toast.success(t("kb.trainedSuccess")),
        onError: () => toast.error(t("kb.errorUpdate")),
      }
    );
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  return (
    <div className="p-6 min-h-full bg-[var(--color-background)] max-w-3xl mx-auto">
      <h1 className="text-xl sm:text-2xl md:text-3xl font-bold mb-6 text-[var(--color-foreground)]">
        {t("kb.trainPageTitle")}
      </h1>

      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg mb-10">
        <h2 className="text-lg font-bold mb-4 text-[var(--color-foreground)]">{t("kb.trainTextSection")}</h2>

        <label className="block mb-1 text-[var(--color-label)]">{t("kb.trainTextTitle")}</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mb-4 w-full p-3 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
        />

        <label className="block mb-1 text-[var(--color-label)]">{t("kb.trainTextContent")}</label>
        <textarea
          rows={6}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="mb-4 w-full p-3 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] resize-y"
        />

        <button
          type="button"
          className="bg-[var(--color-primary)] text-[var(--color-on-primary)] px-4 py-2 rounded hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={trainText}
          disabled={trainTextMutation.isPending}
        >
          {trainTextMutation.isPending ? t("kb.processing") : t("kb.trainWithText")}
        </button>
      </div>

      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg">
        <h2 className="text-lg font-bold mb-4 text-[var(--color-foreground)]">{t("kb.trainFileSection")}</h2>

        <div
          className={`border-2 border-dashed rounded-lg p-10 text-center transition ${
            dragOver ? "border-[var(--color-primary)] bg-[var(--color-table-head)]" : "border-[var(--color-border)]"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          {file ? (
            <div className="text-[var(--color-foreground)]">
              {t("kb.trainFileSelected")} <strong>{file.name}</strong>
            </div>
          ) : (
            <div className="text-[var(--color-muted)]">{t("kb.trainFileDrop")}</div>
          )}
        </div>

        <div className="mt-4">
          <input
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block text-[var(--color-foreground)]"
          />
        </div>

        <button
          type="button"
          className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] px-4 py-2 rounded mt-5 hover:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={trainFile}
          disabled={trainFileMutation.isPending}
        >
          {trainFileMutation.isPending ? t("kb.processing") : t("kb.trainWithFile")}
        </button>
      </div>
    </div>
  );
}
