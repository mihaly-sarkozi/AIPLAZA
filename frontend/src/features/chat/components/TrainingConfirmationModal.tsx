import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import { formatInteger } from "../utils/chatNumbers";

type TrainingConfirmationModalProps = {
  open: boolean;
  filename: string;
  characterCount: number;
  locale: string;
  onCancel: () => void;
  onConfirm: () => void;
  t: (key: string) => string;
};

export default function TrainingConfirmationModal({
  open,
  filename,
  characterCount,
  locale,
  onCancel,
  onConfirm,
  t,
}: TrainingConfirmationModalProps) {
  const charCountText = formatInteger(characterCount, locale);
  const description = `${t("chat.fileCharacterCount").replace("{{count}}", charCountText)} ${t("chat.trainingStartQuestion")}`;

  return (
    <Modal open={open} panelClassName="max-w-md">
      <ModalHeader title={filename} description={description} />
      <ModalFooter>
        <Button variant="secondary" onClick={onCancel}>
          {t("chat.trainingStartCancel")}
        </Button>
        <Button variant="primary" onClick={onConfirm}>
          {t("chat.trainingStartConfirm")}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
