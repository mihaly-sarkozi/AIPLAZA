type TrainingConfirmationPanelProps = {
  onCancel: () => void;
  onConfirm: () => void;
  t: (key: string) => string;
};

export default function TrainingConfirmationPanel({ onCancel, onConfirm, t }: TrainingConfirmationPanelProps) {
  return (
    <div className="mx-auto flex max-w-3xl items-start px-2 mb-[1px]">
      <div className="flex w-full justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-full border border-[var(--color-border)] bg-transparent px-3 py-1 text-xs font-medium text-[var(--color-muted)] hover:bg-[var(--color-border)]/20"
        >
          {t("chat.trainingStartCancel")}
        </button>
        <button
          type="button"
          onClick={onConfirm}
          className="rounded-full bg-[var(--color-primary)] px-3 py-1 text-xs font-medium text-[var(--color-on-primary)] hover:opacity-90"
        >
          {t("chat.trainingStartConfirm")}
        </button>
      </div>
    </div>
  );
}
