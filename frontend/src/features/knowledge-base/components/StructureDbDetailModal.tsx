import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { StructureDbDetail } from "../pages/ingestDetailTypes";

type StructureDbDetailModalProps = {
  detail: StructureDbDetail | null;
  onClose: () => void;
};

export default function StructureDbDetailModal({ detail, onClose }: StructureDbDetailModalProps) {
  return (
    <Modal open={Boolean(detail)} onClose={onClose} panelClassName="max-w-4xl">
      <ModalHeader title={detail?.title ?? "Részletek"} description={detail?.description ?? "A kiválasztott rekord teljes trace / DB részletei."} />
      <pre className="max-h-[65vh] overflow-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4 text-xs">
        {JSON.stringify(detail?.data ?? {}, null, 2)}
      </pre>
      <ModalFooter>
        <Button variant="secondary" onClick={onClose}>
          Bezárás
        </Button>
      </ModalFooter>
    </Modal>
  );
}
