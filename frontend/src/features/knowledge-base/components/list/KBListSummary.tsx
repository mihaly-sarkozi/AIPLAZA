import { formatBytes, formatThousands } from "./kbListUtils";

type KBListSummaryProps = {
  totalKnowledgeBases: number;
  totalStorageBytes: number;
  totalFileBytes: number;
  totalDatabaseBytes: number;
  totalTrainingChars: number;
  t: (key: string) => string;
};

export default function KBListSummary({
  totalKnowledgeBases,
  totalStorageBytes,
  totalFileBytes,
  totalDatabaseBytes,
  totalTrainingChars,
  t,
}: KBListSummaryProps) {
  return (
    <dl className="grid grid-cols-3 gap-x-3 gap-y-2 rounded-2xl bg-[var(--color-card-muted)]/60 px-3 py-2 md:grid-cols-5 md:px-4">
      <SummaryItem label={t("kb.summaryTotal")} value={String(totalKnowledgeBases)} />
      <SummaryItem label={t("kb.summaryTotalSize")} value={formatBytes(totalStorageBytes)} />
      <SummaryItem label={t("kb.summaryFiles")} value={formatBytes(totalFileBytes)} />
      <SummaryItem label={t("kb.summaryDatabaseSize")} value={formatBytes(totalDatabaseBytes)} />
      <SummaryItem label={t("kb.summaryCharacters")} value={formatThousands(totalTrainingChars)} />
    </dl>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="truncate text-[10px] font-medium uppercase tracking-wide text-[var(--color-muted)] md:text-xs">{label}</dt>
      <dd className="mt-0.5 truncate text-sm font-semibold text-[var(--color-foreground)] md:text-base">{value}</dd>
    </div>
  );
}
