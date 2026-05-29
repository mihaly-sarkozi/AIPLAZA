import Alert from "../../../components/ui/Alert";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../api/services/settingsService";
import type { IngestItem, IngestRun } from "../services";
import {
  formatInteger,
  formatModuleProgress,
  formatTimestamp,
  getItemKindLabel,
  getItemProgressPercent,
  getItemProcessingSummary,
  getRunProgressLabel,
  getRunProgressPercent,
  getRunProgressSummary,
  getStatusBadgeClass,
  getStatusLabel,
} from "../pages/ingestLogHelpers";
import { DetailField, ProgressBar } from "./IngestDetailShared";

type KbLike = { name?: string | null } | null | undefined;

type IngestRunProgressProps = {
  run: IngestRun;
  selectedItem: IngestItem | null;
  kb: KbLike;
  parserErrorMessage: string;
  locale?: string;
  timezone?: SettingsTimezone | string;
  dateFormat?: SettingsDateFormat;
  timeFormat?: SettingsTimeFormat;
};

export default function IngestRunProgress({
  run,
  selectedItem,
  kb,
  parserErrorMessage,
  locale = "hu",
  timezone,
  dateFormat,
  timeFormat,
}: IngestRunProgressProps) {
  const timestampOptions = { locale, timezone, dateFormat, timeFormat };
  const processingSummary = getItemProcessingSummary(selectedItem);
  const parserModule = processingSummary.modules.parser;
  const interpretationModule = processingSummary.modules.sentence_interpretation;
  const evaluationModule = processingSummary.modules.sentence_evaluation;
  const documentProgress = processingSummary.document_progress;
  const runProgressSummary = getRunProgressSummary(run);
  const runProgressPercent = getRunProgressPercent(run);
  const runProgressLabel = getRunProgressLabel(run);
  const selectedItemProgressPercent = getItemProgressPercent(selectedItem);
  const selectedItemCharCount = typeof selectedItem?.metadata?.char_count === "number" ? selectedItem.metadata.char_count : 0;
  const selectedItemSentenceCount = typeof selectedItem?.metadata?.sentence_count === "number" ? selectedItem.metadata.sentence_count : 0;
  const runCharCount = typeof run?.metadata?.total_char_count === "number" ? run.metadata.total_char_count : selectedItemCharCount;
  const runSentenceCount =
    typeof run?.metadata?.total_sentence_count === "number" ? run.metadata.total_sentence_count : selectedItemSentenceCount;

  return (
    <>
      <div className="grid gap-4 md:grid-cols-4">
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Státusz</div>
          <div className="mt-3">
            <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusBadgeClass(run.status)}`}>
              {getStatusLabel(run.status)}
            </span>
          </div>
        </div>
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Timestamp</div>
          <div className="mt-2 text-lg font-semibold">{formatTimestamp(selectedItem?.created_at ?? run.created_at, timestampOptions)}</div>
        </div>
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Tanítás típusa</div>
          <div className="mt-2 text-lg font-semibold">{getItemKindLabel(selectedItem)}</div>
        </div>
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Tanító</div>
          <div className="mt-2 text-lg font-semibold">{selectedItem?.created_by_label || run.created_by_label || "Ismeretlen"}</div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Beolvasott karakterek</div>
          <div className="mt-2 text-2xl font-semibold">{formatInteger(runCharCount)}</div>
        </div>
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Mondatok száma</div>
          <div className="mt-2 text-2xl font-semibold">{formatInteger(runSentenceCount)}</div>
        </div>
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Feldolgozás</div>
          <div className="mt-2 text-2xl font-semibold">Feldolgozva {selectedItem ? selectedItemProgressPercent : runProgressPercent}%</div>
        </div>
      </div>

      <div className="app-surface p-5">
        <h2 className="text-xl font-semibold">Run folyamat</h2>
        <div className="mt-4 rounded-lg border border-[var(--color-border)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Összesített előrehaladás</div>
              <div className="mt-2 text-sm text-[var(--color-foreground)]">{runProgressLabel || "Még nincs részletes run progress adat."}</div>
            </div>
            <div className="text-sm font-medium text-[var(--color-foreground)]">{runProgressPercent}%</div>
          </div>
          <ProgressBar value={runProgressPercent} />
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4 text-sm text-[var(--color-muted)]">
            <div>Aktív rekord: {runProgressSummary.active_item_label || selectedItem?.display_name || "n/a"}</div>
            <div>Aktív modul: {runProgressSummary.active_module_label || runProgressSummary.active_module || "n/a"}</div>
            <div>
              Kész elemek: {typeof runProgressSummary.terminal_items === "number" ? runProgressSummary.terminal_items : 0} /{" "}
              {typeof runProgressSummary.total_items === "number" ? runProgressSummary.total_items : run.batch_size}
            </div>
            <div>Megállt itt: {runProgressSummary.stopped_at || "n/a"}</div>
          </div>
        </div>
      </div>

      <div className="app-surface p-5">
        <h2 className="text-xl font-semibold">Fő adatok</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <DetailField label="Tudástár" value={kb?.name || "Ismeretlen tudástár"} />
          <DetailField label="Run azonosító" value={run.id} />
          <DetailField label="Item azonosító" value={selectedItem?.id || "n/a"} />
          <DetailField label="Bemeneti csatorna" value={run.input_channel} />
          <DetailField label="Pipeline route" value={selectedItem?.pipeline_route || run.pipeline_route} />
          <DetailField label="Progress" value={selectedItem?.progress_message || "Még nincs részletes progress üzenet."} />
          <DetailField label="Parser futás" value={String(selectedItem?.metadata?.parser_run_id ?? "Még nincs parser run azonosító.")} />
          <DetailField label="Dokumentum" value={String(selectedItem?.metadata?.document_id ?? "Még nincs dokumentum azonosító.")} />
          <DetailField label="Mondatszám" value={formatInteger(selectedItemSentenceCount)} />
          <DetailField label="Karakterszám" value={formatInteger(selectedItemCharCount)} />
          <DetailField label="Tanító" value={selectedItem?.created_by_label || run.created_by_label || "Ismeretlen"} />
          <DetailField label="Megnevezés" value={selectedItem?.display_name || selectedItem?.title || run.id} />
          <DetailField label="Tartalom / forrás" value={selectedItem ? selectedItem.origin || selectedItem.title : "n/a"} />
          <DetailField label="Origin" value={selectedItem?.origin || "n/a"} />
          <DetailField label="Létrehozva" value={formatTimestamp(run.created_at, timestampOptions)} />
          <DetailField label="Frissítve" value={formatTimestamp(selectedItem?.updated_at ?? run.updated_at, timestampOptions)} />
          <DetailField label="Hiba" value={parserErrorMessage || "Nincs"} />
        </div>
      </div>

      <div className="app-surface p-5">
        <h2 className="text-xl font-semibold">Részmodul állapot</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <DetailField label="Parser" value={formatModuleProgress(parserModule)} />
          <DetailField label="Mondatértelmezés" value={formatModuleProgress(interpretationModule)} />
          <DetailField label="Mondatértékelés" value={formatModuleProgress(evaluationModule)} />
        </div>
        {parserErrorMessage ? (
          <div className="mt-4">
            <Alert tone="error">
              <div className="font-medium">Parser hiba</div>
              <div className="mt-1 text-sm">{parserErrorMessage}</div>
            </Alert>
          </div>
        ) : null}
        <div className="mt-4 rounded-lg border border-[var(--color-border)] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Dokumentum készültség</div>
              <div className="mt-2 text-sm text-[var(--color-foreground)]">
                {documentProgress?.label || "Még nincs részletes dokumentumarányos készültség."}
              </div>
            </div>
            <div className="text-sm font-medium text-[var(--color-foreground)]">{documentProgress?.progress_percent ?? 0}%</div>
          </div>
          <ProgressBar value={documentProgress?.progress_percent ?? 0} />
          <div className="mt-3 text-sm text-[var(--color-muted)]">
            Fázis: {documentProgress?.phase || processingSummary.overall_status || "queued"}
            {documentProgress && typeof documentProgress.processed_parts === "number" && typeof documentProgress.total_parts === "number"
              ? ` | ${documentProgress.processed_parts} / ${documentProgress.total_parts}`
              : ""}
          </div>
        </div>
      </div>
    </>
  );
}
