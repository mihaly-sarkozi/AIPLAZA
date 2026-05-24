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
  return (
    <Modal open={Boolean(user)} onClose={onClose} panelClassName="max-w-md">
      <ModalHeader title={t("roles.modalEditTitle")} />
      {formError ? <Alert tone="error" className="mb-4">{formError}</Alert> : null}
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <label htmlFor="edit-active-toggle" className="text-[var(--color-label)] font-medium cursor-pointer">
            {t("roles.labelActive")}
          </label>
          <button
            id="edit-active-toggle"
            type="button"
            role="switch"
            aria-checked={formData.is_active}
            disabled={isOwner || user.pending_registration === true}
            onClick={() => (isOwner || user.pending_registration ? undefined : setFormData({ ...formData, is_active: !formData.is_active }))}
            className={`relative inline-flex h-6 w-11 shrink-0 rounded-full p-0.5 transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-neutral-600 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none ${formData.is_active ? "bg-[var(--color-primary)]" : "bg-[var(--color-border)]"}`}
          >
            <span
              className={`inline-block h-5 w-5 rounded-full bg-white shadow-sm ring-0 transform transition-transform duration-200 ease-in-out ${formData.is_active ? "translate-x-5" : "translate-x-0"}`}
              aria-hidden
            />
          </button>
        </div>
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
            <p className="text-[var(--color-foreground)] bg-[var(--color-table-head)] border border-[var(--color-border)] p-2 rounded text-sm">
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
          {isOwner ? (
            <p className="text-[var(--color-foreground)] bg-[var(--color-table-head)] border border-[var(--color-border)] p-2 rounded text-sm">
              {t("roles.roleOwner")}
              <span className="block text-xs text-[var(--color-muted)] mt-1">{t("roles.ownerOnlyName")}</span>
            </p>
          ) : user.id === currentUserId ? (
            <p className="text-[var(--color-foreground)] bg-[var(--color-table-head)] border border-[var(--color-border)] p-2 rounded text-sm">
              {user.role === "owner" ? t("roles.roleOwner") : user.role}
              <span className="block text-xs text-[var(--color-muted)] mt-1">{t("roles.ownRoleNoEdit")}</span>
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
