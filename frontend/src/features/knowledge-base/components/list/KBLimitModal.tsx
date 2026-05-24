import Button from "../../../../components/ui/Button";
import Modal from "../../../../components/ui/Modal";

type KBLimitModalProps = {
  open: boolean;
  max: number | null;
  used: number;
  t: (key: string) => string;
  onClose: () => void;
  onViewPackages: () => void;
};

export default function KBLimitModal({ open, max, used, t, onClose, onViewPackages }: KBLimitModalProps) {
  return (
    <Modal open={open} onClose={onClose} closeOnOverlay panelClassName="max-w-md">
      <h2 id="kb-limit-title" className="text-xl font-bold text-[var(--color-foreground)] mb-3">
        {t("kb.limitReachedTitle")}
      </h2>
      <div className="space-y-3 text-sm text-[var(--color-muted-foreground)]">
        <p>
          {t("kb.limitReachedMessage")
            .replace("{{max}}", String(max ?? t("kb.limitByPlan")))
            .replace("{{used}}", String(used))}
        </p>
        <p>{t("kb.limitReachedHint")}</p>
      </div>
      <div className="mt-6 flex flex-col-reverse sm:flex-row gap-2 sm:justify-end">
        <Button type="button" variant="secondary" size="lg" className="w-full sm:w-auto" onClick={onClose}>
          {t("common.back")}
        </Button>
        <Button type="button" size="lg" className="w-full sm:w-auto" onClick={onViewPackages}>
          {t("kb.viewPackages")}
        </Button>
      </div>
    </Modal>
  );
}
