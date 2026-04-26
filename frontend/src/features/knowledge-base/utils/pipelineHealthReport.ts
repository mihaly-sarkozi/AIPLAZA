import type {
  IngestRunTrace,
  IngestRunTraceCandidateSelection,
  IngestRunTraceClaim,
  IngestRunTraceLocalEntity,
  IngestRunTraceSearchProfile,
  IngestRunTraceSimilarityAnalysis,
  IngestRunTraceSentence,
  IngestRunTraceTechnicalMemoryChunk,
} from "../services";

export type PipelineModuleStatus = "OK" | "Warning" | "Missing" | "Not implemented" | "Needs review";

export type PipelineSummaryKey =
  | "sentences"
  | "mentions"
  | "claims"
  | "local_entities"
  | "technical_entities"
  | "technical_memory_chunks"
  | "search_profiles"
  | "candidate_selection_count"
  | "similarity_analysis_count"
  | "skipped_sentence_count"
  | "rejected_claim_count"
  | "unknown_entity_type_count"
  | "unknown_space_ratio"
  | "high_similarity_count"
  | "medium_similarity_count"
  | "low_similarity_count";

export type PipelineSummaryMetric = {
  key: PipelineSummaryKey;
  label: string;
  value: number | string | null;
  missing: boolean;
  tone: "neutral" | "good" | "warning" | "danger";
};

export type PipelineModuleHealth = {
  name: string;
  status: PipelineModuleStatus;
  detail: string;
};

export type PipelineIssue = {
  key: string;
  label: string;
  count: number;
  severity: "info" | "warning" | "danger";
  detail: string;
};

export type PipelineEntityRow = {
  id: string;
  name: string;
  type: string;
  claimsCount: number;
  coherence: number | null;
  timeMode: string;
  spaceMode: string;
  status: PipelineModuleStatus;
  evidenceCount: number;
  claims: string[];
  technicalMemorySummary: string;
  searchProfileCanonicalText: string;
  keywords: string[];
  evidenceIds: string[];
};

export type PipelineClaimRow = {
  id: string;
  sentence: string;
  subject: string;
  predicate: string;
  object: string;
  type: string;
  group: string;
  confidence: number;
  timeMode: string;
  spaceMode: string;
  subjectSource: string;
  warnings: string[];
};

export type PipelineCandidateRow = {
  id: string;
  candidateName: string;
  candidateType: string;
  score: number;
  band: string;
  reasons: string[];
  componentScores: Record<string, number>;
  source: "candidate_selection" | "similarity_analysis";
};

export type PipelineQuality = {
  skippedSentenceCount: number | null;
  rejectedClaimCount: number | null;
  unknownEntityTypeCount: number | null;
  unknownSpaceRatio: number | null;
  highSimilarityCount: number | null;
  mediumSimilarityCount: number | null;
  lowSimilarityCount: number | null;
  noiseClaimCount: number;
  metaClaimCount: number;
  unknownTypeClaimCount: number;
  relevantUnknownSpaceCount: number;
  carryoverSubjectErrorCount: number;
  weakDuplicateCount: number;
  lowCoherenceEntityCount: number;
  duplicateCandidateCount: number;
};

export type PipelineHealthReport = {
  source: "json" | "text";
  runId: string;
  sourceName: string;
  status: string;
  createdAt: string;
  summary: PipelineSummaryMetric[];
  quality: PipelineQuality;
  modules: PipelineModuleHealth[];
  issues: PipelineIssue[];
  local_entities: PipelineEntityRow[];
  technical_entities: PipelineEntityRow[];
  technical_memory_chunks: IngestRunTraceTechnicalMemoryChunk[];
  search_profiles: IngestRunTraceSearchProfile[];
  candidate_selection: PipelineCandidateRow[];
  similarity_analysis: PipelineCandidateRow[];
  claims: PipelineClaimRow[];
  nextActions: string[];
  missingFields: string[];
  raw: IngestRunTrace | string;
};

const SUMMARY_LABELS: Record<PipelineSummaryKey, string> = {
  sentences: "sentences",
  mentions: "mentions",
  claims: "claims",
  local_entities: "local_entities",
  technical_entities: "technical_entities",
  technical_memory_chunks: "technical_memory_chunks",
  search_profiles: "search_profiles",
  candidate_selection_count: "candidate_selection_count",
  similarity_analysis_count: "similarity_analysis_count",
  skipped_sentence_count: "skipped_sentence_count",
  rejected_claim_count: "rejected_claim_count",
  unknown_entity_type_count: "unknown_entity_type_count",
  unknown_space_ratio: "unknown_space_ratio",
  high_similarity_count: "high_similarity_count",
  medium_similarity_count: "medium_similarity_count",
  low_similarity_count: "low_similarity_count",
};

const META_NOISE_PATTERN = /\b(todo|zaj|ellenőrizni|ellenorizni|majd később|majd kesobb|noise|meta)\b/i;
const LOW_COHERENCE_THRESHOLD = 0.7;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value.replace("%", ""));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function asString(value: unknown, fallback = "-"): string {
  if (value == null) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function normalizeKey(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, "_");
}

function getClaimTimeMode(claim: IngestRunTraceClaim): string {
  return claim.space_time_frame?.time_mode || claim.time_mode || "unknown";
}

function getClaimSpaceMode(claim: IngestRunTraceClaim): string {
  return claim.space_time_frame?.space_mode || claim.space_mode || "unknown";
}

function isUnknownType(value: string | null | undefined): boolean {
  const normalized = String(value || "").trim().toLowerCase();
  return !normalized || normalized === "unknown" || normalized === "other";
}

function isRelevantUnknownSpace(sentence: IngestRunTraceSentence, claim: IngestRunTraceClaim): boolean {
  if (getClaimSpaceMode(claim) !== "unknown") return false;
  if (claim.claim_type === "state") return true;
  const text = `${claim.subject_text} ${claim.object_text ?? ""} ${sentence.text}`.toLowerCase();
  return /\b(location|site|office|oficina|sede|ubicaci[oó]n|iroda|telephely|helysz[ií]n)\b/.test(text);
}

function scoreBand(score: number): string {
  if (score >= 0.75) return "high";
  if (score >= 0.45) return "medium";
  return "low";
}

function metricTone(key: PipelineSummaryKey, value: number | string | null, missing: boolean): PipelineSummaryMetric["tone"] {
  if (missing) return "warning";
  const numeric = typeof value === "number" ? value : asNumber(value);
  if (numeric == null) return "neutral";
  if (
    key === "skipped_sentence_count" ||
    key === "rejected_claim_count" ||
    key === "unknown_entity_type_count" ||
    key === "low_similarity_count"
  ) {
    return numeric > 0 ? "warning" : "good";
  }
  if (key === "unknown_space_ratio") return numeric > 0 ? "warning" : "good";
  if (key === "high_similarity_count") return numeric > 0 ? "good" : "warning";
  return "neutral";
}

function collectEvidenceIds(value: unknown): string[] {
  const ids = new Set<string>();
  const visit = (item: unknown) => {
    if (Array.isArray(item)) {
      item.forEach(visit);
      return;
    }
    if (!isRecord(item)) {
      if (typeof item === "string" && /(?:claim|sentence|evidence|id)/i.test(item)) ids.add(item);
      return;
    }
    for (const [key, nested] of Object.entries(item)) {
      if (/id|ids/.test(key.toLowerCase())) {
        if (Array.isArray(nested)) nested.forEach((entry) => entry && ids.add(String(entry)));
        else if (nested) ids.add(String(nested));
      } else if (Array.isArray(nested) || isRecord(nested)) {
        visit(nested);
      }
    }
  };
  visit(value);
  return [...ids].sort();
}

function findMemoryChunk(
  entity: IngestRunTraceLocalEntity,
  chunks: IngestRunTraceTechnicalMemoryChunk[]
): IngestRunTraceTechnicalMemoryChunk | undefined {
  return chunks.find(
    (chunk) =>
      chunk.local_entity_id === entity.local_entity_id ||
      normalizeKey(String(chunk.entity_name || "")) === normalizeKey(entity.canonical_name)
  );
}

function findSearchProfile(entity: IngestRunTraceLocalEntity, profiles: IngestRunTraceSearchProfile[]): IngestRunTraceSearchProfile | undefined {
  return profiles.find(
    (profile) =>
      profile.local_entity_id === entity.local_entity_id ||
      normalizeKey(String(profile.entity_name || "")) === normalizeKey(entity.canonical_name)
  );
}

function buildClaimLookup(trace: IngestRunTrace): Map<string, IngestRunTraceClaim> {
  const claims = new Map<string, IngestRunTraceClaim>();
  for (const sentence of trace.sentences ?? []) {
    for (const claim of sentence.claims ?? []) {
      if (claim.claim_id) claims.set(claim.claim_id, claim);
    }
  }
  return claims;
}

function entityStatus(type: string, coherence: number | null, claimsCount: number): PipelineModuleStatus {
  if (!claimsCount) return "Needs review";
  if (isUnknownType(type)) return "Needs review";
  if (coherence != null && coherence < LOW_COHERENCE_THRESHOLD) return "Warning";
  return "OK";
}

function buildEntityRows(trace: IngestRunTrace): PipelineEntityRow[] {
  const claimLookup = buildClaimLookup(trace);
  return (trace.local_entities ?? []).map((entity) => {
    const memory = findMemoryChunk(entity, trace.technical_memory_chunks ?? []);
    const profile = findSearchProfile(entity, trace.search_profiles ?? []);
    const claims = (entity.claim_ids ?? []).map((claimId) => {
      const claim = claimLookup.get(claimId);
      if (!claim) return `(missing claim) ${claimId}`;
      return `${claim.subject_text || "-"} --${claim.predicate || "-"}--> ${claim.object_text || "-"}`;
    });
    const evidenceIds = collectEvidenceIds([entity.evidence_refs, memory?.evidence_refs, profile?.evidence_refs, entity.claim_ids, entity.sentence_ids]);
    const timeMode = asString(memory?.time_profile?.dominant_time_mode ?? profile?.time_filters?.dominant, "unknown");
    const spaceMode = asString(memory?.space_profile?.dominant_space_mode ?? profile?.space_filters?.dominant, "unknown");
    const coherence = asNumber(entity.coherence_score);
    return {
      id: entity.local_entity_id || entity.normalized_key || entity.canonical_name,
      name: entity.canonical_name || "-",
      type: entity.entity_type || "unknown",
      claimsCount: entity.claim_ids?.length ?? 0,
      coherence,
      timeMode,
      spaceMode,
      status: entityStatus(entity.entity_type, coherence, entity.claim_ids?.length ?? 0),
      evidenceCount: evidenceIds.length,
      claims,
      technicalMemorySummary: memory?.summary_text || "missing from report",
      searchProfileCanonicalText: profile?.canonical_text || profile?.search_text || "missing from report",
      keywords: profile?.keywords ?? [],
      evidenceIds,
    };
  });
}

function buildTechnicalEntityRows(trace: IngestRunTrace): PipelineEntityRow[] {
  return (trace.technical_entities ?? []).map((entity, index) => {
    const claimGroups = isRecord(entity.claim_groups) ? entity.claim_groups : isRecord(entity.claims) ? entity.claims : {};
    const claimsCount = Object.values(claimGroups).reduce((sum, value) => sum + (asNumber(value) ?? 0), 0);
    const coherence = asNumber(entity.coherence_score);
    const type = asString(entity.type ?? entity.entity_type, "unknown");
    return {
      id: asString(entity.technical_entity_id, `technical-${index}`),
      name: asString(entity.name ?? entity.canonical_name),
      type,
      claimsCount,
      coherence,
      timeMode: asString(entity.time_signature?.dominant_time_mode, "unknown"),
      spaceMode: asString(entity.space_signature?.dominant_space_mode, "unknown"),
      status: entityStatus(type, coherence, claimsCount),
      evidenceCount: 0,
      claims: Object.entries(claimGroups).map(([key, value]) => `${key}: ${value}`),
      technicalMemorySummary: asString(entity.coherence ?? entity.coherence_state, "missing from report"),
      searchProfileCanonicalText: "missing from report",
      keywords: [],
      evidenceIds: [],
    };
  });
}

function buildClaimRows(trace: IngestRunTrace): PipelineClaimRow[] {
  const rows: PipelineClaimRow[] = [];
  for (const sentence of trace.sentences ?? []) {
    for (const claim of sentence.claims ?? []) {
      const warnings: string[] = [];
      if (claim.subject_source === "carryover") warnings.push("carryover");
      if (isUnknownType(claim.claim_type)) warnings.push("unknown type");
      if (isRelevantUnknownSpace(sentence, claim)) warnings.push("relevant unknown space");
      if (META_NOISE_PATTERN.test(sentence.text)) warnings.push("meta/noise");
      if (Number(claim.confidence ?? 0) < 0.6) warnings.push("low confidence");
      rows.push({
        id: claim.claim_id || `${sentence.sentence_id}-${rows.length}`,
        sentence: sentence.text || "-",
        subject: claim.subject_text || "-",
        predicate: claim.predicate || "-",
        object: claim.object_text || "-",
        type: claim.claim_type || "unknown",
        group: claim.claim_group || "-",
        confidence: Number(claim.confidence ?? 0),
        timeMode: getClaimTimeMode(claim),
        spaceMode: getClaimSpaceMode(claim),
        subjectSource: claim.subject_source || (claim.context_subject_applied ? "carryover" : "explicit"),
        warnings,
      });
    }
  }
  return rows;
}

function buildCandidateRows(items: IngestRunTraceCandidateSelection[]): PipelineCandidateRow[] {
  return items.map((candidate, index) => {
    const score = Number(candidate.score ?? candidate.candidate_score ?? 0);
    return {
      id: candidate.candidate_selection_id || candidate.candidate_entity_id || `candidate-${index}`,
      candidateName: candidate.candidate_name || "-",
      candidateType: candidate.candidate_type || "unknown",
      score,
      band: scoreBand(score),
      reasons: candidate.reasons ?? candidate.candidate_reason ?? [],
      componentScores: {},
      source: "candidate_selection",
    };
  });
}

function buildSimilarityRows(items: IngestRunTraceSimilarityAnalysis[]): PipelineCandidateRow[] {
  return items.map((analysis, index) => {
    const score = Number(analysis.total_similarity_score ?? 0);
    return {
      id: analysis.similarity_analysis_id || analysis.candidate_entity_id || `similarity-${index}`,
      candidateName: analysis.candidate_name || "-",
      candidateType: analysis.candidate_type || "unknown",
      score,
      band: analysis.similarity_band || scoreBand(score),
      reasons: analysis.similarity_reasons ?? analysis.reasons ?? [],
      componentScores: analysis.component_scores ?? {},
      source: "similarity_analysis",
    };
  });
}

function metric(
  key: PipelineSummaryKey,
  value: number | string | null,
  missingFields: string[],
  missing = value == null
): PipelineSummaryMetric {
  if (missing) missingFields.push(key);
  return { key, label: SUMMARY_LABELS[key], value, missing, tone: metricTone(key, value, missing) };
}

function makeSummary(trace: IngestRunTrace, claims: PipelineClaimRow[], missingFields: string[]): PipelineSummaryMetric[] {
  const summary = trace.summary ?? {};
  const unknownSpaceRatio =
    claims.length > 0 ? Number((claims.filter((claim) => claim.spaceMode === "unknown").length / claims.length).toFixed(2)) : 0;
  return [
    metric("sentences", summary.sentence_count ?? trace.sentences?.length ?? null, missingFields),
    metric("mentions", summary.mention_count ?? (trace.sentences ?? []).reduce((sum, sentence) => sum + (sentence.mentions?.length ?? 0), 0), missingFields),
    metric("claims", summary.claim_count ?? claims.length, missingFields),
    metric("local_entities", trace.local_entities?.length ?? summary.local_entity_count ?? summary.local_entity_cluster_count ?? null, missingFields),
    metric("technical_entities", trace.technical_entities?.length ?? summary.technical_entities ?? null, missingFields),
    metric("technical_memory_chunks", trace.technical_memory_chunks?.length ?? summary.technical_memory_chunks ?? null, missingFields),
    metric("search_profiles", trace.search_profiles?.length ?? summary.search_profiles ?? null, missingFields),
    metric("candidate_selection_count", summary.candidate_selection_count ?? trace.candidate_selections?.length ?? null, missingFields),
    metric("similarity_analysis_count", summary.similarity_analysis_count ?? trace.similarity_analyses?.length ?? null, missingFields),
    metric("skipped_sentence_count", summary.quality?.skipped_sentence_count ?? null, missingFields),
    metric("rejected_claim_count", summary.quality?.rejected_claim_count ?? null, missingFields),
    metric("unknown_entity_type_count", summary.unknown_entity_type_count ?? null, missingFields),
    metric("unknown_space_ratio", summary.quality ? unknownSpaceRatio : unknownSpaceRatio, missingFields, false),
    metric("high_similarity_count", summary.high_similarity_count ?? null, missingFields),
    metric("medium_similarity_count", summary.medium_similarity_count ?? null, missingFields),
    metric("low_similarity_count", summary.low_similarity_count ?? null, missingFields),
  ];
}

function countDuplicateCandidates(rows: PipelineCandidateRow[]): number {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const key = `${normalizeKey(row.candidateName)}:${normalizeKey(row.candidateType)}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.values()].filter((count) => count > 1).reduce((sum, count) => sum + count - 1, 0);
}

function buildModules(report: {
  summary: PipelineSummaryMetric[];
  quality: PipelineQuality;
  claims: PipelineClaimRow[];
  entities: PipelineEntityRow[];
  candidates: PipelineCandidateRow[];
  similarities: PipelineCandidateRow[];
}): PipelineModuleHealth[] {
  const value = (key: PipelineSummaryKey) => report.summary.find((item) => item.key === key);
  const count = (key: PipelineSummaryKey) => asNumber(value(key)?.value) ?? 0;
  const missing = (key: PipelineSummaryKey) => value(key)?.missing === true;
  const module = (name: string, status: PipelineModuleStatus, detail: string): PipelineModuleHealth => ({ name, status, detail });
  return [
    module("Source / Sentence parsing", count("sentences") > 0 ? "OK" : "Missing", `${count("sentences")} sentences`),
    module("Mention Extraction", count("mentions") > 0 ? "OK" : "Missing", `${count("mentions")} mentions`),
    module("Claim Extraction", report.claims.length > 0 ? (report.quality.metaClaimCount > 0 ? "Warning" : "OK") : "Missing", `${report.claims.length} claims`),
    module("Space-Time Frame", report.quality.relevantUnknownSpaceCount > 0 ? "Warning" : "OK", `${report.quality.relevantUnknownSpaceCount} relevant unknown space`),
    module("Claim Typing", report.quality.unknownTypeClaimCount > 0 ? "Needs review" : "OK", `${report.quality.unknownTypeClaimCount} unknown type claims`),
    module("Local Resolver", count("local_entities") > 0 ? (report.quality.lowCoherenceEntityCount > 0 ? "Warning" : "OK") : "Missing", `${count("local_entities")} local entities`),
    module("Technical Entity Builder", missing("technical_entities") ? "Missing" : count("technical_entities") > 0 ? "OK" : "Needs review", `${count("technical_entities")} technical entities`),
    module("Technical Memory Chunk Builder", missing("technical_memory_chunks") ? "Missing" : count("technical_memory_chunks") > 0 ? "OK" : "Needs review", `${count("technical_memory_chunks")} chunks`),
    module("Search Profile Builder", missing("search_profiles") ? "Missing" : count("search_profiles") > 0 ? "OK" : "Needs review", `${count("search_profiles")} profiles`),
    module("Candidate Selection", missing("candidate_selection_count") ? "Missing" : report.candidates.length > 0 ? "OK" : "Needs review", `${report.candidates.length} candidates`),
    module("Similarity Analysis", missing("similarity_analysis_count") ? "Missing" : report.similarities.length > 0 ? (count("high_similarity_count") === 0 ? "Warning" : "OK") : "Needs review", `${report.similarities.length} analyses`),
    module("Tension Engine", "Not implemented", "missing from report"),
    module("Decision Engine", "Not implemented", "missing from report"),
    module("Global Profile Builder", "Not implemented", "missing from report"),
    module("Retrieval Chunk Builder", "Not implemented", "missing from report"),
  ];
}

function buildIssues(quality: PipelineQuality): PipelineIssue[] {
  return [
    { key: "noise", label: "noise sentenceből lett claim", count: quality.noiseClaimCount, severity: "danger", detail: "Noise filter / sentence gate" },
    { key: "meta", label: "TODO / meta mondatból lett claim", count: quality.metaClaimCount, severity: "danger", detail: "Meta sentence guard" },
    { key: "unknown_type", label: "unknown entity type", count: quality.unknownEntityTypeCount ?? 0, severity: "warning", detail: "Entity typing" },
    { key: "unknown_space", label: "relevant claim unknown space", count: quality.relevantUnknownSpaceCount, severity: "warning", detail: "Space-time fallback" },
    { key: "carryover", label: "carryover subject error", count: quality.carryoverSubjectErrorCount, severity: "warning", detail: "Carryover guard" },
    { key: "weak_duplicate", label: "weak duplicate", count: quality.weakDuplicateCount, severity: "warning", detail: "Claim extraction duplicate guard" },
    { key: "low_coherence", label: "low coherence entity", count: quality.lowCoherenceEntityCount, severity: "warning", detail: "Local resolver coherence" },
    { key: "no_high_similarity", label: "similarity high count = 0", count: quality.highSimilarityCount === 0 ? 1 : 0, severity: "warning", detail: "Similarity scoring" },
  ];
}

type InternalQuality = PipelineQuality & { claimsHaveCarryoverWarning?: boolean };

function buildNextActions(quality: InternalQuality): string[] {
  const actions: string[] = [];
  if (quality.noiseClaimCount > 0 || quality.metaClaimCount > 0) actions.push("Noise filter javítandó");
  if (quality.carryoverSubjectErrorCount > 0 || quality.claimsHaveCarryoverWarning) actions.push("Carryover guard szigorítandó");
  if (quality.relevantUnknownSpaceCount > 0 || (quality.unknownSpaceRatio ?? 0) > 0.2) actions.push("Space-time fallback javítandó");
  if (quality.highSimilarityCount === 0 || (quality.lowSimilarityCount ?? 0) > (quality.mediumSimilarityCount ?? 0)) {
    actions.push("Similarity threshold/scoring finomítandó");
  }
  actions.push("Tension/Decision modul még nincs kész");
  return [...new Set(actions)];
}

export function parsePipelineHealthReport(input: IngestRunTrace | string): PipelineHealthReport {
  if (typeof input === "string") {
    const parsed = parseTextReport(input);
    if (parsed) return parsed;
    try {
      const json = JSON.parse(input) as IngestRunTrace;
      return parseJsonTrace(json);
    } catch {
      const fallback = parseTextReport(input, true);
      if (fallback) return fallback;
      throw new Error("Report parse failed.");
    }
  }
  return parseJsonTrace(input);
}

function parseJsonTrace(trace: IngestRunTrace): PipelineHealthReport {
  const missingFields: string[] = [];
  const claims = buildClaimRows(trace);
  const localEntities = buildEntityRows(trace);
  const technicalEntities = buildTechnicalEntityRows(trace);
  const candidateSelection = buildCandidateRows(trace.candidate_selections ?? []);
  const similarityAnalysis = buildSimilarityRows(trace.similarity_analyses ?? []);
  const summary = makeSummary(trace, claims, missingFields);
  const highSimilarityCount = asNumber(summary.find((item) => item.key === "high_similarity_count")?.value);
  const mediumSimilarityCount = asNumber(summary.find((item) => item.key === "medium_similarity_count")?.value);
  const lowSimilarityCount = asNumber(summary.find((item) => item.key === "low_similarity_count")?.value);
  const unknownSpaceRatio = asNumber(summary.find((item) => item.key === "unknown_space_ratio")?.value);
  const quality: InternalQuality = {
    skippedSentenceCount: asNumber(summary.find((item) => item.key === "skipped_sentence_count")?.value),
    rejectedClaimCount: asNumber(summary.find((item) => item.key === "rejected_claim_count")?.value),
    unknownEntityTypeCount:
      asNumber(summary.find((item) => item.key === "unknown_entity_type_count")?.value) ??
      localEntities.filter((entity) => isUnknownType(entity.type)).length,
    unknownSpaceRatio,
    highSimilarityCount,
    mediumSimilarityCount,
    lowSimilarityCount,
    noiseClaimCount: claims.filter((claim) => claim.warnings.includes("meta/noise") && /zaj|noise/i.test(claim.sentence)).length,
    metaClaimCount: claims.filter((claim) => claim.warnings.includes("meta/noise")).length,
    unknownTypeClaimCount: claims.filter((claim) => claim.warnings.includes("unknown type")).length,
    relevantUnknownSpaceCount: claims.filter((claim) => claim.warnings.includes("relevant unknown space")).length,
    carryoverSubjectErrorCount: claims.filter((claim) => claim.subjectSource === "carryover").length,
    weakDuplicateCount: 0,
    lowCoherenceEntityCount: localEntities.filter((entity) => entity.coherence != null && entity.coherence < LOW_COHERENCE_THRESHOLD).length,
    duplicateCandidateCount: countDuplicateCandidates([...candidateSelection, ...similarityAnalysis]),
    claimsHaveCarryoverWarning: claims.some((claim) => claim.warnings.includes("carryover")),
  };
  const modules = buildModules({ summary, quality, claims, entities: localEntities, candidates: candidateSelection, similarities: similarityAnalysis });
  return {
    source: "json",
    runId: trace.run_id || "-",
    sourceName: trace.source_name || "-",
    status: trace.status || "-",
    createdAt: trace.created_at || "-",
    summary,
    quality,
    modules,
    issues: buildIssues(quality),
    local_entities: localEntities,
    technical_entities: technicalEntities,
    technical_memory_chunks: trace.technical_memory_chunks ?? [],
    search_profiles: trace.search_profiles ?? [],
    candidate_selection: candidateSelection,
    similarity_analysis: similarityAnalysis,
    claims,
    nextActions: buildNextActions(quality),
    missingFields: [...new Set(missingFields)],
    raw: trace,
  };
}

function parseTextReport(input: string, force = false): PipelineHealthReport | null {
  const lines = input.split(/\r?\n/);
  const keyValues = new Map<string, string>();
  for (const line of lines) {
    const match = /^([a-zA-Z0-9_ -]+):\s*(.*)$/.exec(line.trim());
    if (match) keyValues.set(normalizeKey(match[1]), match[2].trim());
  }
  if (!force && !keyValues.has("run_id") && !input.includes("KNOWLEDGE TRACE REPORT")) return null;
  const missingFields: string[] = [];
  const textMetric = (key: PipelineSummaryKey, sourceKey = key): PipelineSummaryMetric => {
    const raw = keyValues.get(sourceKey);
    return metric(key, raw == null ? null : asNumber(raw) ?? raw, missingFields);
  };
  const summary = [
    textMetric("sentences"),
    textMetric("mentions"),
    textMetric("claims"),
    textMetric("local_entities"),
    textMetric("technical_entities"),
    textMetric("technical_memory_chunks"),
    textMetric("search_profiles"),
    textMetric("candidate_selection_count"),
    textMetric("similarity_analysis_count"),
    textMetric("skipped_sentence_count"),
    textMetric("rejected_claim_count"),
    textMetric("unknown_entity_type_count"),
    textMetric("unknown_space_ratio"),
    textMetric("high_similarity_count"),
    textMetric("medium_similarity_count"),
    textMetric("low_similarity_count"),
  ];
  const claims: PipelineClaimRow[] = [];
  const candidateSelection: PipelineCandidateRow[] = [];
  const similarityAnalysis: PipelineCandidateRow[] = [];
  let currentClaim: Partial<PipelineClaimRow> | null = null;
  let currentCandidate: Partial<PipelineCandidateRow> | null = null;
  let currentSimilarity: Partial<PipelineCandidateRow> | null = null;
  let section = "";
  const finishClaim = () => {
    if (!currentClaim?.sentence && !currentClaim?.subject) return;
    const row: PipelineClaimRow = {
      id: `text-claim-${claims.length}`,
      sentence: currentClaim.sentence || "-",
      subject: currentClaim.subject || "-",
      predicate: currentClaim.predicate || "-",
      object: currentClaim.object || "-",
      type: currentClaim.type || "unknown",
      group: currentClaim.group || "-",
      confidence: currentClaim.confidence ?? 0,
      timeMode: currentClaim.timeMode || "unknown",
      spaceMode: currentClaim.spaceMode || "unknown",
      subjectSource: currentClaim.subjectSource || "unknown",
      warnings: [],
    };
    if (row.subjectSource === "carryover") row.warnings.push("carryover");
    if (isUnknownType(row.type)) row.warnings.push("unknown type");
    if (row.spaceMode === "unknown") row.warnings.push("relevant unknown space");
    if (META_NOISE_PATTERN.test(row.sentence)) row.warnings.push("meta/noise");
    if (row.confidence < 0.6) row.warnings.push("low confidence");
    claims.push(row);
  };
  const finishSimilarity = () => {
    if (!currentSimilarity?.candidateName) return;
    similarityAnalysis.push({
      id: `text-similarity-${similarityAnalysis.length}`,
      candidateName: currentSimilarity.candidateName,
      candidateType: currentSimilarity.candidateType || "unknown",
      score: currentSimilarity.score ?? 0,
      band: currentSimilarity.band || scoreBand(currentSimilarity.score ?? 0),
      reasons: currentSimilarity.reasons ?? [],
      componentScores: currentSimilarity.componentScores ?? {},
      source: "similarity_analysis",
    });
  };
  const finishCandidate = () => {
    if (!currentCandidate?.candidateName) return;
    candidateSelection.push({
      id: `text-candidate-${candidateSelection.length}`,
      candidateName: currentCandidate.candidateName,
      candidateType: currentCandidate.candidateType || "unknown",
      score: currentCandidate.score ?? 0,
      band: currentCandidate.band || scoreBand(currentCandidate.score ?? 0),
      reasons: currentCandidate.reasons ?? [],
      componentScores: {},
      source: "candidate_selection",
    });
  };
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (/^[A-Z][A-Z _]+:$/.test(line)) {
      finishClaim();
      finishCandidate();
      finishSimilarity();
      currentClaim = null;
      currentCandidate = null;
      currentSimilarity = null;
      section = line.replace(":", "");
      continue;
    }
    if (section === "CLAIMS") {
      if (/^#\d+/.test(line)) {
        finishClaim();
        currentClaim = {};
      } else if (currentClaim && line.startsWith("sentence:")) currentClaim.sentence = line.slice(9).trim();
      else if (currentClaim && line.startsWith("subject:")) currentClaim.subject = line.slice(8).trim();
      else if (currentClaim && line.startsWith("subject_source:")) currentClaim.subjectSource = line.slice(15).trim();
      else if (currentClaim && line.startsWith("predicate:")) currentClaim.predicate = line.slice(10).trim();
      else if (currentClaim && line.startsWith("object:")) currentClaim.object = line.slice(7).trim();
      else if (currentClaim && line.startsWith("type:")) currentClaim.type = line.slice(5).trim();
      else if (currentClaim && line.startsWith("group:")) currentClaim.group = line.slice(6).trim();
      else if (currentClaim && line.startsWith("confidence:")) currentClaim.confidence = asNumber(line.slice(11).trim()) ?? 0;
      else if (currentClaim && line.startsWith("time_mode:")) currentClaim.timeMode = line.slice(10).trim();
      else if (currentClaim && line.startsWith("space_mode:")) currentClaim.spaceMode = line.slice(11).trim();
    }
    if (section === "SIMILARITY ANALYSES") {
      if (/^#\d+/.test(line)) {
        finishSimilarity();
        currentSimilarity = {};
      } else if (currentSimilarity && line.startsWith("candidate_name:")) currentSimilarity.candidateName = line.slice(15).trim();
      else if (currentSimilarity && line.startsWith("candidate_type:")) currentSimilarity.candidateType = line.slice(15).trim();
      else if (currentSimilarity && line.startsWith("total_similarity_score:")) currentSimilarity.score = asNumber(line.slice(23).trim()) ?? 0;
      else if (currentSimilarity && line.startsWith("band:")) currentSimilarity.band = line.slice(5).trim();
      else if (currentSimilarity && line.startsWith("reasons:")) currentSimilarity.reasons = line.slice(8).split(",").map((item) => item.trim()).filter(Boolean);
    }
    if (section === "CANDIDATE SELECTION") {
      if (/^#\d+/.test(line)) {
        finishCandidate();
        currentCandidate = {};
      } else if (currentCandidate && line.startsWith("candidate_name:")) currentCandidate.candidateName = line.slice(15).trim();
      else if (currentCandidate && line.startsWith("candidate_type:")) currentCandidate.candidateType = line.slice(15).trim();
      else if (currentCandidate && line.startsWith("score:")) currentCandidate.score = asNumber(line.slice(6).trim()) ?? 0;
      else if (currentCandidate && line.startsWith("reasons:")) currentCandidate.reasons = line.slice(8).split(",").map((item) => item.trim()).filter(Boolean);
    }
  }
  finishClaim();
  finishCandidate();
  finishSimilarity();
  const quality: InternalQuality = {
    skippedSentenceCount: asNumber(keyValues.get("skipped_sentence_count")),
    rejectedClaimCount: asNumber(keyValues.get("rejected_claim_count")),
    unknownEntityTypeCount: asNumber(keyValues.get("unknown_entity_type_count")),
    unknownSpaceRatio: asNumber(keyValues.get("unknown_space_ratio")),
    highSimilarityCount: asNumber(keyValues.get("high_similarity_count")),
    mediumSimilarityCount: asNumber(keyValues.get("medium_similarity_count")),
    lowSimilarityCount: asNumber(keyValues.get("low_similarity_count")),
    noiseClaimCount: claims.filter((claim) => claim.warnings.includes("meta/noise") && /zaj|noise/i.test(claim.sentence)).length,
    metaClaimCount: claims.filter((claim) => claim.warnings.includes("meta/noise")).length,
    unknownTypeClaimCount: claims.filter((claim) => claim.warnings.includes("unknown type")).length,
    relevantUnknownSpaceCount: claims.filter((claim) => claim.warnings.includes("relevant unknown space")).length,
    carryoverSubjectErrorCount: asNumber(keyValues.get("carryover_subject_error_count")) ?? claims.filter((claim) => claim.subjectSource === "carryover").length,
    weakDuplicateCount: asNumber(keyValues.get("weak_duplicate_claim_count")) ?? 0,
    lowCoherenceEntityCount: asNumber(keyValues.get("low_coherence_local_entity_count")) ?? 0,
    duplicateCandidateCount: countDuplicateCandidates([...candidateSelection, ...similarityAnalysis]),
    claimsHaveCarryoverWarning: claims.some((claim) => claim.warnings.includes("carryover")),
  };
  const modules = buildModules({ summary, quality, claims, entities: [], candidates: candidateSelection, similarities: similarityAnalysis });
  return {
    source: "text",
    runId: keyValues.get("run_id") || "-",
    sourceName: keyValues.get("source_name") || "-",
    status: keyValues.get("status") || "-",
    createdAt: keyValues.get("created_at") || "-",
    summary,
    quality,
    modules,
    issues: buildIssues(quality),
    local_entities: [],
    technical_entities: [],
    technical_memory_chunks: [],
    search_profiles: [],
    candidate_selection: candidateSelection,
    similarity_analysis: similarityAnalysis,
    claims,
    nextActions: buildNextActions(quality),
    missingFields: [...new Set(missingFields)],
    raw: input,
  };
}
