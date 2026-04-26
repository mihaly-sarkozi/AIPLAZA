import type { IngestRunTrace, IngestRunTraceClaim, IngestRunTraceSentence } from "../services";

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

type TraceValidation = {
  claimCount: number;
  sentencesWithoutMentions: number;
  sentencesWithoutClaims: number;
  claimsWithUnknownType: number;
  claimsWithLowConfidence: number;
  claimsWithUnknownTime: number;
  claimsWithUnknownSpace: number;
  claimsWithUnknownSpaceRelevant: number;
  claimsWithStopwordSubject: number;
  claimsWithDescribesPredicate: number;
  claimsWithNoRealSubject: number;
  claimsWithoutStoredSpaceTimeFrame: number;
  skippedSentenceCount: number;
  rejectedClaimCount: number;
  badSubjectClaimCount: number;
  questionSentenceCount: number;
  fragmentSentenceCount: number;
};

type TraceFieldQuality = {
  averageSubjectTokenCount: number;
  longSubjectCount: number;
  claimsWithConjunctionInObject: number;
  uncertaintyClaimCount: number;
  numericEntityAsTimeCount: number;
  carryoverSubjectErrorCount: number;
  contextCarryoverAppliedCount: number;
  contextCarryoverBlockedCount: number;
  sourcePhraseStrippedCount: number;
  subjectSuffixNormalizedCount: number;
  carryoverMissingSubjectErrorCount: number;
  locationClaimsWithBoundedSpace: number;
  locationClaimsWithUnknownSpace: number;
  relationPatternErrorCount: number;
  historicalTimeFrameErrorCount: number;
  weakDuplicateClaimCount: number;
};

type TraceSentenceLanguageSummary = {
  sourceLanguage: string;
  hasMixedSourceLanguage: boolean;
  counts: {
    hu: number;
    en: number;
    es: number;
    other: number;
    na: number;
  };
};

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

const OBJECT_CONJUNCTIONS = [" but ", " however ", " pero ", " viszont ", " azonban ", " y ", " and "];
const UNCERTAINTY_MARKERS = [
  "maybe",
  "not sure",
  "unclear",
  "perhaps",
  "talan",
  "talán",
  "nem biztos",
  "quizas",
  "quizás",
  "tal vez",
];
const LOCATION_KEYWORDS = [
  "office",
  "location",
  "site",
  "oficina",
  "sede",
  "ubicacion",
  "ubicación",
  "iroda",
  "telephely",
  "helyszin",
  "helyszín",
];
const MODAL_PREDICATES = new Set(["kell", "kötelező", "igenyel", "igényel", "must", "required", "requires", "debe", "obligatorio"]);
const USE_PREDICATES = new Set(["hasznal", "használ", "use", "uses", "usa", "utiliza"]);
const CARRYOVER_TRIGGER_PREFIXES = [
  "korabban",
  "elotte",
  "kesobb",
  "jelenleg is",
  "akkoriban",
  "previously",
  "earlier",
  "later",
  "at that time",
  "currently",
  "anteriormente",
  "antes",
  "luego",
  "actualmente",
  "en ese momento",
];
const SOURCE_PHRASE_PREFIXES = [
  "a dokumentum szerint",
  "dokumentum szerint",
  "a forras szerint",
  "a szoveg szerint",
  "a riport szerint",
  "according to the document",
  "according to the source",
  "the document says",
  "the report states",
  "segun el documento",
  "segun la fuente",
  "el documento indica",
];
const NON_BLOCKING_CARRYOVER_REASONS = new Set([
  "explicit_subject_kept",
  "explicit_subject_matches_carry_anchor",
  "no_strong_anchor_in_previous_two_sentences",
]);

function foldText(value?: string | null): string {
  return (value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

function stripLeadingTraceArticle(value: string, language?: string | null): string {
  const foldedLanguage = foldText(language);
  const articles =
    foldedLanguage === "hu"
      ? ["a", "az", "egy"]
      : foldedLanguage === "es"
        ? ["el", "la", "los", "las", "un", "una"]
        : ["the", "a", "an"];
  let text = value.trim();
  let changed = true;
  while (changed) {
    changed = false;
    for (const article of articles) {
      const rx = new RegExp(`^${article}\\b\\s*`, "i");
      const next = text.replace(rx, "").trim();
      if (next !== text) {
        text = next;
        changed = true;
        break;
      }
    }
  }
  return text;
}

function stripLeadingSourcePhraseForTrace(value?: string | null): string {
  let text = String(value ?? "").trim();
  const folded = foldText(text);
  const prefix = SOURCE_PHRASE_PREFIXES.find((item) => folded === item || folded.startsWith(`${item} `));
  if (!prefix) return text;
  const tokenCount = prefix.split(/\s+/).length;
  text = text.split(/\s+/).slice(tokenCount).join(" ").replace(/^[,;:–-]\s*/, "").trim();
  return text;
}

function normalizeHuSubjectSuffixForTrace(value?: string | null): string {
  return String(value ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((token) => {
      const folded = foldText(token);
      for (const suffix of ["nal", "nel", "nak", "nek", "ban", "ben"]) {
        if (folded.endsWith(suffix) && token.length > suffix.length + 2) {
          return token.slice(0, -suffix.length);
        }
      }
      const previous = token.charAt(token.length - 2);
      if (folded.endsWith("n") && token.length > 4 && /[áéíóöőúüű]/i.test(previous)) {
        return token.slice(0, -1);
      }
      return token;
    })
    .join(" ")
    .trim();
}

function truncateText(value: string | null | undefined, limit: number): string {
  const text = String(value ?? "").trim();
  if (!text) return "-";
  return text.length <= limit ? text : `${text.slice(0, limit)}...`;
}

function formatPercent(part: number, total: number): string {
  if (!total) return "0.0%";
  return `${((part / total) * 100).toFixed(1)}%`;
}

function getClaimTimeMode(claim: IngestRunTraceClaim): string {
  return claim.space_time_frame?.time_mode || claim.time_mode || "unknown";
}

function getClaimSpaceMode(claim: IngestRunTraceClaim): string {
  return claim.space_time_frame?.space_mode || claim.space_mode || "unknown";
}

function getClaimTimeValue(claim: IngestRunTraceClaim): string {
  const maybeClaimTimeValue = (claim as IngestRunTraceClaim & { time_value?: string | null }).time_value;
  return claim.space_time_frame?.time_value || maybeClaimTimeValue || "";
}

function hasStoredSpaceTimeFrame(claim: IngestRunTraceClaim): boolean {
  return !!claim.space_time_frame && !String(claim.space_time_frame.frame_id || "").startsWith("compat:");
}

function tokenCount(value?: string | null): number {
  return String(value ?? "")
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
}

function hasConjunctionLeakage(value?: string | null): boolean {
  const folded = ` ${foldText(value)} `;
  return OBJECT_CONJUNCTIONS.some((item) => folded.includes(item));
}

function hasUncertainty(text?: string | null): boolean {
  const folded = foldText(text);
  return UNCERTAINTY_MARKERS.some((marker) => folded.includes(foldText(marker)));
}

function isLocationLikeText(text?: string | null): boolean {
  const folded = foldText(text);
  return LOCATION_KEYWORDS.some((keyword) => folded.includes(foldText(keyword)));
}

function hasLocationMention(sentence: IngestRunTraceSentence): boolean {
  return (sentence.mentions ?? []).some((mention) => foldText(mention.mention_type) === "location");
}

function isUnknownSpaceRelevant(sentence: IngestRunTraceSentence, claim: IngestRunTraceClaim): boolean {
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

function isWeakContextualObject(text?: string | null): boolean {
  const folded = foldText(text);
  if (!folded) return true;
  if (/(?:nal|nel|ban|ben|hoz|hez|hoz|kent|kor)$/.test(folded)) return true;
  if (/^(?:for|at|in|on|para|en)\b/.test(folded)) return true;
  return false;
}

function looksLikeRelationPatternError(claim: IngestRunTraceClaim): boolean {
  if (foldText(claim.predicate) !== "vezetoje") return false;
  const subject = foldText(claim.subject_text);
  const object = foldText(claim.object_text);
  if (subject.includes(" a ")) return true;
  if (object.endsWith(" vezetoje")) return true;
  return false;
}

function hasHistoricalHint(claim: IngestRunTraceClaim): boolean {
  const combined = foldText(`${claim.claim_text} ${claim.predicate} ${claim.object_text ?? ""} ${getClaimTimeValue(claim)}`);
  return /\b(korabban|before|previously|earlier|antes|anteriormente|estaba|was inactive|in \d{4}|en \d{4}|(?:19|20)\d{2}-?ben|(?:19|20)\d{2}-?ban)\b/.test(
    combined
  );
}

function looksLikeHistoricalTimeFrameError(claim: IngestRunTraceClaim): boolean {
  if (!hasHistoricalHint(claim)) return false;
  const timeMode = getClaimTimeMode(claim);
  const timeValue = foldText(getClaimTimeValue(claim));
  if (timeMode === "current" || timeMode === "unknown") return true;
  if (!timeValue) return true;
  return false;
}

function countWeakDuplicateClaims(sentences: IngestRunTraceSentence[]): number {
  let count = 0;
  for (const sentence of sentences) {
    const claims = sentence.claims ?? [];
    for (const claim of claims) {
      const subject = foldText(claim.subject_text);
      const predicate = foldText(claim.predicate);
      if (!subject || !USE_PREDICATES.has(predicate)) continue;
      const hasCompetingModal = claims.some(
        (other) =>
          other.claim_id !== claim.claim_id &&
          foldText(other.subject_text) === subject &&
          MODAL_PREDICATES.has(foldText(other.predicate)) &&
          tokenCount(other.object_text) >= 2
      );
      if (hasCompetingModal && isWeakContextualObject(claim.object_text)) {
        count += 1;
      }
    }
  }
  return count;
}

function looksLikeNumericEntityUsedAsTime(sentence: IngestRunTraceSentence, claim: IngestRunTraceClaim): boolean {
  const timeValue = foldText(getClaimTimeValue(claim));
  if (!/^(19|20)\d{2}$/.test(timeValue)) return false;
  const sentenceText = String(sentence.text ?? "");
  if (
    new RegExp(`\\b${timeValue}-?(?:ben|ban)\\b`, "i").test(sentenceText) ||
    new RegExp(`\\b(?:in|before|after|since|en|antes|despues|después|desde)\\s+${timeValue}\\b`, "i").test(sentenceText)
  ) {
    return false;
  }
  const combined = [claim.subject_text, claim.object_text, claim.claim_text].filter(Boolean).join(" ");
  const rawCombined = String(combined ?? "");
  return /\b[A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű.-]*\s+(19|20)\d{2}\b/u.test(rawCombined);
}

function looksLikeCarryoverSubjectError(
  sentenceClaims: IngestRunTraceClaim[],
  claim: IngestRunTraceClaim,
  index: number
): boolean {
  if (index === 0) return false;
  const firstSubject = foldText(sentenceClaims[0]?.subject_text);
  const subject = foldText(claim.subject_text);
  if (!firstSubject || !subject || subject === firstSubject) return false;
  if (!subject.startsWith(`${firstSubject} `)) return false;
  if (tokenCount(claim.subject_text) <= tokenCount(sentenceClaims[0]?.subject_text) + 1) return false;
  const previousPredicates = sentenceClaims
    .slice(0, index)
    .map((item) => foldText(item.predicate))
    .filter(Boolean);
  return previousPredicates.some((predicate) => subject.includes(predicate));
}

function isRealSubject(subject?: string | null): boolean {
  const folded = foldText(subject);
  if (!folded) return false;
  if (TRACE_STOPWORDS.has(folded)) return false;
  if (/^(19|20)\d{2}$/.test(folded)) return false;
  if (TRACE_MONTHS.has(folded)) return false;
  return true;
}

function isContextCarryoverApplied(claim: IngestRunTraceClaim): boolean {
  return claim.context_subject_applied === true || claim.context_subject_applied === "yes";
}

function isContextCarryoverBlocked(claim: IngestRunTraceClaim): boolean {
  const applied = claim.context_subject_applied;
  if (applied !== false && applied !== "no") return false;
  const reason = String(claim.context_subject_reason ?? "");
  return !!reason && !NON_BLOCKING_CARRYOVER_REASONS.has(reason);
}

function hasCarryoverTrigger(sentence: IngestRunTraceSentence): boolean {
  const folded = foldText(sentence.text);
  return CARRYOVER_TRIGGER_PREFIXES.some((prefix) => folded === prefix || folded.startsWith(`${prefix} `));
}

function hasSourcePhraseStripped(sentence: IngestRunTraceSentence, claim: IngestRunTraceClaim): boolean {
  const foldedSentence = foldText(sentence.text);
  const sourcePrefix = SOURCE_PHRASE_PREFIXES.find((prefix) => foldedSentence === prefix || foldedSentence.startsWith(`${prefix} `));
  if (!sourcePrefix) return false;
  const foldedSubject = foldText(claim.subject_text);
  return !!foldedSubject && !foldedSubject.startsWith(sourcePrefix);
}

function getRawSubjectPrefix(sentence: IngestRunTraceSentence, claim: IngestRunTraceClaim): string {
  const text = String(sentence.text ?? "");
  const predicate = String(claim.predicate ?? "").trim();
  if (!text || !predicate) return "";
  const idx = foldText(text).indexOf(foldText(predicate));
  if (idx <= 0) return "";
  return text.slice(0, idx).trim();
}

function hasSubjectSuffixNormalized(sentence: IngestRunTraceSentence, claim: IngestRunTraceClaim): boolean {
  if (foldText(sentence.language) !== "hu") return false;
  const rawPrefix = getRawSubjectPrefix(sentence, claim);
  if (!rawPrefix) return false;
  const sourceStripped = stripLeadingSourcePhraseForTrace(rawPrefix);
  const articleStripped = stripLeadingTraceArticle(sourceStripped, sentence.language);
  const normalized = normalizeHuSubjectSuffixForTrace(articleStripped);
  return foldText(articleStripped) !== foldText(normalized) && foldText(normalized) === foldText(claim.subject_text);
}

function summarizeSentenceLanguages(trace: IngestRunTrace): TraceSentenceLanguageSummary {
  const counts = {
    hu: 0,
    en: 0,
    es: 0,
    other: 0,
    na: 0,
  };

  for (const sentence of trace.sentences ?? []) {
    const language = foldText(sentence.language);
    if (language === "hu") {
      counts.hu += 1;
    } else if (language === "en") {
      counts.en += 1;
    } else if (language === "es") {
      counts.es += 1;
    } else if (!language || language === "n/a" || language === "unknown") {
      counts.na += 1;
    } else {
      counts.other += 1;
    }
  }

  const activeFamilies = [counts.hu, counts.en, counts.es, counts.other].filter((count) => count > 0).length;
  let sourceLanguage = trace.language || "unknown";
  if (activeFamilies > 1) {
    sourceLanguage = "mixed";
  } else if (counts.hu > 0 && counts.en === 0 && counts.es === 0 && counts.other === 0) {
    sourceLanguage = "hu";
  } else if (counts.en > 0 && counts.hu === 0 && counts.es === 0 && counts.other === 0) {
    sourceLanguage = "en";
  } else if (counts.es > 0 && counts.hu === 0 && counts.en === 0 && counts.other === 0) {
    sourceLanguage = "es";
  }

  return {
    sourceLanguage,
    hasMixedSourceLanguage: activeFamilies > 1,
    counts,
  };
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

function computeValidation(trace: IngestRunTrace): TraceValidation {
  const sentences = trace.sentences ?? [];
  const claims = sentences.flatMap((sentence) => sentence.claims ?? []);
  const quality = getTraceQualitySummary(trace);
  const claimsWithUnknownSpaceRelevant = sentences.reduce((count, sentence) => {
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
    claimsWithUnknownSpaceRelevant,
    claimsWithStopwordSubject: claims.filter((claim) => TRACE_STOPWORDS.has(foldText(claim.subject_text))).length,
    claimsWithDescribesPredicate: quality.describes_claim_count,
    claimsWithNoRealSubject: claims.filter((claim) => !isRealSubject(claim.subject_text)).length,
    claimsWithoutStoredSpaceTimeFrame: claims.filter((claim) => !hasStoredSpaceTimeFrame(claim)).length,
    skippedSentenceCount: quality.skipped_sentence_count,
    rejectedClaimCount: quality.rejected_claim_count,
    badSubjectClaimCount: quality.bad_subject_claim_count,
    questionSentenceCount: quality.question_sentence_count,
    fragmentSentenceCount: quality.fragment_sentence_count,
  };
}

function computeFieldQuality(trace: IngestRunTrace): TraceFieldQuality {
  const sentences = trace.sentences ?? [];
  const claims = sentences.flatMap((sentence) => sentence.claims ?? []);
  const subjects = claims.map((claim) => tokenCount(claim.subject_text)).filter((count) => count > 0);

  let carryoverSubjectErrorCount = 0;
  let contextCarryoverAppliedCount = 0;
  let contextCarryoverBlockedCount = 0;
  let sourcePhraseStrippedCount = 0;
  let subjectSuffixNormalizedCount = 0;
  let carryoverMissingSubjectErrorCount = 0;
  let numericEntityAsTimeCount = 0;
  let relationPatternErrorCount = 0;
  let historicalTimeFrameErrorCount = 0;
  for (const sentence of sentences) {
    for (const [index, claim] of (sentence.claims ?? []).entries()) {
      if (isContextCarryoverApplied(claim)) {
        contextCarryoverAppliedCount += 1;
      }
      if (isContextCarryoverBlocked(claim)) {
        contextCarryoverBlockedCount += 1;
      }
      if (hasSourcePhraseStripped(sentence, claim)) {
        sourcePhraseStrippedCount += 1;
      }
      if (hasSubjectSuffixNormalized(sentence, claim)) {
        subjectSuffixNormalizedCount += 1;
      }
      if ((hasCarryoverTrigger(sentence) || isContextCarryoverApplied(claim)) && !isRealSubject(claim.subject_text)) {
        carryoverMissingSubjectErrorCount += 1;
      }
      if (looksLikeCarryoverSubjectError(sentence.claims ?? [], claim, index)) {
        carryoverSubjectErrorCount += 1;
      }
      if (looksLikeNumericEntityUsedAsTime(sentence, claim)) {
        numericEntityAsTimeCount += 1;
      }
      if (looksLikeRelationPatternError(claim)) {
        relationPatternErrorCount += 1;
      }
      if (looksLikeHistoricalTimeFrameError(claim)) {
        historicalTimeFrameErrorCount += 1;
      }
    }
  }

  const locationClaims = claims.filter(
    (claim) => isLocationLikeText(claim.subject_text) || isLocationLikeText(claim.object_text) || isLocationLikeText(claim.claim_text)
  );

  return {
    averageSubjectTokenCount:
      subjects.length > 0 ? Number((subjects.reduce((sum, count) => sum + count, 0) / subjects.length).toFixed(2)) : 0,
    longSubjectCount: claims.filter((claim) => tokenCount(claim.subject_text) > 5).length,
    claimsWithConjunctionInObject: claims.filter((claim) => hasConjunctionLeakage(claim.object_text)).length,
    uncertaintyClaimCount: claims.filter(
      (claim) => hasUncertainty(claim.object_text) || hasUncertainty(claim.claim_text) || hasUncertainty(claim.subject_text)
    ).length,
    numericEntityAsTimeCount,
    carryoverSubjectErrorCount,
    contextCarryoverAppliedCount,
    contextCarryoverBlockedCount,
    sourcePhraseStrippedCount,
    subjectSuffixNormalizedCount,
    carryoverMissingSubjectErrorCount,
    locationClaimsWithBoundedSpace: locationClaims.filter((claim) => getClaimSpaceMode(claim) === "bounded").length,
    locationClaimsWithUnknownSpace: locationClaims.filter((claim) => getClaimSpaceMode(claim) === "unknown").length,
    relationPatternErrorCount,
    historicalTimeFrameErrorCount,
    weakDuplicateClaimCount: countWeakDuplicateClaims(sentences),
  };
}

function isLocalResolverReady(validation: TraceValidation, fieldQuality: TraceFieldQuality): boolean {
  if (validation.claimCount <= 0) {
    return false;
  }
  const unknownTypeRatio = validation.claimsWithUnknownType / validation.claimCount;
  return (
    validation.claimsWithDescribesPredicate === 0 &&
    unknownTypeRatio < 0.1 &&
    fieldQuality.relationPatternErrorCount === 0 &&
    fieldQuality.weakDuplicateClaimCount === 0 &&
    fieldQuality.longSubjectCount <= 1 &&
    fieldQuality.claimsWithConjunctionInObject === 0 &&
    fieldQuality.uncertaintyClaimCount === 0 &&
    fieldQuality.numericEntityAsTimeCount === 0 &&
    fieldQuality.carryoverMissingSubjectErrorCount === 0
  );
}

function buildTopProblems(trace: IngestRunTrace, validation: TraceValidation, fieldQuality: TraceFieldQuality): string[] {
  const problems: string[] = [];
  const claims = validation.claimCount;
  const languageSummary = summarizeSentenceLanguages(trace);

  if (trace.summary.sentence_count > 0 && trace.summary.claim_count > trace.summary.sentence_count * 2) {
    problems.push("Claim explosion detected");
  }
  if (validation.claimsWithDescribesPredicate > 0) {
    problems.push("Describes fallback still stored");
  }
  if (validation.questionSentenceCount > 0 || validation.fragmentSentenceCount > 0) {
    problems.push("Noise sentences generated claims");
  }

  if (claims > 0 && validation.claimsWithDescribesPredicate > claims * 0.3) {
    problems.push("High describes predicate ratio: predicate extraction is weak.");
  }
  if (claims > 0 && validation.claimsWithUnknownType > claims * 0.3) {
    problems.push("High unknown/other claim type ratio: claim typing is weak.");
  }
  if (claims > 0 && validation.claimsWithLowConfidence > claims * 0.3) {
    problems.push("High low-confidence claim ratio: subject/predicate/object extraction needs improvement.");
  }
  if (validation.claimsWithStopwordSubject > 0) {
    problems.push("Stopword subjects detected: article/stopword filtering is incomplete.");
  }
  if (validation.claimsWithNoRealSubject > 0) {
    problems.push("Claims without real subject detected.");
  }
  if (validation.claimsWithoutStoredSpaceTimeFrame > 0) {
    problems.push("Some claims have no stored space-time frame.");
  }
  if (validation.claimsWithUnknownSpaceRelevant > 0) {
    problems.push("Relevant claims still have unknown space.");
  }
  if (fieldQuality.longSubjectCount > 0) {
    problems.push("Long subject detected");
  }
  if (fieldQuality.claimsWithConjunctionInObject > 0) {
    problems.push("Conjunction leakage in object");
  }
  if (fieldQuality.numericEntityAsTimeCount > 0) {
    problems.push("Numeric entity mistaken as year");
  }
  if (fieldQuality.locationClaimsWithUnknownSpace > 0) {
    problems.push("Location claim has unknown space");
  }
  if (fieldQuality.carryoverSubjectErrorCount > 0) {
    problems.push("Carryover subject error");
  }
  if (fieldQuality.carryoverMissingSubjectErrorCount > 0) {
    problems.push("Carryover missing subject error");
  }
  if (fieldQuality.relationPatternErrorCount > 0) {
    problems.push("Relation pattern extraction error");
  }
  if (fieldQuality.historicalTimeFrameErrorCount > 0) {
    problems.push("Historical time frame extraction error");
  }
  if (fieldQuality.weakDuplicateClaimCount > 0) {
    problems.push("Weak duplicate claim detected");
  }

  if (languageSummary.hasMixedSourceLanguage) {
    problems.push("Possible mixed-language source: sentence-level language detection may be needed.");
  }

  if (problems.length === 0) {
    problems.push("No major structural problems detected in the current trace.");
  }

  return problems;
}

function buildCompactClaim(sentence: IngestRunTraceSentence, claim: IngestRunTraceClaim): string {
  return `[${sentence.language || "n/a"}] ${claim.subject_text || "-"} --${claim.predicate || "-"}--> ${truncateText(
    claim.object_text,
    180
  )} | ${claim.claim_type}/${claim.claim_group} | conf=${claim.confidence} | time=${getClaimTimeMode(claim)} | space=${getClaimSpaceMode(claim)}`;
}

const LOCAL_ENTITY_LOW_COHERENCE_THRESHOLD = 0.7;

function buildClaimLookup(
  trace: IngestRunTrace
): Map<string, { sentence: IngestRunTraceSentence; claim: IngestRunTraceClaim }> {
  const m = new Map<string, { sentence: IngestRunTraceSentence; claim: IngestRunTraceClaim }>();
  for (const sentence of trace.sentences ?? []) {
    for (const claim of sentence.claims ?? []) {
      const id = claim.claim_id;
      if (id) {
        m.set(id, { sentence, claim });
      }
    }
  }
  return m;
}

function formatHumanReadableClaimLine(claim: IngestRunTraceClaim): string {
  const subj = (claim.subject_text || "-").trim() || "-";
  const pred = (claim.predicate || "-").trim() || "-";
  const objRaw = claim.object_text;
  const obj =
    objRaw != null && String(objRaw).trim() !== "" ? truncateText(String(objRaw), 180) : "-";
  return `${subj} --${pred}--> ${obj}`;
}

function deriveLocalEntityQuality(trace: IngestRunTrace) {
  const entities = trace.local_entities ?? [];
  const nList = entities.length;
  const nSummary =
    trace.summary.local_entity_count ?? trace.summary.local_entity_cluster_count ?? 0;
  const entityCount = nList > 0 ? nList : nSummary;

  let lowCoherence: number;
  if (typeof trace.summary.low_coherence_local_entity_count === "number") {
    lowCoherence = trace.summary.low_coherence_local_entity_count;
  } else if (nList > 0) {
    lowCoherence = entities.filter((e) => (e.coherence_score ?? 0) < LOCAL_ENTITY_LOW_COHERENCE_THRESHOLD).length;
  } else {
    lowCoherence = 0;
  }

  let unknownType: number;
  if (typeof trace.summary.unknown_entity_type_count === "number") {
    unknownType = trace.summary.unknown_entity_type_count;
  } else if (nList > 0) {
    unknownType = entities.filter((e) => (e.entity_type || "").toLowerCase() === "unknown").length;
  } else {
    unknownType = 0;
  }

  const claimCounts = entities.map((e) => e.claim_ids?.length ?? 0);
  const totalAttached = claimCounts.reduce((sum, c) => sum + c, 0);
  const avgClaims = nList > 0 ? totalAttached / nList : 0;
  const maxClaims = nList > 0 ? Math.max(0, ...claimCounts) : 0;

  return { entityCount, lowCoherence, unknownType, avgClaims, maxClaims };
}

function formatStringList(values: unknown): string {
  if (!Array.isArray(values) || values.length === 0) {
    return "-";
  }
  return values.map((item) => String(item)).filter(Boolean).join(", ") || "-";
}

function getTechnicalEntityName(entity: NonNullable<IngestRunTrace["technical_entities"]>[number]): string {
  return String(entity.name || entity.canonical_name || "-");
}

function getTechnicalEntityType(entity: NonNullable<IngestRunTrace["technical_entities"]>[number]): string {
  return String(entity.type || entity.entity_type || "unknown");
}

function getTechnicalEntityCoherence(entity: NonNullable<IngestRunTrace["technical_entities"]>[number]): string {
  return String(entity.coherence_state || entity.coherence || "unknown");
}

function getTechnicalClaimGroupCount(
  entity: NonNullable<IngestRunTrace["technical_entities"]>[number],
  key: string
): number {
  const groups = entity.claim_groups ?? entity.claims ?? {};
  const value = groups[key];
  return typeof value === "number" ? value : 0;
}

function getMemoryFactGroupCount(
  chunk: NonNullable<IngestRunTrace["technical_memory_chunks"]>[number],
  key: string
): number {
  return (chunk.facts ?? []).filter((fact) => String(fact.claim_group || "") === key).length;
}

function collectMemoryEvidenceIds(
  chunk: NonNullable<IngestRunTrace["technical_memory_chunks"]>[number],
  key: "claim_id" | "sentence_id"
): string[] {
  const values = new Set<string>();
  for (const fact of chunk.facts ?? []) {
    const value = fact[key];
    if (value) values.add(String(value));
  }
  for (const ref of chunk.evidence_refs ?? []) {
    const value = ref[key];
    if (value) values.add(String(value));
  }
  return [...values].sort();
}

function collectSearchProfileEvidenceIds(
  profile: NonNullable<IngestRunTrace["search_profiles"]>[number],
  key: "claim_ids" | "sentence_ids"
): string[] {
  const values = new Set<string>();
  for (const ref of profile.evidence_refs ?? []) {
    const value = ref[key];
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item) values.add(String(item));
      }
    } else if (value) {
      values.add(String(value));
    }
  }
  return [...values].sort();
}

function deriveTechnicalMemoryChunkQuality(trace: IngestRunTrace) {
  const chunks = trace.technical_memory_chunks ?? [];
  const chunkCount = chunks.length > 0 ? chunks.length : trace.summary.technical_memory_chunks ?? 0;
  const factCounts = chunks.map((chunk) => chunk.facts?.length ?? 0);
  const totalFacts = factCounts.reduce((sum, count) => sum + count, 0);
  const avgFacts = chunks.length > 0 ? totalFacts / chunks.length : 0;
  const maxFacts = chunks.length > 0 ? Math.max(0, ...factCounts) : 0;

  return {
    chunkCount,
    chunksWithoutSummary: chunks.filter((chunk) => !String(chunk.summary_text || "").trim()).length,
    chunksWithoutFacts: chunks.filter((chunk) => (chunk.facts?.length ?? 0) === 0).length,
    chunksWithoutEvidence: chunks.filter(
      (chunk) =>
        collectMemoryEvidenceIds(chunk, "claim_id").length === 0 ||
        collectMemoryEvidenceIds(chunk, "sentence_id").length === 0
    ).length,
    avgFacts,
    maxFacts,
  };
}

function deriveSearchProfileQuality(trace: IngestRunTrace) {
  const profiles = trace.search_profiles ?? [];
  const profileCount = profiles.length > 0 ? profiles.length : trace.summary.search_profiles ?? 0;
  const keywordCounts = profiles.map((profile) => profile.keywords?.length ?? 0);
  const totalKeywords = keywordCounts.reduce((sum, count) => sum + count, 0);
  const avgKeywords = profiles.length > 0 ? totalKeywords / profiles.length : 0;
  const maxKeywords = profiles.length > 0 ? Math.max(0, ...keywordCounts) : 0;

  return {
    profileCount,
    profilesWithoutCanonicalText: profiles.filter((profile) => !String(profile.canonical_text || "").trim()).length,
    profilesWithoutSearchText: profiles.filter((profile) => !String(profile.search_text || "").trim()).length,
    profilesWithoutKeywords: profiles.filter((profile) => (profile.keywords?.length ?? 0) === 0).length,
    profilesWithoutEvidence: profiles.filter(
      (profile) =>
        collectSearchProfileEvidenceIds(profile, "claim_ids").length === 0 ||
        collectSearchProfileEvidenceIds(profile, "sentence_ids").length === 0
    ).length,
    avgKeywords,
    maxKeywords,
  };
}

export function generateKnowledgeTraceReport(trace: IngestRunTrace): string {
  const validation = computeValidation(trace);
  const fieldQuality = computeFieldQuality(trace);
  const localResolverReady = isLocalResolverReady(validation, fieldQuality);
  const topProblems = buildTopProblems(trace, validation, fieldQuality);
  const languageSummary = summarizeSentenceLanguages(trace);
  const sentences = trace.sentences ?? [];
  const claimEntries = sentences.flatMap((sentence) =>
    (sentence.claims ?? []).map((claim) => ({
      sentence,
      claim,
    }))
  );
  const visibleClaims = claimEntries.slice(0, 60);
  const lines: string[] = [];

  lines.push("=== KNOWLEDGE TRACE REPORT ===");
  lines.push(`run_id: ${trace.run_id}`);
  lines.push(`source_id: ${trace.source_id ?? "-"}`);
  lines.push(`source_name: ${trace.source_name ?? "-"}`);
  lines.push(`source_language: ${languageSummary.sourceLanguage}`);
  lines.push(`sentence_languages: hu=${languageSummary.counts.hu}, en=${languageSummary.counts.en}, es=${languageSummary.counts.es}`);
  lines.push(`status: ${trace.status}`);
  lines.push(`created_at: ${trace.created_at}`);
  lines.push("");
  lines.push("SUMMARY:");
  lines.push(`sentences: ${trace.summary.sentence_count}`);
  lines.push(`mentions: ${trace.summary.mention_count}`);
  lines.push(`claims: ${trace.summary.claim_count}`);
  lines.push(`space_time_frames: ${trace.summary.space_time_frame_count}`);
  lines.push(
    `local_entities: ${trace.local_entities?.length ?? trace.summary.local_entity_count ?? trace.summary.local_entity_cluster_count ?? 0}`
  );
  lines.push(`technical_entities: ${trace.technical_entities?.length ?? trace.summary.technical_entities ?? 0}`);
  lines.push(`technical_memory_chunks: ${trace.technical_memory_chunks?.length ?? trace.summary.technical_memory_chunks ?? 0}`);
  lines.push(`search_profiles: ${trace.search_profiles?.length ?? trace.summary.search_profiles ?? 0}`);
  lines.push(`candidate_selection_count: ${trace.summary.candidate_selection_count ?? trace.candidate_selections?.length ?? 0}`);
  lines.push(`candidates_found_count: ${trace.summary.candidates_found_count ?? trace.candidate_selections?.length ?? 0}`);
  lines.push(`candidates_without_evidence_count: ${trace.summary.candidates_without_evidence_count ?? 0}`);
  lines.push(`top_candidate_score: ${Number(trace.summary.top_candidate_score ?? 0).toFixed(2)}`);
  lines.push(`candidate_selection_ready: ${trace.summary.candidate_selection_ready === false ? "false" : "true"}`);
  lines.push(`similarity_analysis_count: ${trace.summary.similarity_analysis_count ?? trace.similarity_analyses?.length ?? 0}`);
  lines.push(`similarity_ready: ${trace.summary.similarity_ready === false ? "false" : "true"}`);
  lines.push(`high_similarity_count: ${trace.summary.high_similarity_count ?? 0}`);
  lines.push(`medium_similarity_count: ${trace.summary.medium_similarity_count ?? 0}`);
  lines.push(`low_similarity_count: ${trace.summary.low_similarity_count ?? 0}`);
  lines.push(`similarity_without_evidence_count: ${trace.summary.similarity_without_evidence_count ?? 0}`);
  lines.push("");
  const leQuality = deriveLocalEntityQuality(trace);
  lines.push("LOCAL ENTITY QUALITY:");
  lines.push(`local_entity_count: ${leQuality.entityCount}`);
  lines.push(`low_coherence_local_entity_count: ${leQuality.lowCoherence}`);
  lines.push(`unknown_entity_type_count: ${leQuality.unknownType}`);
  lines.push(`avg_claims_per_local_entity: ${leQuality.avgClaims.toFixed(2)}`);
  lines.push(`max_claims_per_local_entity: ${leQuality.maxClaims}`);
  lines.push("");
  const tmcQuality = deriveTechnicalMemoryChunkQuality(trace);
  lines.push("TECHNICAL MEMORY CHUNK QUALITY:");
  lines.push(`technical_memory_chunk_count: ${tmcQuality.chunkCount}`);
  lines.push(`chunks_without_summary: ${tmcQuality.chunksWithoutSummary}`);
  lines.push(`chunks_without_facts: ${tmcQuality.chunksWithoutFacts}`);
  lines.push(`chunks_without_evidence: ${tmcQuality.chunksWithoutEvidence}`);
  lines.push(`avg_facts_per_chunk: ${tmcQuality.avgFacts.toFixed(2)}`);
  lines.push(`max_facts_per_chunk: ${tmcQuality.maxFacts}`);
  lines.push("");
  const spQuality = deriveSearchProfileQuality(trace);
  lines.push("SEARCH PROFILE QUALITY:");
  lines.push(`search_profile_count: ${spQuality.profileCount}`);
  lines.push(`profiles_without_canonical_text: ${spQuality.profilesWithoutCanonicalText}`);
  lines.push(`profiles_without_search_text: ${spQuality.profilesWithoutSearchText}`);
  lines.push(`profiles_without_keywords: ${spQuality.profilesWithoutKeywords}`);
  lines.push(`profiles_without_evidence: ${spQuality.profilesWithoutEvidence}`);
  lines.push(`avg_keywords_per_profile: ${spQuality.avgKeywords.toFixed(2)}`);
  lines.push(`max_keywords_per_profile: ${spQuality.maxKeywords}`);
  lines.push("");
  lines.push("CANDIDATE SELECTION QUALITY:");
  lines.push(`candidate_selection_count: ${trace.summary.candidate_selection_count ?? trace.candidate_selections?.length ?? 0}`);
  lines.push(`candidates_found_count: ${trace.summary.candidates_found_count ?? trace.candidate_selections?.length ?? 0}`);
  lines.push(`candidates_without_evidence_count: ${trace.summary.candidates_without_evidence_count ?? 0}`);
  lines.push(`top_candidate_score: ${Number(trace.summary.top_candidate_score ?? 0).toFixed(2)}`);
  lines.push(`candidate_selection_ready: ${trace.summary.candidate_selection_ready === false ? "false" : "true"}`);
  lines.push("");
  lines.push("SIMILARITY QUALITY:");
  lines.push(`similarity_analysis_count: ${trace.summary.similarity_analysis_count ?? trace.similarity_analyses?.length ?? 0}`);
  lines.push(`similarity_ready: ${trace.summary.similarity_ready === false ? "false" : "true"}`);
  lines.push(`high_similarity_count: ${trace.summary.high_similarity_count ?? 0}`);
  lines.push(`medium_similarity_count: ${trace.summary.medium_similarity_count ?? 0}`);
  lines.push(`low_similarity_count: ${trace.summary.low_similarity_count ?? 0}`);
  lines.push(`similarity_without_evidence_count: ${trace.summary.similarity_without_evidence_count ?? 0}`);
  lines.push("");
  lines.push("QUALITY GATE SUMMARY:");
  lines.push(`skipped_sentence_count: ${validation.skippedSentenceCount}`);
  lines.push(`rejected_claim_count: ${validation.rejectedClaimCount}`);
  lines.push(`describes_claim_count: ${validation.claimsWithDescribesPredicate}`);
  lines.push(`bad_subject_claim_count: ${validation.badSubjectClaimCount}`);
  lines.push(`question_sentence_count: ${validation.questionSentenceCount}`);
  lines.push(`fragment_sentence_count: ${validation.fragmentSentenceCount}`);
  if (trace.summary.quality?.todo) {
    lines.push(`quality_todo: ${trace.summary.quality.todo}`);
  }
  lines.push("");
  lines.push("VALIDATION:");
  lines.push(`sentences_without_mentions: ${validation.sentencesWithoutMentions}`);
  lines.push(`sentences_without_claims: ${validation.sentencesWithoutClaims}`);
  lines.push(`claims_with_unknown_type: ${validation.claimsWithUnknownType}`);
  lines.push(`claims_with_low_confidence: ${validation.claimsWithLowConfidence}`);
  lines.push(`claims_with_unknown_time: ${validation.claimsWithUnknownTime}`);
  lines.push(`claims_with_unknown_space: ${validation.claimsWithUnknownSpace}`);
  lines.push(`unknown_space_relevant_count: ${validation.claimsWithUnknownSpaceRelevant}`);
  lines.push(`claims_with_stopword_subject: ${validation.claimsWithStopwordSubject}`);
  lines.push(`claims_with_describes_predicate: ${validation.claimsWithDescribesPredicate}`);
  lines.push(`claims_with_no_real_subject: ${validation.claimsWithNoRealSubject}`);
  lines.push(`claims_without_stored_space_time_frame: ${validation.claimsWithoutStoredSpaceTimeFrame}`);
  lines.push("");
  lines.push("FIELD QUALITY:");
  lines.push(`average_subject_token_count: ${fieldQuality.averageSubjectTokenCount}`);
  lines.push(`long_subject_count: ${fieldQuality.longSubjectCount}`);
  lines.push(`claims_with_conjunction_in_object: ${fieldQuality.claimsWithConjunctionInObject}`);
  lines.push(`uncertainty_claim_count: ${fieldQuality.uncertaintyClaimCount}`);
  lines.push(`numeric_entity_as_time_count: ${fieldQuality.numericEntityAsTimeCount}`);
  lines.push(`carryover_subject_error_count: ${fieldQuality.carryoverSubjectErrorCount}`);
  lines.push(`context_carryover_applied_count: ${fieldQuality.contextCarryoverAppliedCount}`);
  lines.push(`context_carryover_blocked_count: ${fieldQuality.contextCarryoverBlockedCount}`);
  lines.push(`source_phrase_stripped_count: ${fieldQuality.sourcePhraseStrippedCount}`);
  lines.push(`subject_suffix_normalized_count: ${fieldQuality.subjectSuffixNormalizedCount}`);
  lines.push(`carryover_missing_subject_error_count: ${fieldQuality.carryoverMissingSubjectErrorCount}`);
  lines.push(`location_claims_with_bounded_space: ${fieldQuality.locationClaimsWithBoundedSpace}`);
  lines.push(`location_claims_with_unknown_space: ${fieldQuality.locationClaimsWithUnknownSpace}`);
  lines.push(`relation_pattern_error_count: ${fieldQuality.relationPatternErrorCount}`);
  lines.push(`historical_time_frame_error_count: ${fieldQuality.historicalTimeFrameErrorCount}`);
  lines.push(`weak_duplicate_claim_count: ${fieldQuality.weakDuplicateClaimCount}`);
  lines.push(`local_resolver_ready: ${localResolverReady ? "true" : "false"}`);
  lines.push("");
  lines.push("RATIOS:");
  lines.push(`describes_ratio: ${formatPercent(validation.claimsWithDescribesPredicate, validation.claimCount)}`);
  lines.push(`unknown_type_ratio: ${formatPercent(validation.claimsWithUnknownType, validation.claimCount)}`);
  lines.push(`low_confidence_ratio: ${formatPercent(validation.claimsWithLowConfidence, validation.claimCount)}`);
  lines.push(`unknown_time_ratio: ${formatPercent(validation.claimsWithUnknownTime, validation.claimCount)}`);
  lines.push(`unknown_space_ratio: ${formatPercent(validation.claimsWithUnknownSpace, validation.claimCount)}`);
  lines.push(`unknown_space_relevant_ratio: ${formatPercent(validation.claimsWithUnknownSpaceRelevant, validation.claimCount)}`);
  lines.push("");
  lines.push("TOP PROBLEMS:");
  for (const item of topProblems) {
    lines.push(`- ${item}`);
  }
  lines.push("");
  lines.push("LOCAL ENTITIES:");
  lines.push("");
  const sortedLocalEntities = [...(trace.local_entities ?? [])].sort((a, b) =>
    (a.canonical_name || "").localeCompare(b.canonical_name || "", undefined, { sensitivity: "base" })
  );
  const claimById = buildClaimLookup(trace);
  if (sortedLocalEntities.length === 0) {
    lines.push("(none)");
    lines.push("");
  } else {
    sortedLocalEntities.forEach((entity, index) => {
      lines.push(`#${index + 1}`);
      lines.push(`name: ${entity.canonical_name || "-"}`);
      lines.push(`type: ${entity.entity_type || "unknown"}`);
      lines.push(`key: ${entity.normalized_key || "-"}`);
      lines.push(`claims: ${entity.claim_ids?.length ?? 0}`);
      lines.push(`mentions: ${entity.mention_ids?.length ?? 0}`);
      lines.push(`coherence: ${Number(entity.coherence_score ?? 0).toFixed(1)}`);
      const ex = entity.explanation;
      if (ex && Object.keys(ex).length > 0) {
        lines.push("explanation:");
        lines.push(`  grouping_rule: ${ex.grouping_rule ?? "-"}`);
        lines.push(`  normalized_key: ${ex.normalized_key ?? entity.normalized_key ?? "-"}`);
        lines.push(`  entity_type_source: ${ex.entity_type_source ?? "-"}`);
        lines.push(`  claim_count: ${ex.claim_count ?? entity.claim_ids?.length ?? 0}`);
        lines.push(`  surface_form_count: ${ex.surface_form_count ?? entity.surface_forms?.length ?? 0}`);
        lines.push("  coherence_factors:");
        const cfs = ex.coherence_factors ?? [];
        if (cfs.length === 0) {
          lines.push("    - (none)");
        } else {
          for (const f of cfs) {
            lines.push(`    - ${f}`);
          }
        }
      }
      lines.push("claims:");
      const cids = entity.claim_ids ?? [];
      if (cids.length === 0) {
        lines.push("- (none)");
      } else {
        for (const cid of cids) {
          const found = claimById.get(cid);
          if (found) {
            lines.push(`- ${formatHumanReadableClaimLine(found.claim)}`);
          } else {
            lines.push(`- (missing claim ${cid})`);
          }
        }
      }
      lines.push("");
    });
  }
  lines.push("TECHNICAL ENTITIES:");
  lines.push("");
  const technicalEntities = [...(trace.technical_entities ?? [])].sort((a, b) =>
    getTechnicalEntityName(a).localeCompare(getTechnicalEntityName(b), undefined, { sensitivity: "base" })
  );
  if (technicalEntities.length === 0) {
    lines.push("(none)");
    lines.push("");
  } else {
    technicalEntities.forEach((entity, index) => {
      const timeSig = entity.time_signature ?? {};
      const spaceSig = entity.space_signature ?? {};
      const relationSig = entity.relation_signature ?? {};
      lines.push(`#${index + 1}`);
      lines.push(`name: ${getTechnicalEntityName(entity)}`);
      lines.push(`type: ${getTechnicalEntityType(entity)}`);
      lines.push(`local_entity_id: ${entity.local_entity_id ?? "-"}`);
      lines.push(`coherence_state: ${getTechnicalEntityCoherence(entity)}`);
      lines.push(`coherence_score: ${typeof entity.coherence_score === "number" ? entity.coherence_score : "-"}`);
      lines.push("claim_groups:");
      for (const key of ["identity", "descriptor", "state", "relation", "event", "rule", "other"]) {
        lines.push(`  ${key}: ${getTechnicalClaimGroupCount(entity, key)}`);
      }
      lines.push("time_signature:");
      lines.push(`  has_current_claims: ${timeSig.has_current_claims === true ? "true" : "false"}`);
      lines.push(`  has_historical_claims: ${timeSig.has_historical_claims === true ? "true" : "false"}`);
      lines.push(`  time_values: ${formatStringList(timeSig.time_values)}`);
      lines.push(`  dominant_time_mode: ${timeSig.dominant_time_mode ?? "unknown"}`);
      lines.push("space_signature:");
      lines.push(`  has_bounded_space: ${spaceSig.has_bounded_space === true ? "true" : "false"}`);
      lines.push(`  space_values: ${formatStringList(spaceSig.space_values)}`);
      lines.push(`  dominant_space_mode: ${spaceSig.dominant_space_mode ?? "unknown"}`);
      lines.push("relation_signature:");
      lines.push(`  relation_predicates: ${formatStringList(relationSig.relation_predicates)}`);
      lines.push(`  relation_objects: ${formatStringList(relationSig.relation_objects)}`);
      lines.push("");
    });
  }
  lines.push("TECHNICAL MEMORY CHUNKS:");
  lines.push("");
  const technicalMemoryChunks = [...(trace.technical_memory_chunks ?? [])].sort((a, b) =>
    String(a.entity_name || "").localeCompare(String(b.entity_name || ""), undefined, { sensitivity: "base" })
  );
  if (technicalMemoryChunks.length === 0) {
    lines.push("(none)");
    lines.push("");
  } else {
    technicalMemoryChunks.forEach((chunk, index) => {
      const timeProfile = chunk.time_profile ?? {};
      const spaceProfile = chunk.space_profile ?? {};
      lines.push(`#${index + 1}`);
      lines.push(`name: ${chunk.entity_name || "-"}`);
      lines.push(`type: ${chunk.entity_type || "unknown"}`);
      lines.push(`technical_entity_id: ${chunk.technical_entity_id ?? "-"}`);
      lines.push(`local_entity_id: ${chunk.local_entity_id ?? "-"}`);
      lines.push(`coherence_state: ${chunk.coherence_state || "unknown"}`);
      lines.push("summary:");
      lines.push(`  ${chunk.summary_text || "-"}`);
      lines.push("facts:");
      for (const key of ["relation", "state", "rule", "event"]) {
        lines.push(`  ${key}: ${getMemoryFactGroupCount(chunk, key)}`);
      }
      lines.push("time_profile:");
      lines.push(`  dominant: ${timeProfile.dominant_time_mode ?? "unknown"}`);
      lines.push(`  values: ${formatStringList(timeProfile.time_values)}`);
      lines.push("space_profile:");
      lines.push(`  dominant: ${spaceProfile.dominant_space_mode ?? "unknown"}`);
      lines.push(`  values: ${formatStringList(spaceProfile.space_values)}`);
      lines.push("evidence:");
      lines.push(`  claim_ids: ${formatStringList(collectMemoryEvidenceIds(chunk, "claim_id"))}`);
      lines.push(`  sentence_ids: ${formatStringList(collectMemoryEvidenceIds(chunk, "sentence_id"))}`);
      lines.push("");
    });
  }
  lines.push("SEARCH PROFILES:");
  lines.push("");
  const searchProfiles = [...(trace.search_profiles ?? [])].sort((a, b) =>
    String(a.entity_name || "").localeCompare(String(b.entity_name || ""), undefined, { sensitivity: "base" })
  );
  if (searchProfiles.length === 0) {
    lines.push("(none)");
    lines.push("");
  } else {
    searchProfiles.forEach((profile, index) => {
      const timeFilters = profile.time_filters ?? {};
      const spaceFilters = profile.space_filters ?? {};
      lines.push(`#${index + 1}`);
      lines.push(`name: ${profile.entity_name || "-"}`);
      lines.push(`type: ${profile.entity_type || "unknown"}`);
      lines.push(`search_profile_id: ${profile.search_profile_id ?? "-"}`);
      lines.push(`technical_memory_chunk_id: ${profile.technical_memory_chunk_id ?? "-"}`);
      lines.push("canonical_text:");
      lines.push(`  ${profile.canonical_text || "-"}`);
      lines.push("keywords:");
      lines.push(`  ${formatStringList(profile.keywords)}`);
      lines.push("time_filters:");
      lines.push(`  dominant: ${timeFilters.dominant ?? "unknown"}`);
      lines.push(`  values: ${formatStringList(timeFilters.values)}`);
      lines.push("space_filters:");
      lines.push(`  dominant: ${spaceFilters.dominant ?? "unknown"}`);
      lines.push(`  values: ${formatStringList(spaceFilters.values)}`);
      lines.push("evidence:");
      lines.push(`  claim_ids: ${formatStringList(collectSearchProfileEvidenceIds(profile, "claim_ids"))}`);
      lines.push(`  sentence_ids: ${formatStringList(collectSearchProfileEvidenceIds(profile, "sentence_ids"))}`);
      lines.push("");
    });
  }
  lines.push("CANDIDATE SELECTION:");
  lines.push("");
  const candidateSelections = [...(trace.candidate_selections ?? [])].sort(
    (a, b) => Number(b.score ?? b.candidate_score ?? 0) - Number(a.score ?? a.candidate_score ?? 0)
  );
  if (candidateSelections.length === 0) {
    lines.push("(none)");
    lines.push("");
  } else {
    candidateSelections.forEach((candidate, index) => {
      lines.push(`#${index + 1}`);
      lines.push(`candidate_entity_id: ${candidate.candidate_entity_id || "-"}`);
      lines.push(`candidate_name: ${candidate.candidate_name || "-"}`);
      lines.push(`candidate_type: ${candidate.candidate_type || "unknown"}`);
      lines.push(`candidate_source: ${candidate.candidate_source || "unknown"}`);
      lines.push(`score: ${Number(candidate.score ?? candidate.candidate_score ?? 0).toFixed(2)}`);
      lines.push(`reasons: ${(candidate.reasons ?? candidate.candidate_reason ?? []).join(", ") || "-"}`);
      lines.push("evidence:");
      lines.push(`  claim_ids: ${formatStringList(candidate.evidence?.claim_ids)}`);
      lines.push(`  sentence_ids: ${formatStringList(candidate.evidence?.sentence_ids)}`);
      lines.push("");
    });
  }
  lines.push("SIMILARITY ANALYSES:");
  lines.push("");
  const similarityAnalyses = [...(trace.similarity_analyses ?? [])].sort(
    (a, b) => Number(b.total_similarity_score ?? 0) - Number(a.total_similarity_score ?? 0)
  );
  if (similarityAnalyses.length === 0) {
    lines.push("(none)");
    lines.push("");
  } else {
    similarityAnalyses.forEach((analysis, index) => {
      const componentScores = analysis.component_scores ?? {};
      lines.push(`#${index + 1}`);
      lines.push(`candidate_name: ${analysis.candidate_name || "-"}`);
      lines.push(`candidate_type: ${analysis.candidate_type || "unknown"}`);
      lines.push(`total_similarity_score: ${Number(analysis.total_similarity_score ?? 0).toFixed(2)}`);
      lines.push(`band: ${analysis.similarity_band || "low"}`);
      lines.push("component_scores:");
      Object.keys(componentScores)
        .sort()
        .forEach((key) => {
          lines.push(`  ${key}: ${Number(componentScores[key] ?? 0).toFixed(2)}`);
        });
      lines.push(`reasons: ${(analysis.similarity_reasons ?? analysis.reasons ?? []).join(", ") || "-"}`);
      lines.push("evidence:");
      lines.push(`  claim_ids: ${formatStringList(analysis.evidence?.claim_ids)}`);
      lines.push(`  sentence_ids: ${formatStringList(analysis.evidence?.sentence_ids)}`);
      lines.push("");
    });
  }
  lines.push("CLAIMS:");

  visibleClaims.forEach(({ sentence, claim }, index) => {
    const mentionSummary =
      (sentence.mentions ?? []).length > 0
        ? sentence.mentions.map((mention) => `${mention.surface_text}/${mention.mention_type}/${mention.confidence}`).join("; ")
        : "(none)";

    lines.push(`#${index + 1}`);
    lines.push(`sentence: ${truncateText(sentence.text, 300)}`);
    lines.push(`language: ${sentence.language || "n/a"}`);
    lines.push(`mentions: ${truncateText(mentionSummary, 500)}`);
    lines.push("claim:");
    lines.push(`  subject: ${claim.subject_text || "-"}`);
    if (claim.subject_source) {
      lines.push(`  subject_source: ${claim.subject_source}`);
    }
    if (claim.carryover_from_sentence_id) {
      lines.push(`  carryover_from_sentence_id: ${claim.carryover_from_sentence_id}`);
    }
    if ((claim.sanitizers_applied ?? []).length > 0) {
      lines.push(`  sanitizers_applied: ${(claim.sanitizers_applied ?? []).join(", ")}`);
    }
    lines.push(`  predicate: ${claim.predicate || "-"}`);
    lines.push(`  object: ${truncateText(claim.object_text, 180)}`);
    lines.push(`  type: ${claim.claim_type || "-"}`);
    lines.push(`  group: ${claim.claim_group || "-"}`);
    lines.push(`  confidence: ${claim.confidence}`);
    lines.push(`  conflict: ${claim.conflict_behavior || "-"}`);
    lines.push(`  time_mode: ${getClaimTimeMode(claim)}`);
    lines.push(`  time_value: ${claim.space_time_frame?.time_value ?? "-"}`);
    lines.push(`  space_mode: ${getClaimSpaceMode(claim)}`);
    lines.push(`  space_value: ${claim.space_time_frame?.space_value ?? "-"}`);
    lines.push(`  frame_stored: ${hasStoredSpaceTimeFrame(claim) ? "yes" : "no"}`);
    lines.push("compact:");
    lines.push(buildCompactClaim(sentence, claim));
    lines.push("");
  });

  if (claimEntries.length > visibleClaims.length) {
    lines.push(`... truncated: showing first ${visibleClaims.length} of ${claimEntries.length} claims`);
  }

  return lines.join("\n");
}
