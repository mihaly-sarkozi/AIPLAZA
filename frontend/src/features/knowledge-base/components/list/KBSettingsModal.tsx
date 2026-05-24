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
  settingsPermsLoading: boolean;
  settingsSaveLoading: boolean;
  actionLoading: boolean;
  usersWithPerms: KbPermissionRow[];
  currentUserId?: number;
  t: (key: string) => string;
  setFormData: (data: KbFormData) => void;
  setPiiDepersonalizationEnabled: (enabled: boolean) => void;
  clearFormError: () => void;
  onPermissionChange: (userId: number, permission: string) => void;
  onBulkPermissionChange: (enabled: boolean) => void;
  onClose: () => void;
  onSave: () => void;
};

export default function KBSettingsModal({
  kb,
  formData,
  formError,
  piiDepersonalizationEnabled,
  settingsPermsLoading,
  settingsSaveLoading,
  actionLoading,
  usersWithPerms,
  currentUserId,
  t,
  setFormData,
  setPiiDepersonalizationEnabled,
  clearFormError,
  onPermissionChange,
  onBulkPermissionChange,
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
        <label
          className="!mb-0 !inline-flex !items-center rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm text-[var(--color-foreground)]"
          style={{ gap: "8px" }}
        >
          <input
            type="checkbox"
            checked={piiDepersonalizationEnabled}
            onChange={(event) => setPiiDepersonalizationEnabled(event.target.checked)}
            className="kb-perm-checkbox !mt-0 self-center"
          />
          <span className="leading-5 align-middle">PII deperszonalizáció az LLM felé (ajánlott)</span>
        </label>
      </div>

      <h3 className="text-sm font-semibold text-[var(--color-foreground)] mb-2">{t("kb.permissionsTitle")}</h3>
      {settingsPermsLoading ? (
        <p className="text-[var(--color-muted)]">{t("common.loading")}</p>
      ) : (
        <>
          <KBPermissionTable
            users={usersWithPerms}
            currentUserId={currentUserId}
            t={t}
            onChange={onPermissionChange}
            onBulkChange={onBulkPermissionChange}
            mode="settings"
          />
          <ModalFooter className="mt-4">
            <Button type="button" onClick={onClose} variant="secondary" disabled={actionLoading}>
              {t("common.cancel")}
            </Button>
            <Button type="button" onClick={onSave} disabled={settingsSaveLoading}>
              {settingsSaveLoading ? t("common.loading") : t("common.save")}
            </Button>
          </ModalFooter>
        </>
      )}
    </Modal>
  );
}
