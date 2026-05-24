import Button from "../../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../../components/ui/Modal";
import type { KbItem } from "../../hooks/useKb";

type KBDeleteConfirmModalProps = {
  kb: KbItem | null;
  deleteTypeName: string;
  actionLoading: boolean;
  t: (key: string) => string;
  setDeleteTypeName: (value: string) => void;
  onClose: () => void;
  onDelete: () => void;
};

export default function KBDeleteConfirmModal({
  kb,
  deleteTypeName,
  actionLoading,
  t,
  setDeleteTypeName,
  onClose,
  onDelete,
}: KBDeleteConfirmModalProps) {
  if (!kb) return null;
  return (
    <Modal open={Boolean(kb)} onClose={onClose} panelClassName="max-w-md">
      <ModalHeader title={t("kb.confirmDelete")} />
      <p className="text-sm text-[var(--color-muted)] mb-3">{t("kb.confirmDeleteTypeName").replace("{{name}}", kb.name)}</p>
      <div className="mb-4 rounded-lg border border-[var(--color-danger-border)] bg-[var(--color-danger-bg)] px-3 py-2 text-sm leading-relaxed text-[var(--color-danger-text)]">
        {t("kb.confirmDeleteTrainingFilesWarning")}
      </div>
      <input
        type="text"
        value={deleteTypeName}
        onChange={(event) => setDeleteTypeName(event.target.value)}
        placeholder={kb.name}
        className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded mb-4"
      />
      <ModalFooter>
        <Button type="button" onClick={onClose} variant="secondary" disabled={actionLoading}>
          {t("common.cancel")}
        </Button>
        <Button type="button" onClick={onDelete} variant="danger" disabled={actionLoading || deleteTypeName.trim() !== kb.name}>
          {actionLoading ? t("common.loading") : t("common.delete")}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
