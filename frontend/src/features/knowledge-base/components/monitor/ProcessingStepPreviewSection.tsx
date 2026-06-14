import { useTranslation } from "../../../../i18n";
import type { PreviewTable } from "../../utils/stepSummaryDisplay";

type ProcessingStepPreviewSectionProps = {
  tables: PreviewTable[];
};

function PreviewTableBlock({ table }: { table: PreviewTable }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card-muted)]/40 p-4">
      <h4 className="mb-3 text-sm font-semibold text-[var(--color-foreground)]">
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
                      column.key === "from_label" ||
                      column.key === "snippet"
                        ? "font-medium text-[var(--color-foreground)]"
                        : ""
                    } ${column.align === "right" ? "text-right tabular-nums" : ""} ${
                      column.key === "snippet" ? "whitespace-pre-wrap max-w-2xl" : ""
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
          {t("kb.processingMonitor.previewTruncated").replace("{{count}}", String(table.truncateLimit ?? 30))}
        </p>
      ) : null}
    </div>
  );
}

export default function ProcessingStepPreviewSection({ tables }: ProcessingStepPreviewSectionProps) {
  const { t } = useTranslation();
  if (!tables.length) return null;

  return (
    <section className="mt-4 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
      <h3 className="mb-4 text-sm font-semibold text-[var(--color-foreground)]">
        {t("kb.processingMonitor.previewSectionTitle")}
      </h3>
      <div className="space-y-4">
        {tables.map((table) => (
          <PreviewTableBlock key={table.id} table={table} />
        ))}
      </div>
    </section>
  );
}
