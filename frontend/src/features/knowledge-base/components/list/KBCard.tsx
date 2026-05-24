import Button from "../../../../components/ui/Button";
import type { KbItem } from "../../hooks/useKb";
import { formatBytes, formatThousands, isDeletedKb, metricValue } from "./kbListUtils";

type KBCardProps = {
  kb: KbItem;
  canManage: boolean;
  canDeleteKb: boolean;
  billingRestricted: boolean;
  actionLoading: boolean;
  t: (key: string) => string;
  onTrainingLog: (kb: KbItem) => void;
  onSettings: (kb: KbItem) => void;
  onDelete: (kb: KbItem) => void;
};

export default function KBCard({
  kb,
  canManage,
  canDeleteKb,
  billingRestricted,
  actionLoading,
  t,
  onTrainingLog,
  onSettings,
  onDelete,
}: KBCardProps) {
  const deleted = isDeletedKb(kb);
  return (
    <div className={`grid gap-4 px-5 py-4 md:grid-cols-[0.75fr_2fr_0.6fr] md:items-center ${deleted ? "text-[var(--color-muted)]" : ""}`}>
      <div className="min-w-0">
        <p className={`truncate font-medium ${deleted ? "text-[var(--color-muted)]" : "text-[var(--color-foreground)]"}`}>{kb.name}</p>
        <span className={`mt-1 inline-block rounded-lg px-2 py-0.5 text-xs font-medium text-white ${deleted ? "bg-[var(--color-danger-text)]" : "bg-[var(--color-success-text)]"}`}>
          {deleted ? t("kb.statusDeleted") : t("kb.statusActive")}
        </span>
      </div>

      <div className="text-sm text-[var(--color-muted)]">
        <div className="rounded-lg bg-[var(--color-card-muted)] px-3 py-2 text-xs leading-5 text-[var(--color-muted-foreground)]">
          <span className={`font-medium ${deleted ? "text-[var(--color-muted)]" : "text-[var(--color-foreground)]"}`}>
            {t("kb.metricCharacters")}: {formatThousands(metricValue(kb, "training_char_count"))}
          </span>
          <span className="mx-2">|</span>
          {t("kb.metricSize")}: {formatBytes(metricValue(kb, "total_bytes"))}
          <span className="mx-2">|</span>
          {t("kb.metricFile")}: {formatBytes(metricValue(kb, "file_bytes"))}
          <span className="mx-2">|</span>
          {t("kb.metricDatabase")}: {formatBytes(metricValue(kb, "database_bytes"))}
          {canManage && !deleted ? (
            <div className="mt-1">
              <button
                type="button"
                onClick={() => onTrainingLog(kb)}
                className="font-medium text-[var(--color-muted)] hover:text-[var(--color-muted-foreground)] hover:underline"
                title={t("kb.actionTrainingLog")}
                aria-label={t("kb.actionTrainingLog")}
              >
                {t("kb.actionLog")} →
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        {deleted ? (
          <div className="w-full rounded-lg bg-[var(--color-card-muted)] px-3 py-2 text-center text-sm font-medium text-[var(--color-muted-foreground)]">
            {t("kb.deletedNoActions")}
          </div>
        ) : null}
        {canManage && !billingRestricted && !deleted ? (
          <Button type="button" variant="secondary" onClick={() => onSettings(kb)} disabled={actionLoading} size="sm">
            {t("kb.actionSettings")}
          </Button>
        ) : null}
        {canDeleteKb && !billingRestricted && !deleted ? (
          <Button type="button" variant="danger" onClick={() => onDelete(kb)} disabled={actionLoading} size="sm">
            {t("kb.actionDelete")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
