import { sanitizeMessage } from "../../../../utils/sanitize";
import type { ChatSource } from "./chatMessageTypes";
import { sourceDisplayLabel } from "../../utils/chatMessageFormatting";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../../api/services/settingsService";

type SourceTab = "sources" | "context_blocks" | "index_hits" | "prompt" | "raw" | "parts" | "provenance" | "debug";

type ChatSourceModalProps = {
  sourceTab: SourceTab;
  setSourceTab: (tab: SourceTab) => void;
  onClose: () => void;
  t: (key: string) => string;
  locale: string;
  timezone?: SettingsTimezone | string;
  dateFormat?: SettingsDateFormat;
  timeFormat?: SettingsTimeFormat;
  answerMode?: string;
  evidence: Array<Record<string, unknown>>;
  citedSourceIds: string[];
  promptContext?: Record<string, unknown>;
  sources: ChatSource[];
  contextBlocks?: Array<Record<string, unknown>>;
  matchedChunks?: Array<Record<string, unknown>>;
  citations?: string[];
  debugPayload?: Record<string, unknown> | null;
  sourceLoadingId: string | null;
  onDownloadSource: (sourceId: string | undefined) => void;
  context: {
    qaContext: string;
    latestQuestion: string;
    llmContextText: string;
    encodedLlmContextText: string;
    piiApplied: boolean | null;
    piiReason: string;
    rawContextSentToLlm: string;
    rawInputsBeforePii: Record<string, unknown> | null;
    contextComponents: Record<string, unknown> | null;
    answerInformationSources: Array<Record<string, unknown>>;
    indexDebug: object | null;
  };
};

function SourceTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-full border px-2.5 py-1 ${active ? "border-[var(--color-primary)] text-[var(--color-primary)]" : "border-[var(--color-border)] text-[var(--color-muted)]"}`}
    >
      {children}
    </button>
  );
}

export default function ChatSourceModal({
  sourceTab,
  setSourceTab,
  onClose,
  t,
  locale,
  timezone,
  dateFormat,
  timeFormat,
  answerMode,
  evidence,
  citedSourceIds,
  promptContext,
  sources,
  contextBlocks = [],
  matchedChunks = [],
  citations = [],
  debugPayload = null,
  sourceLoadingId,
  onDownloadSource,
  context,
}: ChatSourceModalProps) {
  return (
    <div className="fixed inset-0 z-[1100] flex items-center justify-center bg-black/55 p-4">
      <div className="max-h-[85vh] w-full max-w-3xl overflow-auto rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-[var(--color-foreground)] shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{t("chat.sourceFallback")} - AI prompt context</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-xs text-[var(--color-muted)] hover:bg-[var(--color-border)]/20"
          >
            Bezár
          </button>
        </div>
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          <SourceTabButton active={sourceTab === "sources"} onClick={() => setSourceTab("sources")}>Források</SourceTabButton>
          <SourceTabButton active={sourceTab === "context_blocks"} onClick={() => setSourceTab("context_blocks")}>Context blokkok</SourceTabButton>
          <SourceTabButton active={sourceTab === "index_hits"} onClick={() => setSourceTab("index_hits")}>Index találatok</SourceTabButton>
          <SourceTabButton active={sourceTab === "prompt"} onClick={() => setSourceTab("prompt")}>Prompt context</SourceTabButton>
          <SourceTabButton active={sourceTab === "debug"} onClick={() => setSourceTab("debug")}>Raw debug JSON</SourceTabButton>
          <SourceTabButton active={sourceTab === "raw"} onClick={() => setSourceTab("raw")}>Teljes nyers context</SourceTabButton>
          <SourceTabButton active={sourceTab === "parts"} onClick={() => setSourceTab("parts")}>Context összetevők</SourceTabButton>
          <SourceTabButton active={sourceTab === "provenance"} onClick={() => setSourceTab("provenance")}>Válaszinformáció forrása</SourceTabButton>
        </div>
        <div className="space-y-3 text-[12px] leading-relaxed">
          {sourceTab === "sources" ? (
            <div className="space-y-2">
              {citations.length > 0 ? (
                <div className="rounded-lg border border-[var(--color-border)] p-2 text-[var(--color-muted)]">
                  Citations: {citations.join(", ")}
                </div>
              ) : null}
              {sources.length === 0 ? <div className="text-[var(--color-muted)]">Nincs megjeleníthető forrás.</div> : null}
              {sources.map((source) => (
                <div key={`${source.source_id}-${source.point_id}`} className="rounded-lg border border-[var(--color-border)] p-2">
                  <div className="font-semibold">{sourceDisplayLabel(source, source.title || source.source_id || "forrás", locale, timezone, dateFormat, timeFormat)}</div>
                  <div className="mt-1 whitespace-pre-wrap text-[var(--color-muted)]">{sanitizeMessage(source.snippet || "")}</div>
                  <button
                    type="button"
                    disabled={sourceLoadingId === source.source_id}
                    onClick={() => onDownloadSource(source.source_id || source.point_id)}
                    className="mt-2 rounded border border-[var(--color-border)] px-2 py-1 text-xs"
                  >
                    Letöltés
                  </button>
                </div>
              ))}
            </div>
          ) : null}
          {sourceTab === "context_blocks" ? (
            <ContextBox title="Promptba került evidence blokkok" value={JSON.stringify(contextBlocks, null, 2)} />
          ) : null}
          {sourceTab === "index_hits" ? (
            <ContextBox title="Qdrant / hybrid index találatok" value={JSON.stringify(matchedChunks, null, 2)} />
          ) : null}
          {sourceTab === "prompt" ? (
            <ContextBox
              title="Végső prompt context"
              value={String(context.rawContextSentToLlm || context.encodedLlmContextText || context.llmContextText || "-")}
            />
          ) : null}
          {sourceTab === "debug" ? (
            <ContextBox title="Raw debug JSON" value={JSON.stringify(debugPayload || promptContext?.debug || {}, null, 2)} />
          ) : null}
          {sourceTab === "raw" ? (
            <div>
              <div className="mb-1 font-semibold">Az API híváskor AI-nak küldött teljes nyers tartalom</div>
              <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                {sanitizeMessage(
                  context.rawContextSentToLlm ||
                    (Array.isArray(promptContext?.messages_sent_to_llm) ? JSON.stringify(promptContext.messages_sent_to_llm, null, 2) : "-")
                )}
              </div>
              <div className="mb-1 mt-3 font-semibold">PII előtti nyers bemenet (validáláshoz)</div>
              <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">
                {sanitizeMessage(context.rawInputsBeforePii ? JSON.stringify(context.rawInputsBeforePii, null, 2) : "-")}
              </div>
            </div>
          ) : null}
          {sourceTab === "parts" ? (
            <>
              <ContextBox title="Alap context" value={String(context.contextComponents?.alap_context || context.llmContextText || "-")} />
              <ContextBox title="Előzmények (csak értelmezéshez, nem bizonyíték)" value={String(context.contextComponents?.elozmenyek || context.qaContext || "-")} />
              <ContextBox title="Kérdés" value={String(context.contextComponents?.kerdes || context.latestQuestion || "-")} />
              <ContextBox
                title="Válaszinformáció"
                value={JSON.stringify(
                  context.contextComponents?.valaszinformacio || { answer_mode: answerMode || "", evidence, cited_source_ids: citedSourceIds },
                  null,
                  2
                )}
              />
              <ContextBox title="AI-nak küldött deperszonalizált context" value={context.encodedLlmContextText || context.llmContextText || "-"} />
              <ContextBox
                title="PII deperszonalizáció állapota"
                value={`${context.piiApplied === true ? "lefutott" : context.piiApplied === false ? "nem futott" : "ismeretlen"}${context.piiReason ? ` - ${context.piiReason}` : ""}`}
              />
            </>
          ) : null}
          {sourceTab === "provenance" ? (
            <>
              <div>
                <div className="mb-1 font-semibold">Válaszinformáció kontextus-eredete</div>
                <div className="space-y-2">
                  {context.answerInformationSources.length > 0 ? (
                    context.answerInformationSources.map((row, idx) => (
                      <div key={`answer-src-${idx}`} className="rounded-lg border border-[var(--color-border)] p-2">
                        <div className="text-[11px] text-[var(--color-muted)]">
                          forrás: {sanitizeMessage(String(row.source_id || "-"))} | claim: {sanitizeMessage(String(row.claim_id || "-"))} | sentence:{" "}
                          {sanitizeMessage(String(row.sentence_id || "-"))}
                        </div>
                        <div className="mt-1 whitespace-pre-wrap">{sanitizeMessage(String(row.claim_text || row.sentence_text || ""))}</div>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-lg border border-[var(--color-border)] p-2 text-[var(--color-muted)]">Nincs dedikált answer-source mapping.</div>
                  )}
                </div>
              </div>
              <div>
                <div className="mb-1 font-semibold">Források</div>
                <div className="space-y-1">
                  {sources.map((source, idx) => (
                    <div key={`${source.kb_uuid}-${source.point_id}-${idx}`} className="leading-snug">
                      <span className="text-[var(--color-muted)]">
                        {sanitizeMessage(sourceDisplayLabel(source, t("chat.sourceFallback"), locale, timezone, dateFormat, timeFormat))}
                      </span>
                      <span className="ml-2 text-[var(--color-muted)]">•</span>
                      <button
                        type="button"
                        onClick={() => onDownloadSource(source.source_id)}
                        disabled={!source.source_id || sourceLoadingId === source.source_id}
                        className="ml-1 underline text-left text-[var(--color-primary)] hover:text-[var(--color-foreground)] disabled:opacity-60"
                      >
                        Tartalom
                      </button>
                    </div>
                  ))}
                </div>
              </div>
              <ContextBox title="Miért ezt találta? (index nézet)" value={context.indexDebug ? JSON.stringify(context.indexDebug, null, 2) : "Nincs index debug adat."} />
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ContextBox({ title, value }: { title: string; value: string }) {
  return (
    <div>
      <div className="mb-1 font-semibold">{title}</div>
      <div className="whitespace-pre-wrap rounded-lg border border-[var(--color-border)] p-2">{sanitizeMessage(value)}</div>
    </div>
  );
}
