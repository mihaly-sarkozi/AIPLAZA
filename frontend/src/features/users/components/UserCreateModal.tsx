import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { RoleFormData } from "./rolesTypes";

type UserCreateModalProps = {
  open: boolean;
  formData: RoleFormData;
  formError: string | null;
  actionLoading: boolean;
  t: (key: string) => string;
  setFormData: (data: RoleFormData) => void;
  clearFormError: () => void;
  onClose: () => void;
  onCreate: () => void;
};

export default function UserCreateModal({
  open,
  formData,
  formError,
  actionLoading,
  t,
  setFormData,
  clearFormError,
  onClose,
  onCreate,
}: UserCreateModalProps) {
  return (
    <Modal open={open} onClose={onClose} panelClassName="max-w-md">
      <ModalHeader title={t("roles.modalNewTitle")} description={t("roles.modalNewHint")} />
      {formError ? <Alert tone="error" className="mb-4">{formError}</Alert> : null}
      <div className="space-y-4">
        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelName")}{t("common.required")}</label>
          <input
            type="text"
            value={formData.name}
            onChange={(event) => {
              setFormData({ ...formData, name: event.target.value });
              clearFormError();
            }}
            className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
            placeholder={t("roles.placeholderName")}
            maxLength={100}
            required
          />
        </div>
        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelEmail")}{t("common.required")}</label>
          <input
            type="email"
            value={formData.email}
            onChange={(event) => {
              setFormData({ ...formData, email: event.target.value });
              clearFormError();
            }}
            className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
            placeholder={t("roles.placeholderInviteEmail")}
            maxLength={100}
            required
          />
        </div>
        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelRole")}</label>
          <select
            value={formData.role}
            onChange={(event) => setFormData({ ...formData, role: event.target.value as "user" | "admin" })}
            className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
          >
            <option value="user">{t("roles.roleUser")}</option>
            <option value="admin">{t("roles.roleAdmin")}</option>
          </select>
        </div>
      </div>
      <ModalFooter>
        <Button type="button" onClick={onClose} variant="secondary" disabled={actionLoading}>
          {t("common.cancel")}
        </Button>
        <Button type="button" onClick={onCreate} disabled={actionLoading}>
          {actionLoading ? t("common.loading") : t("common.create")}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
