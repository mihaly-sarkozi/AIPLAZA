import type { FlatSummaryRow } from "./processingMonitorUtils";
import { translateProcessingMonitorKey } from "./processingMonitorUtils";

export type PreviewTableColumn = {
  key: string;
  labelKey: string;
  align?: "left" | "right";
};

export type PreviewTable = {
  id: string;
  titleKey: string;
  columns: PreviewTableColumn[];
  rows: Record<string, string>[];
  truncated?: boolean;
  truncateLimit?: number;
};

export type StepSummaryDisplay = {
  rows: FlatSummaryRow[];
  previewTables: PreviewTable[];
};

type SummaryGroup = FlatSummaryRow["group"];

type StepFieldSpec = {
  key: string;
  format?: "percent" | "distribution" | "issueList" | "languageCode";
};

const PREVIEW_LIMIT = 30;

const INPUT_FIELDS_BY_STEP: Record<string, StepFieldSpec[]> = {
  EXTRACT_CONTENT: [{ key: "raw_ref" }, { key: "mime_type" }],
  NORMALIZE_PARTS: [{ key: "char_count" }],
  BUILD_CHUNKS: [{ key: "part_count" }],
  VALIDATE_RESULT: [{ key: "chunk_count" }],
  DETECT_LANGUAGE: [{ key: "chunk_count" }],
  EXTRACT_ENTITIES: [{ key: "chunk_count" }],
  ENRICH_LOCAL: [{ key: "chunk_count" }, { key: "language_code", format: "languageCode" }],
  EXTRACT_TEMPORAL: [{ key: "chunk_count" }],
  EXTRACT_SPATIAL: [{ key: "chunk_count" }],
  EXTRACT_PROCESS: [{ key: "chunk_count" }],
  BUILD_RELATIONSHIPS: [{ key: "entity_count" }],
  SCORE_KNOWLEDGE: [{ key: "chunk_count" }],
  VALIDATE_DISCOVERY: [{ key: "had_optional_failures" }],
  PIPELINE: [{ key: "chunk_count" }],
};

const OUTPUT_FIELDS_BY_STEP: Record<string, StepFieldSpec[]> = {
  EXTRACT_CONTENT: [
    { key: "char_count" },
    { key: "part_count" },
    { key: "extract_strategy" },
    { key: "page_count" },
    { key: "file_size_mb" },
  ],
  NORMALIZE_PARTS: [
    { key: "part_count" },
    { key: "normalized_parts" },
    { key: "failed_parts" },
    { key: "applied_rules" },
  ],
  BUILD_CHUNKS: [
    { key: "chunks_created" },
    { key: "table_chunks" },
    { key: "split_chunks" },
    { key: "merged_chunks" },
    { key: "ocr_chunks" },
    { key: "validation_warnings", format: "issueList" },
  ],
  VALIDATE_RESULT: [{ key: "status" }, { key: "missing", format: "issueList" }],
  DETECT_LANGUAGE: [
    { key: "chunks_checked" },
    { key: "document_language_code", format: "languageCode" },
    { key: "document_language_confidence", format: "percent" },
    { key: "language_distribution", format: "distribution" },
  ],
  EXTRACT_ENTITIES: [{ key: "entity_count" }, { key: "mention_count" }],
  ENRICH_LOCAL: [
    { key: "chunks_processed" },
    { key: "enrichments_created" },
    { key: "keywords_created" },
    { key: "topics_created" },
    { key: "fallback_language_chunks" },
    { key: "low_confidence_chunks" },
    { key: "language_distribution", format: "distribution" },
    { key: "content_type_distribution", format: "distribution" },
  ],
  EXTRACT_TEMPORAL: [{ key: "chunks_processed" }, { key: "temporal_mentions_created" }],
  EXTRACT_SPATIAL: [{ key: "chunks_processed" }, { key: "spatial_mentions_created" }],
  EXTRACT_PROCESS: [{ key: "chunks_processed" }, { key: "process_mentions_created" }],
  BUILD_RELATIONSHIPS: [
    { key: "relationships_created" },
    { key: "entity_count" },
    { key: "topic_count" },
    { key: "keyword_count" },
    { key: "temporal_count" },
    { key: "spatial_count" },
    { key: "process_count" },
  ],
  SCORE_KNOWLEDGE: [{ key: "score_count" }],
  VALIDATE_DISCOVERY: [{ key: "status" }, { key: "warnings", format: "issueList" }],
  PIPELINE: [{ key: "status" }, { key: "warnings", format: "issueList" }],
  GENERATE: [{ key: "embedding_count" }, { key: "dimension" }],
  UPSERT: [{ key: "upserted_count" }, { key: "collection_name" }],
};

function formatPercent(value: unknown, locale: string): string {
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value ?? "—");
  const pct = num <= 1 ? num * 100 : num;
  return `${pct.toLocaleString(locale, { maximumFractionDigits: 1 })}%`;
}

function translateLanguageCode(t: (key: string) => string, code: string): string {
  const key = `kb.processingMonitor.languages.${code}`;
  const translated = t(key);
  if (translated !== key) return translated;
  return code;
}

function translatePartOrChunkType(t: (key: string) => string, kind: "partTypes" | "chunkTypes", value: string): string {
  const key = `kb.processingMonitor.${kind}.${value}`;
  const translated = t(key);
  if (translated !== key) return translated;
  return value.replace(/_/g, " ");
}

function translateRelation(t: (key: string) => string, relation: string): string {
  const key = `kb.processingMonitor.relations.${relation}`;
  const translated = t(key);
  if (translated !== key) return translated;
  return relation.replace(/_/g, " ");
}

function formatDistribution(value: unknown, t: (key: string) => string): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return "—";
  return Object.entries(value as Record<string, number>)
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([code, count]) => `${translateLanguageCode(t, code)}: ${count}`)
    .join(", ");
}

function formatIssueList(value: unknown, t: (key: string) => string): string {
  if (!Array.isArray(value) || !value.length) return "—";
  return value
    .map((item) => {
      const code = String(item);
      const translated = translateProcessingMonitorKey(t, code, "issue");
      return translated || code;
    })
    .join("; ");
}

function formatFieldValue(
  spec: StepFieldSpec,
  value: unknown,
  t: (key: string) => string,
  locale: string,
): string {
  if (value === null || value === undefined || value === "") return "—";
  switch (spec.format) {
    case "percent":
      return formatPercent(value, locale);
    case "distribution":
      return formatDistribution(value, t);
    case "issueList":
      return formatIssueList(value, t);
    case "languageCode":
      return translateLanguageCode(t, String(value));
    default:
      if (Array.isArray(value)) {
        return value.map(String).join(", ");
      }
      if (typeof value === "object") {
        return JSON.stringify(value);
      }
      return String(value);
  }
}

function pickFields(
  summary: Record<string, unknown>,
  specs: StepFieldSpec[] | undefined,
  group: SummaryGroup,
  t: (key: string) => string,
  locale: string,
): FlatSummaryRow[] {
  if (!specs?.length) return [];
  const rows: FlatSummaryRow[] = [];
  for (const spec of specs) {
    if (!(spec.key in summary)) continue;
    rows.push({
      key: spec.key,
      labelKey: spec.key,
      value: formatFieldValue(spec, summary[spec.key], t, locale),
      group,
    });
  }
  return rows;
}

function asObjectArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object");
}

function buildEntityTable(summary: Record<string, unknown>, t: (key: string) => string, locale: string): PreviewTable | null {
  const rows = asObjectArray(summary.entities)
    .map((item) => {
      const name = String(item.name ?? "").trim();
      if (!name) return null;
      return {
        name,
        type: translateProcessingMonitorKey(t, String(item.type ?? "other"), "entityType"),
        confidence: formatPercent(item.confidence, locale),
      };
    })
    .filter((row) => row !== null);
  if (!rows.length) return null;
  return {
    id: "entities",
    titleKey: "entityPreviewTitle",
    columns: [
      { key: "name", labelKey: "entityTable.name" },
      { key: "type", labelKey: "entityTable.type" },
      { key: "confidence", labelKey: "entityTable.confidence", align: "right" },
    ],
    rows,
    truncated: rows.length >= PREVIEW_LIMIT,
    truncateLimit: PREVIEW_LIMIT,
  };
}

function buildKeywordTable(summary: Record<string, unknown>, t: (key: string) => string, locale: string): PreviewTable | null {
  const rows = asObjectArray(summary.keywords)
    .map((item) => {
      const term = String(item.term ?? "").trim();
      if (!term) return null;
      return {
        term,
        language: translateLanguageCode(t, String(item.language_code ?? "")),
        confidence: formatPercent(item.confidence, locale),
      };
    })
    .filter((row) => row !== null);
  if (!rows.length) return null;
  return {
    id: "keywords",
    titleKey: "keywordPreviewTitle",
    columns: [
      { key: "term", labelKey: "keywordTable.term" },
      { key: "language", labelKey: "keywordTable.language" },
      { key: "confidence", labelKey: "keywordTable.confidence", align: "right" },
    ],
    rows,
    truncated: rows.length >= PREVIEW_LIMIT,
    truncateLimit: PREVIEW_LIMIT,
  };
}

function buildTopicTable(summary: Record<string, unknown>, _t: (key: string) => string, locale: string): PreviewTable | null {
  const rows = asObjectArray(summary.topics)
    .map((item) => {
      const name = String(item.name ?? item.topic_key ?? "").trim();
      if (!name) return null;
      return {
        name,
        topic_key: String(item.topic_key ?? ""),
        confidence: formatPercent(item.confidence, locale),
      };
    })
    .filter((row) => row !== null);
  if (!rows.length) return null;
  return {
    id: "topics",
    titleKey: "topicPreviewTitle",
    columns: [
      { key: "name", labelKey: "topicTable.name" },
      { key: "topic_key", labelKey: "topicTable.key" },
      { key: "confidence", labelKey: "topicTable.confidence", align: "right" },
    ],
    rows,
    truncated: rows.length >= PREVIEW_LIMIT,
    truncateLimit: PREVIEW_LIMIT,
  };
}

function buildMentionTable(
  summary: Record<string, unknown>,
  key: string,
  titleKey: string,
  locale: string,
  t: (key: string) => string,
  typeKey?: string,
): PreviewTable | null {
  const rows = asObjectArray(summary[key])
    .map((item) => {
      const text = String(item.text ?? item.process_name ?? "").trim();
      if (!text) return null;
      const row: Record<string, string> = {
        text,
        confidence: formatPercent(item.confidence, locale),
      };
      if (typeKey && item[typeKey]) {
        row.type = translateProcessingMonitorKey(t, String(item[typeKey]), "mentionType");
      }
      if (item.step_text) {
        row.step = String(item.step_text);
      }
      return row;
    })
    .filter((row): row is Record<string, string> => row !== null);
  if (!rows.length) return null;
  const columns: PreviewTableColumn[] = [{ key: "text", labelKey: "mentionTable.text" }];
  if (rows.some((row) => row.type)) {
    columns.push({ key: "type", labelKey: "mentionTable.type" });
  }
  if (rows.some((row) => row.step)) {
    columns.push({ key: "step", labelKey: "mentionTable.step" });
  }
  columns.push({ key: "confidence", labelKey: "mentionTable.confidence", align: "right" });
  return {
    id: key,
    titleKey,
    columns,
    rows,
    truncated: rows.length >= PREVIEW_LIMIT,
    truncateLimit: PREVIEW_LIMIT,
  };
}

function buildRelationshipTable(summary: Record<string, unknown>, locale: string, t: (key: string) => string): PreviewTable | null {
  const rows = asObjectArray(summary.relationships)
    .map((item) => {
      const fromLabel = String(item.from_label ?? "").trim();
      const toLabel = String(item.to_label ?? "").trim();
      if (!fromLabel || !toLabel) return null;
      return {
        from_label: fromLabel,
        relation: translateRelation(t, String(item.relation ?? "")),
        to_label: toLabel,
        confidence: formatPercent(item.confidence, locale),
      };
    })
    .filter((row) => row !== null);
  if (!rows.length) return null;
  return {
    id: "relationships",
    titleKey: "relationshipPreviewTitle",
    columns: [
      { key: "from_label", labelKey: "relationshipTable.from" },
      { key: "relation", labelKey: "relationshipTable.relation" },
      { key: "to_label", labelKey: "relationshipTable.to" },
      { key: "confidence", labelKey: "relationshipTable.confidence", align: "right" },
    ],
    rows,
    truncated: rows.length >= PREVIEW_LIMIT,
    truncateLimit: PREVIEW_LIMIT,
  };
}

function buildScoreTable(summary: Record<string, unknown>, t: (key: string) => string, locale: string): PreviewTable | null {
  const rows = asObjectArray(summary.scores)
    .map((item) => {
      const snippet = String(item.snippet ?? "").trim();
      if (!snippet && item.score == null) return null;
      return {
        chunk_index: item.chunk_index != null ? `#${item.chunk_index}` : "—",
        chunk_type: translatePartOrChunkType(t, "chunkTypes", String(item.chunk_type ?? "")),
        score: formatPercent(item.score, locale),
        snippet,
      };
    })
    .filter((row) => row !== null);
  if (!rows.length) return null;
  return {
    id: "scores",
    titleKey: "scorePreviewTitle",
    columns: [
      { key: "chunk_index", labelKey: "scoreTable.chunk" },
      { key: "chunk_type", labelKey: "scoreTable.type" },
      { key: "score", labelKey: "scoreTable.score", align: "right" },
      { key: "snippet", labelKey: "scoreTable.snippet" },
    ],
    rows,
    truncated: rows.length >= PREVIEW_LIMIT,
    truncateLimit: PREVIEW_LIMIT,
  };
}

function buildBlockTable(
  summary: Record<string, unknown>,
  key: "blocks" | "chunks",
  titleKey: string,
  t: (key: string) => string,
): PreviewTable | null {
  const items = asObjectArray(summary[key]);
  const rows = items
    .map((item, arrayIndex) => {
      const snippet = String(item.snippet ?? "").trim();
      if (!snippet) return null;
      const typeKind = key === "chunks" ? "chunkTypes" : "partTypes";
      const typeValue = String(item.chunk_type ?? item.part_type ?? "");
      const row: Record<string, string> = {
        index: key === "chunks" ? `#${item.index ?? arrayIndex + 1}` : `#${arrayIndex + 1}`,
        type: translatePartOrChunkType(t, typeKind, typeValue),
        snippet,
      };
      if (key === "chunks") {
        row.meta = [
          item.page != null ? `${t("kb.processingMonitor.blockTable.page")}: ${item.page}` : null,
          item.tokens != null ? `${t("kb.processingMonitor.blockTable.tokens")}: ${item.tokens}` : null,
          item.language_code ? translateLanguageCode(t, String(item.language_code)) : null,
        ]
          .filter(Boolean)
          .join(" · ");
      } else {
        row.meta = [
          item.page != null ? `${t("kb.processingMonitor.blockTable.page")}: ${item.page}` : null,
          item.char_count != null ? `${t("kb.processingMonitor.blockTable.chars")}: ${item.char_count}` : null,
        ]
          .filter(Boolean)
          .join(" · ");
      }
      return row;
    })
    .filter((row): row is Record<string, string> => row !== null);
  if (!rows.length) return null;
  return {
    id: key,
    titleKey,
    columns: [
      { key: "index", labelKey: key === "chunks" ? "blockTable.chunkIndex" : "blockTable.blockIndex" },
      { key: "type", labelKey: "blockTable.type" },
      { key: "meta", labelKey: "blockTable.meta" },
      { key: "snippet", labelKey: "blockTable.snippet" },
    ],
    rows,
    truncated: rows.length >= PREVIEW_LIMIT,
    truncateLimit: PREVIEW_LIMIT,
  };
}

function buildPreviewTables(
  step: string | undefined,
  summary: Record<string, unknown>,
  group: SummaryGroup,
  t: (key: string) => string,
  locale: string,
): PreviewTable[] {
  if (group !== "output" || !step) return [];
  const tables: PreviewTable[] = [];
  const add = (table: PreviewTable | null) => {
    if (table) tables.push(table);
  };

  switch (step) {
    case "EXTRACT_ENTITIES":
      add(buildEntityTable(summary, t, locale));
      break;
    case "ENRICH_LOCAL":
      add(buildKeywordTable(summary, t, locale));
      add(buildTopicTable(summary, t, locale));
      break;
    case "EXTRACT_TEMPORAL":
      add(buildMentionTable(summary, "temporal_mentions", "temporalPreviewTitle", locale, t, "type"));
      break;
    case "EXTRACT_SPATIAL":
      add(buildMentionTable(summary, "spatial_mentions", "spatialPreviewTitle", locale, t, "location_type"));
      break;
    case "EXTRACT_PROCESS":
      add(buildMentionTable(summary, "process_mentions", "processPreviewTitle", locale, t));
      break;
    case "BUILD_RELATIONSHIPS":
      add(buildRelationshipTable(summary, locale, t));
      break;
    case "SCORE_KNOWLEDGE":
      add(buildScoreTable(summary, t, locale));
      break;
    case "EXTRACT_CONTENT":
    case "NORMALIZE_PARTS":
      add(buildBlockTable(summary, "blocks", step === "EXTRACT_CONTENT" ? "extractedBlocksPreviewTitle" : "normalizedBlocksPreviewTitle", t));
      break;
    case "BUILD_CHUNKS":
      add(buildBlockTable(summary, "chunks", "chunkPreviewTitle", t));
      break;
    default:
      break;
  }
  return tables;
}

export function buildStepSummaryDisplay(
  step: string | undefined,
  summary: Record<string, unknown>,
  group: SummaryGroup,
  t: (key: string) => string,
  locale: string,
): StepSummaryDisplay {
  const specs = group === "input" ? INPUT_FIELDS_BY_STEP[step ?? ""] : OUTPUT_FIELDS_BY_STEP[step ?? ""];
  const rows = pickFields(summary, specs, group, t, locale);
  const previewTables = buildPreviewTables(step, summary, group, t, locale);
  return { rows, previewTables };
}
