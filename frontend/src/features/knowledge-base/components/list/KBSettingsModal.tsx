import Alert from "../../../../components/ui/Alert";
import Button from "../../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../../components/ui/Modal";
import type { KbItem } from "../../hooks/useKb";
import { KB_NAME_MAX_LENGTH, type KbFormData, type KbPermissionRow } from "./kbListUtils";
import KBPermissionTable from "./KBPermissionTable";

type KBSettingsModalProps = {
  kb: KbItem | null;
  formData: KbFormData;
  formError: string | null;
  piiDepersonalizationEnabled: boolean;
  isPublic: boolean;
  publicEnabled: boolean;
  settingsPermsLoading: boolean;
  settingsSaveLoading: boolean;
  actionLoading: boolean;
  usersWithPerms: KbPermissionRow[];
  currentUserId?: number;
  t: (key: string) => string;
  setFormData: (data: KbFormData) => void;
  setPiiDepersonalizationEnabled: (enabled: boolean) => void;
  setPublicEnabled: (enabled: boolean) => void;
  clearFormError: () => void;
  onPermissionChange: (userId: number, permission: string) => void;
  onClose: () => void;
  onSave: () => void;
};

export default function KBSettingsModal({
  kb,
  formData,
  formError,
  piiDepersonalizationEnabled,
  isPublic,
  publicEnabled,
  settingsPermsLoading,
  settingsSaveLoading,
  actionLoading,
  usersWithPerms,
  currentUserId,
  t,
  setFormData,
  setPiiDepersonalizationEnabled,
  setPublicEnabled,
  clearFormError,
  onPermissionChange,
  onClose,
  onSave,
}: KBSettingsModalProps) {
  if (!kb) return null;
  return (
    <Modal open={Boolean(kb)} onClose={onClose} panelClassName="max-w-2xl">
      <ModalHeader eyebrow={t("nav.knowledgeBase")} title={t("kb.actionSettings")} description={t("kb.settingsUsageHint")} />
      {formError ? <Alert tone="error" className="mb-4">{formError}</Alert> : null}
      <div className="mb-5 space-y-4">
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
        <div className="flex items-center text-sm text-[var(--color-muted)]">
          <input
            id="kb-settings-pii-depersonalization"
            type="checkbox"
            checked={piiDepersonalizationEnabled}
            disabled={actionLoading || settingsSaveLoading}
            onChange={(event) => setPiiDepersonalizationEnabled(event.target.checked)}
            className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
          />
          <label htmlFor="kb-settings-pii-depersonalization" className="!mb-0 ml-2 !block translate-y-px cursor-pointer !font-medium leading-4 !text-[var(--color-muted)]">
            PII deperszonalizáció az LLM felé (ajánlott)
          </label>
        </div>
        <div className="flex items-center text-sm text-[var(--color-muted)]">
          <input
            id="kb-settings-public-enabled"
            type="checkbox"
            checked={publicEnabled}
            disabled={actionLoading || settingsSaveLoading}
            onChange={(event) => setPublicEnabled(event.target.checked)}
            className="kb-perm-checkbox focus:ring-0 focus:outline-none focus:shadow-none [&:focus]:outline-none [&:focus]:ring-0 [&:focus]:shadow-none"
          />
          <label htmlFor="kb-settings-public-enabled" className="!mb-0 ml-2 !block translate-y-px cursor-pointer !font-medium leading-4 !text-[var(--color-muted)]">
            Publikus (Bejelentkezés nélkül elérhető, pl. weboldalon)
          </label>
        </div>
      </div>

      {!isPublic ? (
        <>
          <h3 className="text-sm font-semibold text-[var(--color-foreground)] mb-2">{t("kb.permissionsTitle")}</h3>
          {settingsPermsLoading ? (
            <p className="text-[var(--color-muted)]">{t("common.loading")}</p>
          ) : (
            <KBPermissionTable
              users={usersWithPerms}
              currentUserId={currentUserId}
              t={t}
              onChange={onPermissionChange}
              mode="settings"
            />
          )}
        </>
      ) : null}
      <ModalFooter className="mt-4">
        <Button type="button" onClick={onClose} variant="secondary" disabled={actionLoading}>
          {t("common.cancel")}
        </Button>
        <Button type="button" onClick={onSave} disabled={settingsSaveLoading || (!isPublic && settingsPermsLoading)}>
          {settingsSaveLoading ? t("common.loading") : t("common.save")}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
