import { useTranslation } from "../../../i18n";
import Modal, { ModalHeader } from "../../../components/ui/Modal";
import { SystemSecurityBody } from "../pages/SettingsPage";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { t } = useTranslation();

  return (
    <Modal open={isOpen} onClose={onClose} panelClassName="max-w-md bg-[var(--color-background)]">
      <ModalHeader
        eyebrow={t("settings.systemLabel")}
        title={t("settings.title")}
        description={t("settings.pageIntro")}
      />
      <SystemSecurityBody onSaved={onClose} onCancel={onClose} />
    </Modal>
  );
}
