import Alert from "../../../../components/ui/Alert";
import Button from "../../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../../components/ui/Modal";
import { KB_NAME_MAX_LENGTH, type KbFormData, type KbPermissionRow } from "./kbListUtils";
import KBPermissionTable from "./KBPermissionTable";

type KBCreateModalProps = {
  open: boolean;
  formData: KbFormData;
  formError: string | null;
  canManage: boolean;
  actionLoading: boolean;
  usersWithPerms: KbPermissionRow[];
  currentUserId?: number;
  t: (key: string) => string;
  setFormData: (data: KbFormData) => void;
  clearFormError: () => void;
  onPermissionChange: (userId: number, permission: string) => void;
  onClose: () => void;
  onSubmit: (event: React.FormEvent) => void;
};

export default function KBCreateModal({
  open,
  formData,
  formError,
  canManage,
  actionLoading,
  usersWithPerms,
  currentUserId,
  t,
  setFormData,
  clearFormError,
  onPermissionChange,
  onClose,
  onSubmit,
}: KBCreateModalProps) {
  return (
    <Modal open={open} onClose={onClose} panelClassName="max-w-2xl">
      <ModalHeader title={t("kb.modalNewTitle")} description={t("kb.modalNewHint")} />
      {formError ? <Alert tone="error" className="mb-4">{formError}</Alert> : null}
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("kb.labelName")}{t("common.required")}</label>
          <input
            type="text"
            value={formData.name}
            onChange={(event) => {
              setFormData({ ...formData, name: event.target.value });
              clearFormError();
            }}
            className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
            placeholder={t("kb.placeholderName")}
            maxLength={KB_NAME_MAX_LENGTH}
            required
          />
        </div>
        {canManage && usersWithPerms.length > 0 ? (
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-foreground)] mb-1">{t("kb.permissionsTitle")}</h3>
            <p className="text-xs text-[var(--color-muted)] mb-2">{t("kb.permissionsHint")}</p>
            <KBPermissionTable users={usersWithPerms} currentUserId={currentUserId} t={t} onChange={onPermissionChange} mode="create" />
          </div>
        ) : null}
        <ModalFooter>
          <Button type="button" onClick={onClose} variant="secondary" disabled={actionLoading}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={actionLoading}>
            {actionLoading ? t("common.loading") : t("common.save")}
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
