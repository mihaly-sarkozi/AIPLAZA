// frontend/src/features/settings/components/SettingsModal.tsx
// Feladat: Legacy settings modal wrapper, amely a shellt ágyazza modalba kompatibilitási okból.
// Sárközi Mihály - 2026.05.29

import { useTranslation } from "../../../i18n";
import Modal, { ModalHeader } from "../../../components/ui/Modal";
import { useAuthStore } from "../../../store/authStore";
import { canAccessSettings } from "../model/settingsPermissions";
import SettingsShell from "../shell/SettingsShell";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);

  return (
    <Modal open={isOpen} onClose={onClose} panelClassName="max-w-md bg-[var(--color-background)]">
      <ModalHeader
        eyebrow={t("settings.systemLabel")}
        title={t("settings.title")}
        description={t("settings.pageIntro")}
      />
      {user && canAccessSettings(user) ? <SettingsShell user={user} /> : null}
    </Modal>
  );
}
