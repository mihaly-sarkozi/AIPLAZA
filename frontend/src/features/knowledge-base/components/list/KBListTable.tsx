import type { RefObject } from "react";
import type { KbItem } from "../../hooks/useKb";
import KBCard from "./KBCard";

type KBListTableProps = {
  items: KbItem[];
  canManage: boolean;
  canDeleteKb: boolean;
  billingRestricted: boolean;
  actionLoading: boolean;
  loadMoreRef: RefObject<HTMLDivElement | null>;
  t: (key: string) => string;
  onTrainingLog: (kb: KbItem) => void;
  onSettings: (kb: KbItem) => void;
  onDelete: (kb: KbItem) => void;
};

export default function KBListTable({
  items,
  canManage,
  canDeleteKb,
  billingRestricted,
  actionLoading,
  loadMoreRef,
  t,
  onTrainingLog,
  onSettings,
  onDelete,
}: KBListTableProps) {
  return (
    <section>
      <div className="app-table-wrap">
        <div className="app-table-head hidden grid-cols-[0.75fr_2fr_0.6fr] gap-4 !bg-[#efefef] px-5 py-3 text-sm font-medium !text-[var(--color-foreground)] md:grid">
          <div>{t("kb.tableName")}</div>
          <div>{t("kb.tableTraffic")}</div>
          <div>{t("kb.tableActions")}</div>
        </div>
        <div className="divide-y divide-[var(--color-border)]">
          {items.map((kb) => (
            <KBCard
              key={kb.uuid}
              kb={kb}
              canManage={canManage}
              canDeleteKb={canDeleteKb}
              billingRestricted={billingRestricted}
              actionLoading={actionLoading}
              t={t}
              onTrainingLog={onTrainingLog}
              onSettings={onSettings}
              onDelete={onDelete}
            />
          ))}
        </div>
        <div ref={loadMoreRef} className="h-8" />
      </div>
    </section>
  );
}
