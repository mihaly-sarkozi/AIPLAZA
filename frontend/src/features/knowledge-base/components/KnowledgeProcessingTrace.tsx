import { Fragment, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import { cn } from "../../../utils/cn";
import type { IngestRunTrace, IngestRunTraceClaim, IngestRunTraceLocalEntity } from "../services";
import { generateKnowledgeTraceReport } from "../utils/knowledgeTraceReport";

type ConfidenceFilter = "all" | "low" | "medium" | "high";
type ViewMode = "table" | "json";
const TRACE_STOPWORDS = new Set([
  "a",
  "az",
  "egy",
  "es",
  "és",
  "hogy",
  "vagy",
  "de",
  "is",
  "nem",
  "the",
  "an",
  "and",
  "or",
  "of",
  "to",
  "in",
  "is",
  "was",
  "el",
  "la",
  "los",
  "las",
  "un",
  "una",
  "y",
  "o",
  "del",
  "en",
  "es",
  "fue",
]);
const TRACE_MONTHS = new Set([
  "januar",
  "februar",
  "marcius",
  "aprilis",
  "majus",
  "junius",
  "julius",
  "augusztus",
  "szeptember",
  "oktober",
  "november",
  "december",
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
]);

const LOCAL_ENTITY_LOW_COHERENCE_THRESHOLD = 0.7;

interface KnowledgeProcessingTraceProps {
  trace: IngestRunTrace | null | undefined;
  loading?: boolean;
  error?: string | null;
  emptyMessage?: string;
}

type TraceQualitySummary = {
  skipped_sentence_count: number;
  rejected_claim_count: number;
  describes_claim_count: number;
  low_confidence_claim_count: number;
  bad_subject_claim_count: number;
  question_sentence_count: number;
  fragment_sentence_count: number;
  todo?: string;
};

function getConfidenceBucket(confidence: number): ConfidenceFilter {
  if (confidence >= 0.75) return "high";
  if (confidence >= 0.5) return "medium";
  return "low";
}

function badgeToneForClaimType(claimType: string): string {
  switch (claimType) {
    case "identifier":
      return "bg-[var(--color-primary)]/15 text-[var(--color-primary)]";
    case "stable_descriptor":
      return "bg-[var(--color-muted)]/15 text-[var(--color-foreground)]";
    case "state":
      return "bg-amber-500/15 text-amber-700";
    case "relation":
      return "bg-sky-500/15 text-sky-700";
    case "event":
      return "bg-slate-500/15 text-slate-700";
    case "rule_procedure":
      return "bg-red-500/15 text-red-700";
    case "opinion":
      return "bg-violet-500/15 text-violet-700";
    default:
      return "bg-[var(--color-border)] text-[var(--color-muted)]";
  }
}

function badgeToneForSpaceTime(mode?: string | null): string {
  switch (mode) {
    case "current":
      return "bg-emerald-500/15 text-emerald-700";
    case "event":
      return "bg-sky-500/15 text-sky-700";
    case "bounded":
      return "bg-violet-500/15 text-violet-700";
    case "zero_time":
    case "irrelevant":
      return "bg-slate-400/15 text-slate-700";
    default:
      return "bg-[var(--color-border)] text-[var(--color-muted)]";
  }
}

function getClaimTimeMode(claim: IngestRunTraceClaim): string {
  return claim.time_mode || claim.space_time_frame?.time_mode || "unknown";
}

function getClaimSpaceMode(claim: IngestRunTraceClaim): string {
  return claim.space_mode || claim.space_time_frame?.space_mode || "unknown";
}

function formatTimestamp(value?: string | null): string {
  if (!value) return "-";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function foldText(value?: string | null): string {
  return (value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function isStopwordSubject(subject?: string | null): boolean {
  const folded = foldText(subject);
  return !!folded && TRACE_STOPWORDS.has(folded);
}

function isRealSubject(subject?: string | null): boolean {
  const folded = foldText(subject);
  if (!folded) return false;
  if (TRACE_STOPWORDS.has(folded)) return false;
  if (/^(19|20)\d{2}$/.test(folded)) return false;
  if (TRACE_MONTHS.has(folded)) return false;
  return true;
}

function hasStoredSpaceTimeFrame(claim: IngestRunTraceClaim): boolean {
  return !!claim.space_time_frame && !String(claim.space_time_frame.frame_id || "").startsWith("compat:");
}

function isLocationLikeText(text?: string | null): boolean {
  const folded = foldText(text);
  return ["office", "location", "site", "oficina", "sede", "ubicacion", "ubicación", "iroda", "telephely", "helyszin", "helyszín"].some(
    (keyword) => folded.includes(foldText(keyword))
  );
}

function hasLocationMention(sentence: NonNullable<IngestRunTrace["sentences"]>[number]): boolean {
  return (sentence.mentions ?? []).some((mention) => foldText(mention.mention_type) === "location");
}

function isUnknownSpaceRelevant(
  sentence: NonNullable<IngestRunTrace["sentences"]>[number],
  claim: IngestRunTraceClaim
): boolean {
  if (getClaimSpaceMode(claim) !== "unknown") {
    return false;
  }
  if (claim.claim_type === "state") {
    return true;
  }
  if (isLocationLikeText(claim.subject_text) || hasLocationMention(sentence)) {
    return true;
  }
  return false;
}

function getTraceQualitySummary(trace: IngestRunTrace): TraceQualitySummary {
  const summaryQuality = trace.summary?.quality ?? {};
  const claims = (trace.sentences ?? []).flatMap((sentence) => sentence.claims ?? []);
  const describesClaimCount = claims.filter((claim) => foldText(claim.predicate) === "describes").length;
  const lowConfidenceClaimCount = claims.filter((claim) => Number(claim.confidence ?? 0) < 0.5).length;
  const badSubjectClaimCount = claims.filter((claim) => !isRealSubject(claim.subject_text)).length;

  return {
    skipped_sentence_count: Number(summaryQuality.skipped_sentence_count ?? 0),
    rejected_claim_count: Number(summaryQuality.rejected_claim_count ?? 0),
    describes_claim_count: Number(summaryQuality.describes_claim_count ?? describesClaimCount),
    low_confidence_claim_count: Number(summaryQuality.low_confidence_claim_count ?? lowConfidenceClaimCount),
    bad_subject_claim_count: Number(summaryQuality.bad_subject_claim_count ?? badSubjectClaimCount),
    question_sentence_count: Number(summaryQuality.question_sentence_count ?? 0),
    fragment_sentence_count: Number(summaryQuality.fragment_sentence_count ?? 0),
    todo: typeof summaryQuality.todo === "string" ? summaryQuality.todo : undefined,
  };
}

function formatRatio(part: number, total: number): string {
  if (!total) return "0/0";
  return `${part}/${total}`;
}

function buildClaimLookupMap(trace: IngestRunTrace): Map<string, IngestRunTraceClaim> {
  const m = new Map<string, IngestRunTraceClaim>();
  for (const sentence of trace.sentences ?? []) {
    for (const claim of sentence.claims ?? []) {
      if (claim.claim_id) {
        m.set(claim.claim_id, claim);
      }
    }
  }
  return m;
}

function formatLinkedClaimOneLiner(claim: IngestRunTraceClaim): string {
  const subj = (claim.subject_text || "-").trim() || "-";
  const pred = (claim.predicate || "-").trim() || "-";
  const objRaw = claim.object_text;
  const obj = objRaw != null && String(objRaw).trim() !== "" ? String(objRaw).trim() : "-";
  return `${subj} --${pred}--> ${obj}`;
}

async function copyTextToClipboard(text: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }

  if (typeof document === "undefined") {
    return false;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  let copied = false;
  try {
    copied = document.execCommand("copy");
  } finally {
    document.body.removeChild(textarea);
  }

  return copied;
}

function sanitizeFilenamePart(value: string | null | undefined): string {
  return String(value || "trace")
    .trim()
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80) || "trace";
}

function saveTextFile(text: string, filename: string): boolean {
  if (typeof document === "undefined" || typeof Blob === "undefined" || typeof URL === "undefined") {
    return false;
  }

  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  return true;
}

function ClaimDetails({ claim }: { claim: IngestRunTraceClaim }) {
  const timeMode = getClaimTimeMode(claim);
  const spaceMode = getClaimSpaceMode(claim);
  return (
    <div className="grid gap-3 rounded-lg bg-[var(--color-primary)]/5 p-4 text-sm">
      <div>
        <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Claim ID</div>
        <div className="mt-1 break-all font-mono text-xs">{claim.claim_id}</div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Claim text</div>
        <div className="mt-1">{claim.claim_text || "-"}</div>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Claim status</div>
          <div className="mt-1">{claim.claim_status || "-"}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Conflict behavior</div>
          <div className="mt-1">{claim.conflict_behavior || "-"}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Time mode</div>
          <div className="mt-1">{timeMode}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Space mode</div>
          <div className="mt-1">{spaceMode}</div>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Identity weight</div>
          <div className="mt-1">{claim.identity_weight}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Similarity weight</div>
          <div className="mt-1">{claim.similarity_weight}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Tension weight</div>
          <div className="mt-1">{claim.tension_weight}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Cardinality / status</div>
          <div className="mt-1">
            {claim.cardinality} / {claim.claim_status}
          </div>
        </div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Space-time frame</div>
        {claim.space_time_frame ? (
          <pre className="mt-2 overflow-x-auto rounded-md border border-[var(--color-border)] bg-[var(--color-background)] p-3 text-xs">
            {JSON.stringify(claim.space_time_frame, null, 2)}
          </pre>
        ) : (
          <div className="mt-2 text-sm text-[var(--color-muted)]">No space-time frame yet</div>
        )}
      </div>
    </div>
  );
}

export default function KnowledgeProcessingTrace({
  trace,
  loading = false,
  error,
  emptyMessage = "No processing trace found.",
}: KnowledgeProcessingTraceProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("table");
  const [searchText, setSearchText] = useState("");
  const [claimTypeFilter, setClaimTypeFilter] = useState("all");
  const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>("all");
  const [showUnknownSpaceTimeOnly, setShowUnknownSpaceTimeOnly] = useState(false);
  const [expandedClaims, setExpandedClaims] = useState<Record<string, boolean>>({});
  const [localEntityTypeFilter, setLocalEntityTypeFilter] = useState("all");
  const [localEntityLowCoherenceOnly, setLocalEntityLowCoherenceOnly] = useState(false);
  const [localEntityUnknownTypeOnly, setLocalEntityUnknownTypeOnly] = useState(false);

  useEffect(() => {
    if (!trace || typeof window === "undefined" || !window?.console) return;
    console.log("[KnowledgeTraceUI]", { run_id: trace.run_id, summary: trace.summary });
  }, [trace]);

  const claimTypes = useMemo(() => {
    const values = new Set<string>();
    for (const sentence of trace?.sentences ?? []) {
      for (const claim of sentence.claims ?? []) values.add(claim.claim_type || "other");
    }
    return ["all", ...Array.from(values).sort()];
  }, [trace]);

  const claimLookup = useMemo(() => {
    if (!trace) return new Map<string, IngestRunTraceClaim>();
    return buildClaimLookupMap(trace);
  }, [trace]);

  const localEntityTypeOptions = useMemo(() => {
    if (!trace) return ["all"];
    const values = new Set<string>();
    for (const entity of trace.local_entities ?? []) {
      values.add(entity.entity_type || "unknown");
    }
    return ["all", ...Array.from(values).sort()];
  }, [trace]);

  const filteredLocalEntities = useMemo((): IngestRunTraceLocalEntity[] => {
    if (!trace) return [];
    const list = trace.local_entities ?? [];
    return list.filter((entity) => {
      if (localEntityTypeFilter !== "all" && (entity.entity_type || "unknown") !== localEntityTypeFilter) {
        return false;
      }
      if (localEntityLowCoherenceOnly && (entity.coherence_score ?? 0) >= LOCAL_ENTITY_LOW_COHERENCE_THRESHOLD) {
        return false;
      }
      if (localEntityUnknownTypeOnly && (entity.entity_type || "").toLowerCase() !== "unknown") {
        return false;
      }
      return true;
    });
  }, [trace, localEntityTypeFilter, localEntityLowCoherenceOnly, localEntityUnknownTypeOnly]);

  const filteredSentences = useMemo(() => {
    return (trace?.sentences ?? [])
      .map((sentence) => {
        const matchesSentence = sentence.text.toLowerCase().includes(searchText.trim().toLowerCase());
        const claims = (sentence.claims ?? []).filter((claim) => {
          const matchesClaimType = claimTypeFilter === "all" || claim.claim_type === claimTypeFilter;
          const matchesConfidence =
            confidenceFilter === "all" || getConfidenceBucket(Number(claim.confidence ?? 0)) === confidenceFilter;
          const matchesSpaceTime =
            !showUnknownSpaceTimeOnly ||
            getClaimTimeMode(claim) === "unknown" ||
            getClaimSpaceMode(claim) === "unknown";
          return matchesClaimType && matchesConfidence && matchesSpaceTime;
        });
        const keepSentence = matchesSentence || claims.length > 0;
        return keepSentence ? { ...sentence, claims } : null;
      })
      .filter(Boolean) as NonNullable<IngestRunTrace["sentences"]>[number][];
  }, [trace, searchText, claimTypeFilter, confidenceFilter, showUnknownSpaceTimeOnly]);

  const validation = useMemo(() => {
    const sentences = trace?.sentences ?? [];
    const claims = sentences.flatMap((sentence) => sentence.claims ?? []);
    const quality = trace ? getTraceQualitySummary(trace) : getTraceQualitySummary({
      run_id: "",
      language: "unknown",
      status: "",
      created_at: "",
      summary: { sentence_count: 0, mention_count: 0, claim_count: 0, space_time_frame_count: 0 },
      sentences: [],
    });
    const unknownSpaceRelevantCount = sentences.reduce((count, sentence) => {
      return count + (sentence.claims ?? []).filter((claim) => isUnknownSpaceRelevant(sentence, claim)).length;
    }, 0);
    return {
      claimCount: claims.length,
      sentencesWithoutMentions: sentences.filter((sentence) => (sentence.mentions ?? []).length === 0).length,
      sentencesWithoutClaims: sentences.filter((sentence) => (sentence.claims ?? []).length === 0).length,
      claimsWithUnknownType: claims.filter((claim) => !claim.claim_type || claim.claim_type === "other").length,
      claimsWithLowConfidence: quality.low_confidence_claim_count,
      claimsWithUnknownTime: claims.filter((claim) => getClaimTimeMode(claim) === "unknown").length,
      claimsWithUnknownSpace: claims.filter((claim) => getClaimSpaceMode(claim) === "unknown").length,
      unknownSpaceRelevantCount,
      stopwordSubjectCount: claims.filter((claim) => isStopwordSubject(claim.subject_text)).length,
      claimsWithDescribesPredicate: quality.describes_claim_count,
      claimsWithoutRealSubject: claims.filter((claim) => !isRealSubject(claim.subject_text)).length,
      claimsWithoutStoredSpaceTimeFrame: claims.filter((claim) => !hasStoredSpaceTimeFrame(claim)).length,
      skippedSentenceCount: quality.skipped_sentence_count,
      rejectedClaimCount: quality.rejected_claim_count,
      badSubjectClaimCount: quality.bad_subject_claim_count,
      questionSentenceCount: quality.question_sentence_count,
      fragmentSentenceCount: quality.fragment_sentence_count,
      qualityTodo: quality.todo,
    };
  }, [trace]);

  if (loading) {
    return <Alert tone="info">Trace betöltése folyamatban...</Alert>;
  }
  if (error) {
    return <Alert tone="error">{error}</Alert>;
  }
  if (!trace) {
    return <Alert tone="info">{emptyMessage}</Alert>;
  }
  if ((trace.sentences ?? []).length === 0 && (trace.local_entities ?? []).length === 0) {
    return <Alert tone="info">Empty trace: no sentences and no local entities for this run yet.</Alert>;
  }

  const prettyJson = JSON.stringify(trace, null, 2);

  return (
    <section className="space-y-6">
      <div className="app-surface p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <h2 className="text-xl font-semibold">Knowledge Processing Trace</h2>
            <div className="grid gap-2 text-sm text-[var(--color-muted)] md:grid-cols-2">
              <div>
                <span className="font-medium text-[var(--color-foreground)]">Run:</span> {trace.run_id}
              </div>
              <div>
                <span className="font-medium text-[var(--color-foreground)]">Source ID:</span> {trace.source_id ?? "-"}
              </div>
              <div>
                <span className="font-medium text-[var(--color-foreground)]">Source:</span> {trace.source_name ?? "-"}
              </div>
              <div>
                <span className="font-medium text-[var(--color-foreground)]">Language:</span> {trace.language}
              </div>
              <div>
                <span className="font-medium text-[var(--color-foreground)]">Status:</span> {trace.status}
              </div>
              <div>
                <span className="font-medium text-[var(--color-foreground)]">Created:</span> {formatTimestamp(trace.created_at)}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                try {
                  const report = generateKnowledgeTraceReport(trace);
                  const filename = `ai-trace-report-${sanitizeFilenamePart(trace.run_id)}.txt`;
                  if (saveTextFile(report, filename)) {
                    toast.success("AI trace report saved");
                    return;
                  }
                  toast.error("AI trace report save failed.");
                } catch {
                  toast.error("AI trace report save failed.");
                }
              }}
            >
              Save AI Report
            </Button>
            <Button variant={viewMode === "table" ? "primary" : "secondary"} size="sm" onClick={() => setViewMode("table")}>
              Table view
            </Button>
            <Button variant={viewMode === "json" ? "primary" : "secondary"} size="sm" onClick={() => setViewMode("json")}>
              JSON view
            </Button>
          </div>
        </div>
      </div>

      {trace.status !== "completed" ? (
        <Alert tone="info">Partial data: this ingest run is not completed yet, so the trace may still change.</Alert>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Sentences</div>
          <div className="mt-2 text-2xl font-semibold">{trace.summary.sentence_count}</div>
        </div>
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Mentions</div>
          <div className="mt-2 text-2xl font-semibold">{trace.summary.mention_count}</div>
        </div>
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Claims</div>
          <div className="mt-2 text-2xl font-semibold">{trace.summary.claim_count}</div>
        </div>
        <div className="app-surface p-4">
          <div className="text-sm text-[var(--color-muted)]">Space-time frames</div>
          <div className="mt-2 text-2xl font-semibold">{trace.summary.space_time_frame_count}</div>
        </div>
      </div>

      <div className="app-surface p-5">
        <h3 className="text-lg font-semibold">Validation hints</h3>
        <div className="mt-4 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-3">
          <div>{validation.skippedSentenceCount} sentence skipped by quality gate</div>
          <div>{validation.rejectedClaimCount} claim rejected by quality gate</div>
          <div>{validation.claimsWithDescribesPredicate} describes claim still stored</div>
          <div>{validation.badSubjectClaimCount} claim has bad subject</div>
          <div>{validation.questionSentenceCount} question sentence produced diagnostics</div>
          <div>{validation.fragmentSentenceCount} fragment sentence produced diagnostics</div>
          <div>{validation.sentencesWithoutMentions} sentence has no mention</div>
          <div>{validation.sentencesWithoutClaims} sentence has no claim</div>
          <div>{validation.claimsWithUnknownType} claim has unknown type</div>
          <div>Unknown type ratio: {formatRatio(validation.claimsWithUnknownType, validation.claimCount)}</div>
          <div>{validation.claimsWithLowConfidence} claim has low confidence</div>
          <div>Low confidence ratio: {formatRatio(validation.claimsWithLowConfidence, validation.claimCount)}</div>
          <div>{validation.claimsWithUnknownTime} claim has unknown time</div>
          <div>{validation.claimsWithUnknownSpace} claim has unknown space</div>
          <div>{validation.unknownSpaceRelevantCount} claim has relevant unknown space</div>
          <div>{validation.stopwordSubjectCount} claim has stopword subject</div>
          <div>{validation.claimsWithDescribesPredicate} claim uses describes predicate</div>
          <div>Describes ratio: {formatRatio(validation.claimsWithDescribesPredicate, validation.claimCount)}</div>
          <div>{validation.claimsWithoutRealSubject} claim has no real subject</div>
          <div>{validation.claimsWithoutStoredSpaceTimeFrame} claim has no stored space-time frame</div>
        </div>
        {validation.qualityTodo ? (
          <div className="mt-3 text-xs text-[var(--color-muted)]">{validation.qualityTodo}</div>
        ) : null}
      </div>

      <div className="app-surface p-5">
        <h3 className="text-lg font-semibold">Quality Gate Summary</h3>
        <div className="mt-4 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-3">
          <div>skipped_sentence_count: {validation.skippedSentenceCount}</div>
          <div>rejected_claim_count: {validation.rejectedClaimCount}</div>
          <div>describes_claim_count: {validation.claimsWithDescribesPredicate}</div>
          <div>bad_subject_claim_count: {validation.badSubjectClaimCount}</div>
          <div>question_sentence_count: {validation.questionSentenceCount}</div>
          <div>fragment_sentence_count: {validation.fragmentSentenceCount}</div>
        </div>
      </div>

      <div className="app-surface p-5">
        <h3 className="text-lg font-semibold">Tension / Retrieval Summary</h3>
        <div className="mt-4 grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-3">
          <div>tension_analysis_count: {trace.summary.tension_analysis_count ?? trace.tension_analyses?.length ?? 0}</div>
          <div>hard_conflict_count: {trace.summary.hard_conflict_count ?? 0}</div>
          <div>temporal_change_count: {trace.summary.temporal_change_count ?? 0}</div>
          <div>retrieval_chunk_count: {trace.summary.retrieval_chunk_count ?? trace.retrieval_chunks?.length ?? 0}</div>
          <div>conflicting_chunk_count: {trace.summary.conflicting_chunk_count ?? 0}</div>
          <div>temporal_context_included: {trace.summary.temporal_context_included ? "true" : "false"}</div>
        </div>
      </div>

      <details open className="app-surface p-5">
        <summary className="cursor-pointer text-lg font-semibold">TENSION ANALYSES</summary>
        <div className="mt-4 grid gap-3">
          {(trace.tension_analyses ?? []).length ? (
            (trace.tension_analyses ?? []).map((item, index) => (
              <pre
                key={String(item.tension_analysis_id ?? index)}
                className="overflow-x-auto rounded border border-[var(--color-border)] bg-[var(--color-background)] p-3 text-xs"
              >
                {JSON.stringify(item, null, 2)}
              </pre>
            ))
          ) : (
            <div className="text-sm text-[var(--color-muted)]">missing from report</div>
          )}
        </div>
      </details>

      <details open className="app-surface p-5">
        <summary className="cursor-pointer text-lg font-semibold">RETRIEVAL CHUNKS</summary>
        <div className="mt-4 grid gap-3">
          {(trace.retrieval_chunks ?? []).length ? (
            (trace.retrieval_chunks ?? []).map((item, index) => (
              <div key={String(item.profile_id ?? index)} className="rounded border border-[var(--color-border)] bg-[var(--color-background)] p-3 text-xs">
                <div className="mb-2 font-semibold">{item.entity_name ?? item.canonical_key ?? "retrieval chunk"}</div>
                <pre className="whitespace-pre-wrap rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-2 font-mono text-[11px]">
                  {item.retrieval_chunk_text ?? "missing chunk text"}
                </pre>
              </div>
            ))
          ) : (
            <div className="text-sm text-[var(--color-muted)]">missing from report</div>
          )}
        </div>
      </details>

      <div className="app-surface p-5">
        <h3 className="text-lg font-semibold">Local Entities</h3>
        <p className="mt-1 text-xs text-[var(--color-muted)]">
          Debug / validation view. Coherence threshold for “low”: &lt; {LOCAL_ENTITY_LOW_COHERENCE_THRESHOLD}.
        </p>
        <div className="mt-4 flex flex-wrap items-end gap-4 border-b border-[var(--color-border)] pb-4 text-sm">
          <label className="grid gap-1">
            <span className="text-xs uppercase text-[var(--color-muted)]">entity_type</span>
            <select
              className="rounded border border-[var(--color-border)] bg-transparent px-2 py-1.5 font-mono text-xs"
              value={localEntityTypeFilter}
              onChange={(e) => setLocalEntityTypeFilter(e.target.value)}
            >
              {localEntityTypeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </label>
          <label className="flex cursor-pointer items-center gap-2 font-mono text-xs">
            <input
              type="checkbox"
              checked={localEntityLowCoherenceOnly}
              onChange={(e) => setLocalEntityLowCoherenceOnly(e.target.checked)}
            />
            low coherence only
          </label>
          <label className="flex cursor-pointer items-center gap-2 font-mono text-xs">
            <input
              type="checkbox"
              checked={localEntityUnknownTypeOnly}
              onChange={(e) => setLocalEntityUnknownTypeOnly(e.target.checked)}
            />
            unknown type only
          </label>
        </div>
        <div className="mt-3 font-mono text-xs text-[var(--color-muted)]">
          showing {filteredLocalEntities.length} / {(trace.local_entities ?? []).length} entities
        </div>
        {(trace.local_entities ?? []).length === 0 ? (
          <div className="mt-4 text-sm text-[var(--color-muted)]">No local_entities on this trace (resolver / DB empty).</div>
        ) : filteredLocalEntities.length === 0 ? (
          <div className="mt-4 text-sm text-[var(--color-muted)]">No entities match the current filters.</div>
        ) : (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {filteredLocalEntities.map((entity, idx) => (
              <div
                key={entity.local_entity_id || `le-${idx}`}
                className="space-y-2 border border-[var(--color-border)] bg-[var(--color-background)] p-3 text-xs"
              >
                <div className="font-mono">
                  <span className="text-[var(--color-muted)]">canonical_name </span>
                  <span className="break-words">{entity.canonical_name || "-"}</span>
                </div>
                <div className="font-mono">
                  <span className="text-[var(--color-muted)]">entity_type </span>
                  {entity.entity_type || "unknown"}
                </div>
                <div className="font-mono">
                  <span className="text-[var(--color-muted)]">coherence_score </span>
                  {Number(entity.coherence_score ?? 0).toFixed(3)}
                </div>
                <div className="font-mono">
                  <span className="text-[var(--color-muted)]">claim count </span>
                  {entity.claim_ids?.length ?? 0}
                  <span className="text-[var(--color-muted)]"> · mention count </span>
                  {entity.mention_ids?.length ?? 0}
                </div>
                <div className="font-mono">
                  <div className="text-[var(--color-muted)]">surface_forms</div>
                  <div className="mt-1 break-words">
                    {(entity.surface_forms ?? []).length ? (entity.surface_forms ?? []).join(" | ") : "-"}
                  </div>
                </div>
                <div className="font-mono">
                  <div className="text-[var(--color-muted)]">linked claims</div>
                  <ul className="mt-1 list-inside list-disc space-y-0.5 break-words">
                    {(entity.claim_ids ?? []).length ? (
                      (entity.claim_ids ?? []).map((cid) => {
                        const c = claimLookup.get(cid);
                        return (
                          <li key={cid}>
                            {c ? formatLinkedClaimOneLiner(c) : <span className="text-[var(--color-muted)]">(missing in trace) {cid}</span>}
                          </li>
                        );
                      })
                    ) : (
                      <li className="text-[var(--color-muted)]">(none)</li>
                    )}
                  </ul>
                </div>
                <div className="font-mono">
                  <div className="text-[var(--color-muted)]">explanation</div>
                  <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-words rounded border border-[var(--color-border)] bg-[var(--color-background)] p-2 text-[10px] leading-snug">
                    {entity.explanation && Object.keys(entity.explanation).length > 0
                      ? JSON.stringify(entity.explanation, null, 2)
                      : "{}"}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {viewMode === "json" ? (
        <div className="app-surface p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-lg font-semibold">Raw JSON</h3>
            <Button
              variant="secondary"
              size="sm"
              onClick={async () => {
                if (await copyTextToClipboard(prettyJson)) {
                  toast.success("Trace JSON copied");
                  return;
                }
                toast.error("Trace JSON copy failed.");
              }}
            >
              Copy JSON
            </Button>
          </div>
          <pre className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4 text-xs">
            {prettyJson}
          </pre>
        </div>
      ) : (
        <>
          <div className="app-surface p-5">
            <div className="grid gap-3 md:grid-cols-4">
              <input
                className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
                placeholder="Search sentence text"
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
              />
              <select
                className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
                value={claimTypeFilter}
                onChange={(event) => setClaimTypeFilter(event.target.value)}
              >
                {claimTypes.map((claimType) => (
                  <option key={claimType} value={claimType}>
                    {claimType}
                  </option>
                ))}
              </select>
              <select
                className="rounded-lg border border-[var(--color-border)] bg-transparent px-3 py-2 text-sm"
                value={confidenceFilter}
                onChange={(event) => setConfidenceFilter(event.target.value as ConfidenceFilter)}
              >
                <option value="all">all</option>
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
              <label className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={showUnknownSpaceTimeOnly}
                  onChange={(event) => setShowUnknownSpaceTimeOnly(event.target.checked)}
                />
                Only unknown space-time
              </label>
            </div>
          </div>

          {!filteredSentences.length ? (
            <Alert tone="info">No trace rows match the current filters.</Alert>
          ) : null}

          {filteredSentences.map((sentence) => (
            <div key={sentence.sentence_id} className="app-surface p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Sentence #{sentence.order_index}</div>
                  <div className="mt-2 text-base font-medium">{sentence.text}</div>
                  <div className="mt-1 text-sm text-[var(--color-muted)]">Language: {sentence.language || "unknown"}</div>
                </div>
              </div>

              <div className="mt-4">
                <div className="text-sm font-medium">Mentions</div>
                {(sentence.mentions ?? []).length ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {sentence.mentions.map((mention) => (
                      <span
                        key={mention.mention_id}
                        className="inline-flex rounded-full border border-[var(--color-border)] px-3 py-1 text-xs"
                      >
                        {mention.surface_text} / {mention.mention_type} / {mention.confidence}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="mt-2 text-sm text-[var(--color-muted)]">No mentions extracted yet</div>
                )}
              </div>

              <div className="mt-5 overflow-x-auto">
                {(sentence.claims ?? []).length ? (
                  <table className="min-w-full border-separate border-spacing-0 text-sm">
                    <thead>
                      <tr className="text-left text-[var(--color-muted)]">
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Subject</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Predicate</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Object</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Claim type</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Claim group</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Confidence</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Conflict</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Time mode</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium">Space mode</th>
                        <th className="border-b border-[var(--color-border)] px-3 py-2 font-medium"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {sentence.claims.map((claim) => {
                        const expanded = !!expandedClaims[claim.claim_id];
                        const timeMode = getClaimTimeMode(claim);
                        const spaceMode = getClaimSpaceMode(claim);
                        return (
                          <Fragment key={claim.claim_id}>
                            <tr>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">{claim.subject_text || "-"}</td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">{claim.predicate || "-"}</td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">{claim.object_text || "-"}</td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">
                                <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-medium", badgeToneForClaimType(claim.claim_type))}>
                                  {claim.claim_type}
                                </span>
                              </td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">{claim.claim_group || "-"}</td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">
                                <span
                                  className={cn(
                                    "inline-flex rounded-full px-2.5 py-1 text-xs font-medium",
                                    getConfidenceBucket(claim.confidence) === "high" && "bg-emerald-500/15 text-emerald-700",
                                    getConfidenceBucket(claim.confidence) === "medium" && "bg-amber-500/15 text-amber-700",
                                    getConfidenceBucket(claim.confidence) === "low" && "bg-red-500/15 text-red-700"
                                  )}
                                >
                                  {claim.confidence}
                                </span>
                              </td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">{claim.conflict_behavior}</td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">
                                <span
                                  className={cn(
                                    "inline-flex rounded-full px-2.5 py-1 text-xs font-medium",
                                    badgeToneForSpaceTime(timeMode)
                                  )}
                                >
                                  {timeMode}
                                </span>
                              </td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 align-top">
                                <span
                                  className={cn(
                                    "inline-flex rounded-full px-2.5 py-1 text-xs font-medium",
                                    badgeToneForSpaceTime(spaceMode)
                                  )}
                                >
                                  {spaceMode}
                                </span>
                              </td>
                              <td className="border-b border-[var(--color-border)] px-3 py-3 text-right align-top">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() =>
                                    setExpandedClaims((current) => ({ ...current, [claim.claim_id]: !current[claim.claim_id] }))
                                  }
                                >
                                  {expanded ? "Hide" : "Details"}
                                </Button>
                              </td>
                            </tr>
                            {expanded ? (
                              <tr>
                                <td className="px-3 py-3" colSpan={10}>
                                  <ClaimDetails claim={claim} />
                                </td>
                              </tr>
                            ) : null}
                          </Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                ) : (
                  <div className="text-sm text-[var(--color-muted)]">No claims extracted yet</div>
                )}
              </div>

              {(sentence.claims ?? []).length > 0 && !(sentence.claims ?? []).some((claim) => claim.space_time_frame) ? (
                <div className="mt-3 text-sm text-[var(--color-muted)]">No space-time frame yet</div>
              ) : null}
            </div>
          ))}
        </>
      )}
    </section>
  );
}
