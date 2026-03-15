import { useTranslation } from "../i18n";

interface SavedModalProps {
  open: boolean;
  onClose: () => void;
  message?: string;
}

export function SavedModal({ open, onClose, message }: SavedModalProps) {
  const { t } = useTranslation();
  if (!open) return null;
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-96 shadow-lg">
        <p className="text-[var(--color-foreground)] mb-6">
          {message ?? t("profile.saved")}
        </p>
        <div className="flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded text-[var(--color-foreground)] hover:bg-[var(--color-button-hover)] bg-[var(--color-card)] border border-[var(--color-border)] focus:outline-none"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
