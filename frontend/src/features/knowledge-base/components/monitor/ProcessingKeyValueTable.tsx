import { useTranslation } from "../../../../i18n";
import type { FlatSummaryRow } from "../../utils/processingMonitorUtils";

type ProcessingKeyValueTableProps = {
  title: string;
  rows: FlatSummaryRow[];
  emptyLabel: string;
};

function labelForKey(t: (key: string) => string, labelKey: string): string {
  const translated = t(`kb.processingMonitor.fields.${labelKey}`);
  if (translated !== `kb.processingMonitor.fields.${labelKey}`) return translated;
  return labelKey.replace(/_/g, " ").replace(/\./g, " / ");
}

export default function ProcessingKeyValueTable({ title, rows, emptyLabel }: ProcessingKeyValueTableProps) {
  const { t } = useTranslation();
  if (!rows.length) {
    return (
      <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
        <h3 className="text-sm font-semibold text-[var(--color-foreground)]">{title}</h3>
        <p className="mt-2 text-sm text-[var(--color-muted)]">{emptyLabel}</p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
      <h3 className="mb-3 text-sm font-semibold text-[var(--color-foreground)]">{title}</h3>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-[var(--color-muted)]">
              <th className="px-3 py-2 font-medium">{t("kb.processingMonitor.table.field")}</th>
              <th className="px-3 py-2 font-medium">{t("kb.processingMonitor.table.value")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-b border-[var(--color-border)]/70 align-top last:border-0">
                <td className="px-3 py-2 font-medium text-[var(--color-foreground)]">{labelForKey(t, row.labelKey)}</td>
                <td className="px-3 py-2 whitespace-pre-wrap break-words text-[var(--color-muted)]">{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
