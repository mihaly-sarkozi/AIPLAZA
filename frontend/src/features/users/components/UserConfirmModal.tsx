import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";

type UserConfirmModalProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  actionLoading: boolean;
  danger?: boolean;
  t: (key: string) => string;
  onClose: () => void;
  onConfirm: () => void;
};

export default function UserConfirmModal({
  open,
  title,
  description,
  confirmLabel,
  actionLoading,
  danger,
  t,
  onClose,
  onConfirm,
}: UserConfirmModalProps) {
  return (
    <Modal open={open} onClose={onClose} panelClassName="max-w-md">
      <ModalHeader title={title} description={description} />
      <ModalFooter>
        <Button type="button" onClick={onClose} variant="secondary" disabled={actionLoading}>
          {t("common.cancel")}
        </Button>
        <Button type="button" onClick={onConfirm} variant={danger ? "danger" : "primary"} disabled={actionLoading}>
          {actionLoading ? t("common.loading") : confirmLabel}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
