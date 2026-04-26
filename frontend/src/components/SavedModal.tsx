import { useTranslation } from "../i18n";
import Button from "./ui/Button";
import Modal, { ModalFooter } from "./ui/Modal";

interface SavedModalProps {
  open: boolean;
  onClose: () => void;
  message?: string;
}

export function SavedModal({ open, onClose, message }: SavedModalProps) {
  const { t } = useTranslation();
  return (
    <Modal open={open} onClose={onClose} panelClassName="max-w-md">
        <p className="text-[var(--color-foreground)] mb-6">
          {message ?? t("profile.saved")}
        </p>
        <ModalFooter>
          <Button variant="secondary" onClick={onClose}>
            {t("common.close")}
          </Button>
        </ModalFooter>
    </Modal>
  );
}
