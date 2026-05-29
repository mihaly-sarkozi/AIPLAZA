import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { RoleFormData, RoleUser } from "./rolesTypes";

type UserEditModalProps = {
  user: RoleUser | null;
  currentUserId: number | undefined;
  formData: RoleFormData;
  formError: string | null;
  actionLoading: boolean;
  t: (key: string) => string;
  setFormData: (data: RoleFormData) => void;
  clearFormError: () => void;
  onClose: () => void;
  onSave: () => void;
};

export default function UserEditModal({
  user,
  currentUserId,
  formData,
  formError,
  actionLoading,
  t,
  setFormData,
  clearFormError,
  onClose,
  onSave,
}: UserEditModalProps) {
  if (!user) return null;
  const isOwner = user.role === "owner";
  const readOnlyFieldClass =
    "text-[var(--color-foreground)] bg-[var(--color-table-head)] border border-slate-200 dark:border-slate-700 p-2 rounded text-sm";
  return (
    <Modal open={Boolean(user)} onClose={onClose} panelClassName="max-w-md">
      <ModalHeader title={t("roles.modalEditTitle")} />
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
          <label className="block mb-1 text-[var(--color-label)]">
            {t("roles.labelEmail")}{!isOwner && user.id !== currentUserId ? t("common.required") : ""}
          </label>
          {isOwner ? (
            <p className={readOnlyFieldClass}>
              {user.email}
            </p>
          ) : (
            <input
              type="email"
              value={formData.email}
              onChange={(event) => {
                setFormData({ ...formData, email: event.target.value });
                clearFormError();
              }}
              className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
              placeholder={t("roles.placeholderEmail")}
              maxLength={100}
              required={user.id !== currentUserId}
            />
          )}
        </div>
        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("roles.labelRole")}</label>
          {isOwner || (user.role === "admin" && user.id === currentUserId) ? (
            <p className={readOnlyFieldClass}>
              {isOwner ? t("roles.roleOwner") : t("roles.roleAdmin")}
              {isOwner ? <span className="block text-xs text-[var(--color-muted)] mt-1">{t("roles.ownerOnlyName")}</span> : null}
            </p>
          ) : (
            <select
              value={formData.role}
              onChange={(event) => setFormData({ ...formData, role: event.target.value as "user" | "admin" })}
              className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
            >
              <option value="user">{t("roles.roleUser")}</option>
              <option value="admin">{t("roles.roleAdmin")}</option>
            </select>
          )}
        </div>
      </div>
      <ModalFooter>
        <Button type="button" onClick={onClose} variant="secondary" disabled={actionLoading}>
          {t("common.cancel")}
        </Button>
        <Button type="button" onClick={onSave} disabled={actionLoading}>
          {actionLoading ? t("common.loading") : t("common.save")}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
