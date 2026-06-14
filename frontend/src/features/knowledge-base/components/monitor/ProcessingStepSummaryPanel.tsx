import { useTranslation } from "../../../../i18n";
import type { PreviewTable, StepSummaryDisplay } from "../../utils/stepSummaryDisplay";
import ProcessingKeyValueTable from "./ProcessingKeyValueTable";

type ProcessingStepSummaryPanelProps = {
  title: string;
  display: StepSummaryDisplay;
  emptyLabel: string;
};

function PreviewTableSection({ table }: { table: PreviewTable }) {
  const { t } = useTranslation();
  return (
    <div>
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
        {t(`kb.processingMonitor.${table.titleKey}`)}
      </h4>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)] text-left text-[var(--color-muted)]">
              {table.columns.map((column) => (
                <th
                  key={column.key}
                  className={`px-3 py-2 font-medium ${column.align === "right" ? "text-right" : ""}`}
                >
                  {t(`kb.processingMonitor.${column.labelKey}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, index) => (
              <tr key={`${table.id}-${index}`} className="border-b border-[var(--color-border)]/70 align-top last:border-0">
                {table.columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-3 py-2 break-words text-[var(--color-muted)] ${
                      column.key === "name" ||
                      column.key === "term" ||
                      column.key === "text" ||
                      column.key === "from_label"
                        ? "font-medium text-[var(--color-foreground)]"
                        : ""
                    } ${column.align === "right" ? "text-right tabular-nums" : ""} ${
                      column.key === "snippet" ? "whitespace-pre-wrap" : ""
                    }`}
                  >
                    {row[column.key] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.truncated ? (
        <p className="mt-2 text-xs text-[var(--color-muted)]">
          {t("kb.processingMonitor.previewTruncated", { count: table.truncateLimit ?? 30 })}
        </p>
      ) : null}
    </div>
  );
}

export default function ProcessingStepSummaryPanel({
  title,
  display,
  emptyLabel,
}: ProcessingStepSummaryPanelProps) {
  const { t } = useTranslation();
  const hasRows = display.rows.length > 0;
  const hasPreviewTables = display.previewTables.length > 0;

  if (!hasRows && !hasPreviewTables) {
    return <ProcessingKeyValueTable title={title} rows={[]} emptyLabel={emptyLabel} />;
  }

  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
      <h3 className="mb-3 text-sm font-semibold text-[var(--color-foreground)]">{title}</h3>

      {hasRows ? (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-left text-[var(--color-muted)]">
                <th className="px-3 py-2 font-medium">{t("kb.processingMonitor.table.field")}</th>
                <th className="px-3 py-2 font-medium">{t("kb.processingMonitor.table.value")}</th>
              </tr>
            </thead>
            <tbody>
              {display.rows.map((row) => {
                const label = t(`kb.processingMonitor.fields.${row.labelKey}`);
                const fieldLabel =
                  label !== `kb.processingMonitor.fields.${row.labelKey}`
                    ? label
                    : row.labelKey.replace(/_/g, " ");
                return (
                  <tr key={row.key} className="border-b border-[var(--color-border)]/70 align-top last:border-0">
                    <td className="px-3 py-2 font-medium text-[var(--color-foreground)]">{fieldLabel}</td>
                    <td className="px-3 py-2 whitespace-pre-wrap break-words text-[var(--color-muted)]">{row.value}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      {hasPreviewTables ? (
        <div className={`space-y-4 ${hasRows ? "mt-4 border-t border-[var(--color-border)] pt-4" : ""}`}>
          {display.previewTables.map((table) => (
            <PreviewTableSection key={table.id} table={table} />
          ))}
        </div>
      ) : null}
    </section>
  );
}
