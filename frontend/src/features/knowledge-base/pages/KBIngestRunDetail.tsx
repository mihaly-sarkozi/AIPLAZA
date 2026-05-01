import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import api from "../../../api/axiosClient";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useIngestRun, useKbList, useReprocessIngestItemMutation } from "../hooks/useKb";
import {
  ACTIVE_RUN_STATUSES,
  formatModuleProgress,
  getRunProgressLabel,
  getRunProgressPercent,
  getRunProgressSummary,
  formatTimestamp,
  getItemKindLabel,
  getItemProcessingSummary,
  getItemPreview,
  getRunPrimaryItem,
  getStatusBadgeClass,
  getStatusLabel,
} from "./ingestLogHelpers";
import {
  getIngestRunTrace,
  getSentenceInterpretation,
  listIngestItemParagraphs,
  listIngestItemSentences,
  updateSemanticBlockStatus,
  type IngestRunTrace,
  type IngestRunTraceClaim,
} from "../services";

type SentenceRow = {
  id: string;
  source_id: string;
  document_id: string;
  paragraph_id: string;
  order_index: number;
  text_content: string;
  char_start: number;
  char_end: number;
  token_count: number;
  created_at: string;
  metadata: Record<string, unknown>;
};

type ParagraphRow = {
  id: string;
  source_id: string;
  document_id: string;
  block_id?: string | null;
  order_index: number;
  text_content: string;
  char_start: number;
  char_end: number;
  sentence_count: number;
  created_at: string;
  metadata: Record<string, unknown>;
};

type SentenceInterpretationDetail = {
  interpretation: {
    id: string;
    sentence_id: string;
    sentence_text: string;
    claim_summary: string;
    assertion_mode: string;
    claim_type: string;
    time_mode: string;
    time_label?: string | null;
    space_mode: string;
    space_label?: string | null;
    confidence: number;
    information_value_score: number;
    information_value_status: string;
    information_value_reason?: string | null;
    created_at: string;
    updated_at: string;
    metadata: Record<string, unknown>;
  };
  mentions: Array<{
    id: string;
    sentence_id: string;
    mention_type: string;
    text_content: string;
    normalized_value?: string | null;
    char_start: number;
    char_end: number;
    confidence: number;
    created_at: string;
    metadata: Record<string, unknown>;
  }>;
  claims: Array<{
    id: string;
    sentence_id: string;
    subject_text: string;
    predicate_text: string;
    object_text?: string | null;
    claim_type: string;
    assertion_mode: string;
    time_mode: string;
    time_label?: string | null;
    space_mode: string;
    space_label?: string | null;
    confidence: number;
    created_at: string;
    metadata: Record<string, unknown>;
  }>;
};

type StructureDbDetail = {
  title: string;
  description?: string;
  data: Record<string, unknown>;
};

function getBlockTypeLabel(value: unknown) {
  switch (value) {
    case "heading":
      return "Header / title";
    case "paragraph":
      return "Paragraph-like blokk";
    case "list_item":
      return "List item";
    case "table_row":
      return "Table-like blokk";
    case "metadata":
      return "Rövid meta sor";
    case "noise":
      return "Zajos blokk";
    default:
      return typeof value === "string" && value ? value : "Paragraph-like blokk";
  }
}

function getSemanticBlockContextLabel(block: Record<string, unknown>) {
  const subject = String(block.primary_subject || "-");
  const spaceValues = Array.isArray(block.space_values) ? block.space_values : [];
  const timeValues = Array.isArray(block.time_values) ? block.time_values : [];
  const space = String(block.primary_space || spaceValues[0] || "-");
  const time = String(block.primary_time || timeValues[0] || "-");
  return `Alany: ${subject} | Hely: ${space} | Idő: ${time}`;
}

function sourceLabelForBlock(block: Record<string, unknown>, trace: IngestRunTrace | null) {
  return trace?.source_name || String(block.source_name || block.source_title || block.source_id || "Forrás");
}

function claimTextForBlockClaim(claim: IngestRunTraceClaim | undefined, fallbackId: unknown) {
  if (claim?.claim_text) return claim.claim_text;
  const subject = claim?.subject_text || "";
  const predicate = claim?.predicate || "";
  const objectText = claim?.object_text || "";
  const text = [subject, predicate, objectText].filter(Boolean).join(" ");
  return text || String(fallbackId || "Állítás");
}

function getTableRoleLabel(value: unknown) {
  switch (value) {
    case "header":
      return "Táblafejléc";
    case "row":
      return "Adatsor";
    case "unknown":
      return "Ismeretlen táblasor";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

function getMetadataKindLabel(value: unknown) {
  switch (value) {
    case "table_of_contents":
      return "Tartalomjegyzék";
    case "short_meta":
      return "Rövid meta sor";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

function getNoiseKindLabel(value: unknown) {
  switch (value) {
    case "layout_noise":
      return "Layout zaj";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

function getParagraphRoleSummary(paragraph: ParagraphRow) {
  const metadata = paragraph.metadata ?? {};
  const blockType = String(metadata.block_type ?? "");
  if (blockType === "table_row") {
    return getTableRoleLabel(metadata.table_role);
  }
  if (blockType === "metadata") {
    return getMetadataKindLabel(metadata.metadata_kind);
  }
  if (blockType === "noise") {
    return getNoiseKindLabel(metadata.noise_kind);
  }
  if (blockType === "heading") {
    return "Szakasz elválasztó";
  }
  if (blockType === "list_item") {
    return "Lista egység";
  }
  return "Normál blokk";
}

function getParagraphDebugDetails(paragraph: ParagraphRow) {
  const metadata = paragraph.metadata ?? {};
  const details: string[] = [];
  if (typeof metadata.line_count === "number") {
    details.push(`${metadata.line_count} sor`);
  }
  const tableHeaders = Array.isArray(metadata.table_column_headers)
    ? metadata.table_column_headers.map((value) => String(value)).filter(Boolean)
    : [];
  const tableCells = Array.isArray(metadata.table_cells)
    ? metadata.table_cells.map((value) => String(value)).filter(Boolean)
    : [];
  if (tableHeaders.length) {
    details.push(`oszlopok: ${tableHeaders.join(" | ")}`);
  }
  if (tableCells.length) {
    details.push(`cellák: ${tableCells.join(" | ")}`);
  }
  if (typeof metadata.docx_table_row_index === "number") {
    details.push(`docx sor: ${metadata.docx_table_row_index + 1}`);
  }
  if (typeof metadata.docx_table_column_count === "number") {
    details.push(`oszlopszám: ${metadata.docx_table_column_count}`);
  }
  if (typeof metadata.font_size === "number") {
    details.push(`betűméret: ${metadata.font_size}`);
  }
  if (typeof metadata.is_bold === "boolean") {
    details.push(metadata.is_bold ? "félkövér" : "nem félkövér");
  }
  return details.length ? details.join(" | ") : "n/a";
}

function getSplitReasonLabel(value: unknown) {
  switch (value) {
    case "strong_punctuation":
      return "Erős mondatzárás";
    case "medium_punctuation:semicolon":
      return "Pontosvessző";
    case "medium_punctuation:colon":
      return "Kettőspont";
    case "newline_candidate":
      return "Sortörés jelölt";
    case "long_segment_fallback":
      return "Hosszú szegmens fallback";
    case "heading_block":
      return "Heading blokk";
    case "list_item_block":
      return "Listaelem blokk";
    case "list_item_line":
      return "Lista sor";
    case "table_row_block":
      return "Táblasor blokk";
    case "structure_block":
      return "Szerkezeti blokk";
    case "tail":
      return "Maradék szegmens";
    case "fallback_single":
      return "Egyben hagyott blokk";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

function formatSplitConfidence(value: unknown) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "n/a";
}

function formatStringList(value: unknown) {
  if (Array.isArray(value)) {
    const items = value.map((item) => String(item)).filter(Boolean);
    return items.length ? items.join(", ") : "n/a";
  }
  return typeof value === "string" && value ? value : "n/a";
}

function getSplitStrengthLabel(value: unknown) {
  switch (value) {
    case "claim_refined":
      return "Claim-finomított";
    case "strong":
      return "Erős";
    case "weak":
      return "Gyenge";
    default:
      return typeof value === "string" && value ? value : "n/a";
  }
}

function getSentenceSplitSummary(metadata: Record<string, unknown> | undefined) {
  const meta = metadata ?? {};
  const parts: string[] = [];
  if (meta.split_reason) {
    parts.push(getSplitReasonLabel(meta.split_reason));
  }
  if (meta.refined_from_reason) {
    parts.push(`alap: ${getSplitReasonLabel(meta.refined_from_reason)}`);
  }
  if (meta.split_strength) {
    parts.push(`erő: ${getSplitStrengthLabel(meta.split_strength)}`);
  }
  if (typeof meta.uncertain_split === "boolean") {
    parts.push(meta.uncertain_split ? "bizonytalan" : "stabil");
  }
  return parts.length ? parts.join(" | ") : "n/a";
}

function getSentenceRefinementSummary(metadata: Record<string, unknown> | undefined) {
  const meta = metadata ?? {};
  const parts: string[] = [];
  if (meta.claim_split_reasons) {
    parts.push(`claim okok: ${formatStringList(meta.claim_split_reasons)}`);
  }
  if (meta.subject_hint) {
    parts.push(`S: ${String(meta.subject_hint)}`);
  }
  if (meta.predicate_hint) {
    parts.push(`P: ${String(meta.predicate_hint)}`);
  }
  if (meta.object_hint) {
    parts.push(`O: ${String(meta.object_hint)}`);
  }
  return parts.length ? parts.join(" | ") : "n/a";
}

function getMentionTypeLabel(value: string) {
  const labels: Record<string, string> = {
    person: "Személy",
    organization: "Cég/szervezet",
    system: "Rendszer",
    place: "Hely",
    address: "Cím",
    email: "Email cím",
    phone_number: "Telefonszám",
    birth_date: "Születési dátum",
    tax_id: "Adószám",
    spanish_nif: "Spanyol NIF",
    spanish_nie: "Spanyol NIE",
    spanish_cif: "Spanyol CIF",
    eu_vat_number: "EU VAT / közösségi adószám",
    iban: "IBAN",
    bic_swift: "BIC / SWIFT",
    italian_codice_fiscale: "Olasz codice fiscale",
    french_siren: "Francia SIREN",
    french_siret: "Francia SIRET",
    polish_pesel: "Lengyel PESEL",
    romanian_cnp: "Román CNP",
    portuguese_nif: "Portugál NIF",
    license_plate: "Rendszám",
    vin: "Alvázszám",
    traffic_permit_number: "Forgalmi engedélyszám",
    driver_license_number: "Jogosítvány szám",
    social_security_number: "TB azonosító",
    company_registration_number: "Cégjegyzékszám",
    mixed_identifier: "Vegyes azonosító/kód",
    generic_identifier: "Általános azonosító",
    function: "Funkció",
    rule: "Szabály",
    role: "Szerepkör",
    document_reference: "Dokumentumhivatkozás",
    coreference: "Visszautalás",
  };
  return labels[value] ?? value;
}

function getInformationValueStatusLabel(value: string) {
  const labels: Record<string, string> = {
    context_strong: "Erős kontextus",
    merge_with_previous: "Előzőhöz csatolandó",
    discard_candidate: "Eldobható jelölt",
    weak: "Gyenge",
    usable: "Használható",
    strong: "Erős",
    unrated: "Nincs értékelve",
  };
  return labels[value] ?? value;
}

function getAssertionModeLabel(value: string) {
  const labels: Record<string, string> = {
    context_header: "Fejléc / kontextus",
  };
  return labels[value] ?? value;
}

function getClaimTypeLabel(value: string) {
  const labels: Record<string, string> = {
    context_header: "Fejléc-kapcsolat",
  };
  return labels[value] ?? value;
}

function getInformationValueBadgeClass(value: string) {
  switch (value) {
    case "strong":
      return "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
    case "usable":
      return "bg-blue-500/10 text-blue-700 dark:text-blue-300";
    case "weak":
      return "bg-amber-500/10 text-amber-700 dark:text-amber-300";
    case "merge_with_previous":
    case "discard_candidate":
      return "bg-rose-500/10 text-rose-700 dark:text-rose-300";
    default:
      return "bg-slate-500/10 text-slate-700 dark:text-slate-300";
  }
}

function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] p-4">
      <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{label}</div>
      <div className="mt-2 text-sm text-[var(--color-foreground)]">{value}</div>
    </div>
  );
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--color-card-muted)]">
      <div className="h-full rounded-full bg-[var(--color-primary)] transition-all" style={{ width: `${value}%` }} />
    </div>
  );
}

export default function KBIngestRunDetail() {
  const { uuid, runId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const selectedItemId = searchParams.get("item");
  const { data: kbList = [], isLoading: kbLoading } = useKbList();
  const kb = useMemo(() => kbList.find((item) => item.uuid === uuid), [kbList, uuid]);
  const [isOpeningSource, setIsOpeningSource] = useState(false);
  const [showSentencesModal, setShowSentencesModal] = useState(false);
  const [isLoadingSentences, setIsLoadingSentences] = useState(false);
  const [sentenceRows, setSentenceRows] = useState<SentenceRow[]>([]);
  const [showSentenceInterpretationModal, setShowSentenceInterpretationModal] = useState(false);
  const [isLoadingSentenceInterpretation, setIsLoadingSentenceInterpretation] = useState(false);
  const [selectedSentenceInterpretation, setSelectedSentenceInterpretation] = useState<SentenceInterpretationDetail | null>(null);
  const [showBlockUnitsModal, setShowBlockUnitsModal] = useState(false);
  const [showStructureModal, setShowStructureModal] = useState(false);
  const [isLoadingStructure, setIsLoadingStructure] = useState(false);
  const [paragraphRows, setParagraphRows] = useState<ParagraphRow[]>([]);
  const [selectedStructureParagraphId, setSelectedStructureParagraphId] = useState<string | null>(null);
  const [showStructureSentencesModal, setShowStructureSentencesModal] = useState(false);
  const [structureSentenceRows, setStructureSentenceRows] = useState<SentenceRow[]>([]);
  const [isLoadingStructureSentences, setIsLoadingStructureSentences] = useState(false);
  const [traceDetail, setTraceDetail] = useState<IngestRunTrace | null>(null);
  const [isLoadingTrace, setIsLoadingTrace] = useState(false);
  const [updatingBlockId, setUpdatingBlockId] = useState<string | null>(null);
  const [structureDbDetail, setStructureDbDetail] = useState<StructureDbDetail | null>(null);
  const reprocessMutation = useReprocessIngestItemMutation({
    onSuccess: () => {
      setSentenceRows([]);
      setParagraphRows([]);
      setStructureSentenceRows([]);
      setSelectedStructureParagraphId(null);
      toast.success("Az újrafeldolgozás elindult. A státusz automatikusan frissül.");
      void runQuery.refetch();
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error) ?? "Az újrafeldolgozás indítása sikertelen.");
    },
  });

  const runQuery = useIngestRun(runId, {
    refetchInterval: ({ state }) => (ACTIVE_RUN_STATUSES.has(state.data?.status ?? "") ? 1500 : 4000),
  });

  useEffect(() => {
    if (kbLoading) return;
    if (!uuid || !kb) {
      navigate("/kb", { replace: true });
    }
  }, [kb, kbLoading, navigate, uuid]);

  useEffect(() => {
    if (!runId) {
      setTraceDetail(null);
      return;
    }
    let cancelled = false;
    const loadTrace = async () => {
      setIsLoadingTrace(true);
      try {
        const trace = await getIngestRunTrace(runId);
        if (!cancelled) {
          setTraceDetail(trace);
        }
      } catch {
        if (!cancelled) {
          setTraceDetail(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingTrace(false);
        }
      }
    };
    void loadTrace();
    return () => {
      cancelled = true;
    };
  }, [runId, runQuery.data?.updated_at]);

  const error = runQuery.error ? getApiErrorMessage(runQuery.error) : null;
  const run = runQuery.data;
  const selectedItem = run ? getRunPrimaryItem(run, selectedItemId) : null;
  const processingSummary = useMemo(() => getItemProcessingSummary(selectedItem), [selectedItem]);
  const parserModule = processingSummary.modules.parser;
  const interpretationModule = processingSummary.modules.sentence_interpretation;
  const evaluationModule = processingSummary.modules.sentence_evaluation;
  const documentProgress = processingSummary.document_progress;
  const runProgressSummary = useMemo(() => getRunProgressSummary(run), [run]);
  const runProgressPercent = useMemo(() => getRunProgressPercent(run), [run]);
  const runProgressLabel = useMemo(() => getRunProgressLabel(run), [run]);
  const parserErrorMessage =
    (typeof parserModule?.error_message === "string" && parserModule.error_message.trim()) ||
    (typeof selectedItem?.error_message === "string" && selectedItem.error_message.trim()) ||
    (typeof runProgressSummary.last_error_message === "string" && runProgressSummary.last_error_message.trim()) ||
    "";
  const getStructureParagraphSentences = (paragraphId: string) =>
    structureSentenceRows
      .filter((sentence) => sentence.paragraph_id === paragraphId)
      .sort((a, b) => a.order_index - b.order_index);
  const traceClaimLookup = useMemo(() => {
    const lookup = new Map<string, IngestRunTraceClaim>();
    for (const sentence of traceDetail?.sentences ?? []) {
      for (const claim of sentence.claims ?? []) {
        if (claim.claim_id) lookup.set(String(claim.claim_id), claim);
      }
    }
    return lookup;
  }, [traceDetail]);
  const traceSentenceLookup = useMemo(() => {
    const lookup = new Map<string, NonNullable<IngestRunTrace["sentences"]>[number]>();
    for (const sentence of traceDetail?.sentences ?? []) {
      if (sentence.sentence_id) lookup.set(String(sentence.sentence_id), sentence);
    }
    return lookup;
  }, [traceDetail]);

  const setBlockStatus = async (
    blockId: string | undefined,
    status: "draft" | "approved" | "rejected" | "withdrawn" | "outdated" | "disputed"
  ) => {
    if (!uuid || !blockId) return;
    setUpdatingBlockId(blockId);
    try {
      const result = await updateSemanticBlockStatus(uuid, blockId, status);
      setTraceDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          semantic_blocks: (prev.semantic_blocks ?? []).map((block) =>
            String(block.id ?? "") === blockId ? { ...block, ...result.block } : block
          ),
        };
      });
      toast.success(`A blokk státusza frissült: ${status}`);
    } catch (error) {
      toast.error(getApiErrorMessage(error) ?? "A blokk státusz frissítése sikertelen.");
    } finally {
      setUpdatingBlockId(null);
    }
  };

  const openSentences = async () => {
    if (!selectedItem || isLoadingSentences) return;
    setIsLoadingSentences(true);
    try {
      const response = await listIngestItemSentences(selectedItem.id);
      setSentenceRows(response ?? []);
      setShowSentencesModal(true);
    } catch (loadError) {
      toast.error(getApiErrorMessage(loadError) ?? "A mondatok betöltése sikertelen.");
    } finally {
      setIsLoadingSentences(false);
    }
  };

  const openStructure = async () => {
    if (!selectedItem || isLoadingStructure) return;
    setIsLoadingStructure(true);
    try {
      const response = await listIngestItemParagraphs(selectedItem.id);
      setParagraphRows(response ?? []);
      setSelectedStructureParagraphId(null);
      setShowStructureSentencesModal(false);
      setShowStructureModal(true);
    } catch (loadError) {
      toast.error(getApiErrorMessage(loadError) ?? "A parser blokkstruktúra betöltése sikertelen.");
    } finally {
      setIsLoadingStructure(false);
    }
  };

  const openSentenceInterpretation = async (sentenceId: string) => {
    if (!sentenceId || isLoadingSentenceInterpretation) return;
    setIsLoadingSentenceInterpretation(true);
    try {
      const detail = await getSentenceInterpretation(sentenceId);
      setSelectedSentenceInterpretation(detail);
      setShowSentenceInterpretationModal(true);
    } catch (loadError) {
      toast.error(getApiErrorMessage(loadError) ?? "A mondat értelmezése nem tölthető be.");
    } finally {
      setIsLoadingSentenceInterpretation(false);
    }
  };

  const toggleStructureParagraph = async (paragraphId: string) => {
    if (!selectedItem) return;
    setSelectedStructureParagraphId(paragraphId);
    setShowStructureSentencesModal(true);
    setIsLoadingStructureSentences(true);
    try {
      const response = await listIngestItemSentences(selectedItem.id);
      setStructureSentenceRows(response ?? []);
    } catch (loadError) {
      toast.error(getApiErrorMessage(loadError) ?? "A blokkhoz tartozó mondatok betöltése sikertelen.");
    } finally {
      setIsLoadingStructureSentences(false);
    }
  };

  const selectedStructureParagraph = useMemo(
    () => paragraphRows.find((paragraph) => paragraph.id === selectedStructureParagraphId) ?? null,
    [paragraphRows, selectedStructureParagraphId]
  );

  const openSource = async () => {
    if (!selectedItem || isOpeningSource) return;
    if (selectedItem.input_type === "url") {
      const url = typeof selectedItem.metadata?.url === "string" ? selectedItem.metadata.url : selectedItem.origin;
      if (!url) {
        toast.error("Ehhez a hivatkozáshoz nincs megnyitható URL.");
        return;
      }
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }

    setIsOpeningSource(true);
    try {
      const response = await api.get<ArrayBuffer>(`/knowledge/ingest/items/${selectedItem.id}/raw`, {
        responseType: "arraybuffer",
      });
      const contentType =
        response.headers["content-type"] ||
        (selectedItem.input_type === "text" ? "text/plain; charset=utf-8" : "application/octet-stream");
      const blob = new Blob([response.data], { type: contentType });
      const blobUrl = URL.createObjectURL(blob);
      window.open(blobUrl, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    } catch (openError) {
      toast.error(getApiErrorMessage(openError) ?? "A forrás megnyitása sikertelen.");
    } finally {
      setIsOpeningSource(false);
    }
  };

  const openLabel =
    selectedItem?.input_type === "file"
      ? "Fájl megnyitása"
      : selectedItem?.input_type === "url"
        ? "Hivatkozás megnyitása"
        : "Szöveg megnyitása";

  return (
    <div className="app-page">
      <div className="app-page-container">
        <PageHeader
          eyebrow="Tanítás részletei"
          title={selectedItem ? selectedItem.title : "Tanítás részletei"}
          description="Ez az oldal most csak a fő adatokat mutatja. A későbbi értelmezés és feldolgozás ezen a nézeten jelenik majd meg."
          actions={
            <div className="flex gap-2">
              {selectedItem ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    if (!uuid || !selectedItem) return;
                    reprocessMutation.mutate({ itemId: selectedItem.id, kbUuid: uuid });
                  }}
                  disabled={reprocessMutation.isPending}
                >
                  {reprocessMutation.isPending ? "Újrafeldolgozás..." : "Újrafeldolgozás"}
                </Button>
              ) : null}
              {selectedItem ? (
                <Button variant="primary" onClick={openSource} disabled={isOpeningSource}>
                  {isOpeningSource ? "Megnyitás..." : openLabel}
                </Button>
              ) : null}
              {selectedItem ? (
                <Button variant="secondary" onClick={openStructure} disabled={isLoadingStructure}>
                  {isLoadingStructure ? "Betöltés..." : "Szerkezet"}
                </Button>
              ) : null}
              {selectedItem ? (
                <Button variant="secondary" onClick={() => setShowBlockUnitsModal(true)} disabled={isLoadingTrace}>
                  {isLoadingTrace ? "Betöltés..." : "Mondat egységek / blokkok"}
                </Button>
              ) : null}
              {selectedItem ? (
                <Button variant="secondary" onClick={openSentences} disabled={isLoadingSentences}>
                  {isLoadingSentences ? "Betöltés..." : "Mondatok"}
                </Button>
              ) : null}
              <Button variant="secondary" onClick={() => navigate(`/kb/ingest/${uuid}`)}>
                Vissza a naplóhoz
              </Button>
              <Button variant="ghost" onClick={() => runQuery.refetch()}>
                Frissítés
              </Button>
            </div>
          }
        />

        {error ? <Alert tone="error">{error}</Alert> : null}

        {run ? (
          <section className="space-y-6">
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
                <div className="mt-2 text-lg font-semibold">{formatTimestamp(selectedItem?.created_at ?? run.created_at)}</div>
              </div>
              <div className="app-surface p-4">
                <div className="text-sm text-[var(--color-muted)]">Tanítás típusa</div>
                <div className="mt-2 text-lg font-semibold">{getItemKindLabel(selectedItem)}</div>
              </div>
              <div className="app-surface p-4">
                <div className="text-sm text-[var(--color-muted)]">Batch méret</div>
                <div className="mt-2 text-lg font-semibold">{run.batch_size}</div>
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
                <DetailField
                  label="Progress"
                  value={selectedItem?.progress_message || "Még nincs részletes progress üzenet."}
                />
                <DetailField
                  label="Parser futás"
                  value={String(selectedItem?.metadata?.parser_run_id ?? "Még nincs parser run azonosító.")}
                />
                <DetailField
                  label="Dokumentum"
                  value={String(selectedItem?.metadata?.document_id ?? "Még nincs dokumentum azonosító.")}
                />
                <DetailField
                  label="Mondatszám"
                  value={String(selectedItem?.metadata?.sentence_count ?? "0")}
                />
                <DetailField label="Megnevezés" value={selectedItem?.display_name || selectedItem?.title || run.id} />
                <DetailField label="Tartalom / forrás" value={selectedItem ? getItemPreview(selectedItem) : "n/a"} />
                <DetailField label="Origin" value={selectedItem?.origin || "n/a"} />
                <DetailField label="Létrehozva" value={formatTimestamp(run.created_at)} />
                <DetailField label="Frissítve" value={formatTimestamp(selectedItem?.updated_at ?? run.updated_at)} />
                <DetailField label="Hiba" value={parserErrorMessage || "Nincs"} />
              </div>
            </div>

            <div className="app-surface p-5">
              <h2 className="text-xl font-semibold">Részmodul állapot</h2>
              <div className="mt-4 grid gap-4 md:grid-cols-3">
                <DetailField
                  label="Parser"
                  value={formatModuleProgress(parserModule)}
                />
                <DetailField
                  label="Mondatértelmezés"
                  value={formatModuleProgress(interpretationModule)}
                />
                <DetailField
                  label="Mondatértékelés"
                  value={formatModuleProgress(evaluationModule)}
                />
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
                  <div className="text-sm font-medium text-[var(--color-foreground)]">
                    {documentProgress?.progress_percent ?? 0}%
                  </div>
                </div>
                <ProgressBar value={documentProgress?.progress_percent ?? 0} />
                <div className="mt-3 text-sm text-[var(--color-muted)]">
                  Fázis: {documentProgress?.phase || processingSummary.overall_status || "queued"}
                  {documentProgress &&
                  typeof documentProgress.processed_parts === "number" &&
                  typeof documentProgress.total_parts === "number"
                    ? ` | ${documentProgress.processed_parts} / ${documentProgress.total_parts}`
                    : ""}
                </div>
              </div>
            </div>

            {run.items.length > 1 ? (
              <div className="app-surface p-5">
                <h2 className="text-xl font-semibold">Run tételek</h2>
                <div className="mt-4 space-y-3">
                  {run.items.map((item) => {
                    const detailUrl = `/kb/ingest/${uuid}/runs/${run.id}?item=${encodeURIComponent(item.id)}`;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => navigate(detailUrl)}
                        className={`w-full rounded-lg border p-4 text-left transition-colors ${
                          selectedItem?.id === item.id
                            ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5"
                            : "border-[var(--color-border)] hover:bg-[var(--color-primary)]/5"
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-medium">{item.display_name || item.title}</div>
                          <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${getStatusBadgeClass(item.status)}`}>
                            {getStatusLabel(item.status)}
                          </span>
                        </div>
                        <div className="mt-2 text-sm text-[var(--color-muted)]">{getItemPreview(item)}</div>
                        <div className="mt-2 text-xs text-[var(--color-muted)]">{formatModuleProgress(getItemProcessingSummary(item).modules.sentence_interpretation)}</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </section>
        ) : (
          <div className="app-surface p-5 text-sm text-[var(--color-muted)]">A tanítás részletei betöltés alatt állnak.</div>
        )}
      </div>
      <Modal open={showStructureModal} onClose={() => setShowStructureModal(false)} panelClassName="max-w-6xl">
        <ModalHeader
          title="Parser blokkstruktúra"
          description="A parser által felismert bekezdések és blokk-típusok az aktuális tanítási rekordhoz."
        />
        <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
          <table className="min-w-full text-sm">
            <thead className="bg-[var(--color-card-muted)]">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Blokk típus</th>
                <th className="px-3 py-2 text-left">Szerep / jelleg</th>
                <th className="px-3 py-2 text-left">Oldal</th>
                <th className="px-3 py-2 text-left">Mondat</th>
                <th className="px-3 py-2 text-left">Karaktertartomány</th>
                <th className="px-3 py-2 text-left">Teszt meta</th>
                <th className="px-3 py-2 text-left">Tartalom</th>
              </tr>
            </thead>
            <tbody>
              {paragraphRows.length ? (
                paragraphRows.map((paragraph) => {
                  const isSelected = selectedStructureParagraphId === paragraph.id;
                  return (
                    <tr
                      key={paragraph.id}
                      className={`border-t border-[var(--color-border)] align-top cursor-pointer hover:bg-[var(--color-primary)]/5 ${
                        isSelected ? "bg-[var(--color-primary)]/5" : ""
                      }`}
                      onClick={() => void toggleStructureParagraph(paragraph.id)}
                    >
                      <td className="px-3 py-2">{paragraph.order_index}</td>
                      <td className="px-3 py-2">{getBlockTypeLabel(paragraph.metadata?.block_type)}</td>
                      <td className="px-3 py-2">{getParagraphRoleSummary(paragraph)}</td>
                      <td className="px-3 py-2">{String(paragraph.metadata?.page_number ?? "-")}</td>
                      <td className="px-3 py-2">{paragraph.sentence_count}</td>
                      <td className="px-3 py-2">
                        {paragraph.char_start}-{paragraph.char_end}
                      </td>
                      <td className="px-3 py-2 text-xs text-[var(--color-muted)] whitespace-pre-wrap">
                        {getParagraphDebugDetails(paragraph)}
                      </td>
                      <td className="px-3 py-2 whitespace-pre-wrap">{paragraph.text_content}</td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td className="px-3 py-4 text-[var(--color-muted)]" colSpan={8}>
                    Ehhez a rekordhoz még nincs megjeleníthető blokkstruktúra.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <ModalFooter>
          <Button variant="secondary" onClick={() => setShowStructureModal(false)}>
            Bezárás
          </Button>
        </ModalFooter>
      </Modal>
      <Modal open={showBlockUnitsModal} onClose={() => setShowBlockUnitsModal(false)} panelClassName="max-w-6xl">
        <ModalHeader
          title="Mondat egységek / blokkok"
          description="A tanításból képzett alany-hely-idő tudásblokkok, olvasható forrással és állításokkal."
        />
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
          <div className="font-semibold">Tanított tudásblokkok</div>
          <div className="mt-1 text-xs text-[var(--color-muted)]">
            Ezek azok a block-first egységek, amelyekhez állítások, mondatok és források tartoznak.
          </div>
          <div className="mt-3 grid gap-3">
            {(traceDetail?.semantic_blocks ?? []).length ? (
              (traceDetail?.semantic_blocks ?? []).map((block, index) => {
                const claimIds = Array.isArray(block.claim_ids) ? block.claim_ids : [];
                const sentenceIds = Array.isArray(block.sentence_ids) ? block.sentence_ids : [];
                return (
                  <div key={String(block.id ?? index)} className="rounded border border-[var(--color-border)] bg-[var(--color-background)] p-3 text-xs">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="font-medium">{String(block.summary || block.primary_subject || `Tudásblokk ${index + 1}`)}</div>
                        <div className="mt-1 text-[var(--color-muted)]">{getSemanticBlockContextLabel(block)}</div>
                      </div>
                      <div className="font-mono text-[var(--color-muted)]">
                        #{String(block.order_start ?? "-")}-{String(block.order_end ?? "-")}
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
                      <span className="rounded bg-[var(--color-card-muted)] px-2 py-1">Mondatok: {sentenceIds.length}</span>
                      <span className="rounded bg-[var(--color-card-muted)] px-2 py-1">Státusz: {String(block.block_status ?? "draft")}</span>
                      <span className="rounded bg-[var(--color-card-muted)] px-2 py-1">
                        Retrieval súly: {Number(block.retrieval_weight ?? 1).toFixed(2)}
                      </span>
                      {Number(block.conflict_count ?? 0) > 0 ? (
                        <span className="rounded bg-red-500/10 px-2 py-1 text-red-700">
                          Konfliktus: {Number(block.conflict_count ?? 0)}
                        </span>
                      ) : null}
                      <button
                        type="button"
                        disabled={updatingBlockId === String(block.id ?? "")}
                        className="rounded bg-emerald-500/10 px-2 py-1 text-emerald-700 hover:bg-emerald-500/20 disabled:opacity-50"
                        onClick={() => void setBlockStatus(String(block.id ?? ""), "approved")}
                      >
                        Jóváhagyás
                      </button>
                      <button
                        type="button"
                        disabled={updatingBlockId === String(block.id ?? "")}
                        className="rounded bg-amber-500/10 px-2 py-1 text-amber-700 hover:bg-amber-500/20 disabled:opacity-50"
                        onClick={() => void setBlockStatus(String(block.id ?? ""), "outdated")}
                      >
                        Elavult
                      </button>
                      <button
                        type="button"
                        disabled={updatingBlockId === String(block.id ?? "")}
                        className="rounded bg-red-500/10 px-2 py-1 text-red-700 hover:bg-red-500/20 disabled:opacity-50"
                        onClick={() => void setBlockStatus(String(block.id ?? ""), "withdrawn")}
                      >
                        Visszavonás
                      </button>
                      <button
                        type="button"
                        className="rounded bg-[var(--color-card-muted)] px-2 py-1 underline hover:text-[var(--color-primary)]"
                        onClick={() =>
                          setStructureDbDetail({
                            title: "Forrás részletei",
                            description: sourceLabelForBlock(block, traceDetail),
                            data: {
                              source_name: traceDetail?.source_name ?? null,
                              source_id: traceDetail?.source_id ?? block.source_id ?? null,
                              document_id: block.document_id ?? null,
                              block_id: block.id ?? null,
                              paragraph_ids: block.paragraph_ids ?? [],
                              sentences: sentenceIds.map((sentenceId) => traceSentenceLookup.get(String(sentenceId)) ?? { sentence_id: sentenceId }),
                              block,
                            },
                          })
                        }
                      >
                        Forrás: {sourceLabelForBlock(block, traceDetail)}
                      </button>
                    </div>
                    <div className="mt-2 space-y-1">
                      <div className="font-medium">Állítások</div>
                      {claimIds.length ? (
                        claimIds.map((claimId) => {
                          const claim = traceClaimLookup.get(String(claimId));
                          return (
                            <button
                              key={String(claimId)}
                              type="button"
                              className="block w-full rounded border border-[var(--color-border)] bg-[var(--color-surface)] p-2 text-left text-[11px] hover:border-[var(--color-primary)]"
                              onClick={() =>
                                setStructureDbDetail({
                                  title: "Állítás részletei",
                                  description: claimTextForBlockClaim(claim, claimId),
                                  data: {
                                    block_id: block.id ?? null,
                                    source_name: traceDetail?.source_name ?? null,
                                    source_id: traceDetail?.source_id ?? block.source_id ?? null,
                                    claim_id: claimId,
                                    claim: claim ?? null,
                                    source_sentence: claim?.claim_id ? traceDetail?.sentences.find((sentence) => sentence.claims.some((item) => item.claim_id === claim.claim_id)) ?? null : null,
                                  },
                                })
                              }
                            >
                              {claimTextForBlockClaim(claim, claimId)}
                            </button>
                          );
                        })
                      ) : (
                        <div className="text-[var(--color-muted)]">Nincs külön állítás ehhez a blokkhoz.</div>
                      )}
                    </div>
                    <div className="mt-2 whitespace-pre-wrap text-[11px]">{String(block.text || "")}</div>
                  </div>
                );
              })
            ) : (
              <div className="text-sm text-[var(--color-muted)]">Ehhez a tanításhoz még nincs semantic block adat.</div>
            )}
          </div>
        </div>
        <ModalFooter>
          <Button variant="secondary" onClick={() => setShowBlockUnitsModal(false)}>
            Bezárás
          </Button>
        </ModalFooter>
      </Modal>
      <Modal open={Boolean(structureDbDetail)} onClose={() => setStructureDbDetail(null)} panelClassName="max-w-4xl">
        <ModalHeader
          title={structureDbDetail?.title ?? "Részletek"}
          description={structureDbDetail?.description ?? "A kiválasztott rekord teljes trace / DB részletei."}
        />
        <pre className="max-h-[65vh] overflow-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] p-4 text-xs">
          {JSON.stringify(structureDbDetail?.data ?? {}, null, 2)}
        </pre>
        <ModalFooter>
          <Button variant="secondary" onClick={() => setStructureDbDetail(null)}>
            Bezárás
          </Button>
        </ModalFooter>
      </Modal>
      <Modal
        open={showStructureSentencesModal}
        onClose={() => setShowStructureSentencesModal(false)}
        panelClassName="max-w-5xl"
      >
        <ModalHeader
          title="A blokkból képzett mondatok"
          description="A kiválasztott szerkezeti sorból keletkező mondatok, a vágás okával és biztonságával együtt."
        />
        {selectedStructureParagraph ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-[var(--color-border)] p-4">
              <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Kiválasztott szerkezeti sor</div>
              <div className="mt-2 text-sm text-[var(--color-foreground)] whitespace-pre-wrap">
                {selectedStructureParagraph.text_content}
              </div>
              <div className="mt-2 text-xs text-[var(--color-muted)]">
                {getBlockTypeLabel(selectedStructureParagraph.metadata?.block_type)} | {getParagraphRoleSummary(selectedStructureParagraph)} |{" "}
                {selectedStructureParagraph.char_start}-{selectedStructureParagraph.char_end}
              </div>
            </div>
            {isLoadingStructureSentences ? (
              <div className="text-sm text-[var(--color-muted)]">Mondatok betöltése...</div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
                <table className="min-w-full text-sm">
                  <thead className="bg-[var(--color-card-muted)]">
                    <tr>
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-left">Mondat</th>
                      <th className="px-3 py-2 text-left">Vágás</th>
                      <th className="px-3 py-2 text-left">Finomítás</th>
                      <th className="px-3 py-2 text-left">Biztonság</th>
                      <th className="px-3 py-2 text-left">Karaktertartomány</th>
                    </tr>
                  </thead>
                  <tbody>
                    {getStructureParagraphSentences(selectedStructureParagraph.id).length ? (
                      getStructureParagraphSentences(selectedStructureParagraph.id).map((sentence) => (
                        <tr
                          key={sentence.id}
                          className="border-t border-[var(--color-border)] align-top hover:bg-[var(--color-primary)]/5 cursor-pointer"
                          onClick={() => void openSentenceInterpretation(sentence.id)}
                        >
                          <td className="px-3 py-2">{sentence.order_index}</td>
                          <td className="px-3 py-2 whitespace-pre-wrap">{sentence.text_content}</td>
                          <td className="px-3 py-2 text-xs whitespace-pre-wrap">{getSentenceSplitSummary(sentence.metadata)}</td>
                          <td className="px-3 py-2 text-xs whitespace-pre-wrap">{getSentenceRefinementSummary(sentence.metadata)}</td>
                          <td className="px-3 py-2">{formatSplitConfidence(sentence.metadata?.split_confidence)}</td>
                          <td className="px-3 py-2">
                            {sentence.char_start}-{sentence.char_end}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td className="px-3 py-4 text-[var(--color-muted)]" colSpan={6}>
                          Ehhez a szerkezeti sorhoz nincs külön megjeleníthető mondatlista.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-[var(--color-muted)]">Nincs kiválasztott szerkezeti sor.</div>
        )}
        <ModalFooter>
          <Button variant="secondary" onClick={() => setShowStructureSentencesModal(false)}>
            Bezárás
          </Button>
        </ModalFooter>
      </Modal>
      <Modal open={showSentencesModal} onClose={() => setShowSentencesModal(false)} panelClassName="max-w-5xl">
        <ModalHeader
          title="Mondatokra bontott rekordok"
          description="Az aktuális tanítási rekordhoz tartozó mondatok listája."
        />
        <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
          <table className="min-w-full text-sm">
            <thead className="bg-[var(--color-card-muted)]">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Mondat</th>
                <th className="px-3 py-2 text-left">Vágás</th>
                <th className="px-3 py-2 text-left">Finomítás</th>
                <th className="px-3 py-2 text-left">Erősség</th>
                <th className="px-3 py-2 text-left">Bekezdés</th>
                <th className="px-3 py-2 text-left">Karaktertartomány</th>
                <th className="px-3 py-2 text-left">Token</th>
              </tr>
            </thead>
            <tbody>
              {sentenceRows.length ? (
                sentenceRows.map((sentence) => (
                  <tr
                    key={sentence.id}
                    className="border-t border-[var(--color-border)] align-top hover:bg-[var(--color-primary)]/5 cursor-pointer"
                    onClick={() => openSentenceInterpretation(sentence.id)}
                  >
                    <td className="px-3 py-2">{sentence.order_index}</td>
                    <td className="px-3 py-2 whitespace-pre-wrap">{sentence.text_content}</td>
                    <td className="px-3 py-2 text-xs whitespace-pre-wrap">{getSentenceSplitSummary(sentence.metadata)}</td>
                    <td className="px-3 py-2 text-xs whitespace-pre-wrap">{getSentenceRefinementSummary(sentence.metadata)}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-col gap-1">
                        <span
                          className={`inline-flex w-fit rounded-full px-2.5 py-1 text-xs font-medium ${getInformationValueBadgeClass(String(sentence.metadata?.information_value_status ?? "unrated"))}`}
                        >
                          {getInformationValueStatusLabel(String(sentence.metadata?.information_value_status ?? "unrated"))}
                        </span>
                        <span className="text-xs text-[var(--color-muted)]">
                          {typeof sentence.metadata?.information_value_score === "number"
                            ? `${sentence.metadata.information_value_score}/10`
                            : "n/a"}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2">{String(sentence.metadata?.paragraph_order ?? sentence.paragraph_id)}</td>
                    <td className="px-3 py-2">
                      {sentence.char_start}-{sentence.char_end}
                    </td>
                    <td className="px-3 py-2">{sentence.token_count}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-3 py-4 text-[var(--color-muted)]" colSpan={8}>
                    Ehhez a rekordhoz még nincs megjeleníthető mondat.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <ModalFooter>
          {isLoadingSentenceInterpretation ? <div className="mr-auto text-sm text-[var(--color-muted)]">Részletek betöltése...</div> : null}
          <Button variant="secondary" onClick={() => setShowSentencesModal(false)}>
            Bezárás
          </Button>
        </ModalFooter>
      </Modal>
      <Modal
        open={showSentenceInterpretationModal}
        onClose={() => setShowSentenceInterpretationModal(false)}
        panelClassName="max-w-6xl"
      >
        <ModalHeader
          title="Mondatértelmezés"
          description="A kiválasztott mondat strukturált szemantikai értelmezése."
        />
        {selectedSentenceInterpretation ? (
          <div className="space-y-5">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <DetailField label="Állítás összefoglaló" value={selectedSentenceInterpretation.interpretation.claim_summary || "n/a"} />
              <DetailField
                label="Állítás természete"
                value={getAssertionModeLabel(selectedSentenceInterpretation.interpretation.assertion_mode)}
              />
              <DetailField label="Claim típus" value={getClaimTypeLabel(selectedSentenceInterpretation.interpretation.claim_type)} />
              <DetailField
                label="Tér-idő keret"
                value={`${selectedSentenceInterpretation.interpretation.time_mode}${selectedSentenceInterpretation.interpretation.time_label ? ` / ${selectedSentenceInterpretation.interpretation.time_label}` : ""}${selectedSentenceInterpretation.interpretation.space_label ? ` / ${selectedSentenceInterpretation.interpretation.space_label}` : ""}`}
              />
              <DetailField
                label="Információérték"
                value={`${selectedSentenceInterpretation.interpretation.information_value_score}/10`}
              />
              <DetailField
                label="Információérték státusz"
                value={getInformationValueStatusLabel(selectedSentenceInterpretation.interpretation.information_value_status)}
              />
              <DetailField
                label="Információérték indok"
                value={selectedSentenceInterpretation.interpretation.information_value_reason || "n/a"}
              />
              <DetailField
                label="Mondatvágás"
                value={getSentenceSplitSummary(selectedSentenceInterpretation.interpretation.metadata)}
              />
              <DetailField
                label="Finomvágás részlet"
                value={getSentenceRefinementSummary(selectedSentenceInterpretation.interpretation.metadata)}
              />
            </div>
            <div className="app-surface p-4">
              <div className="text-sm text-[var(--color-muted)]">Mondat</div>
              <div className="mt-2 whitespace-pre-wrap text-sm">{selectedSentenceInterpretation.interpretation.sentence_text}</div>
            </div>
            <div className="grid gap-5 xl:grid-cols-2">
              <div className="app-surface p-4">
                <h3 className="text-lg font-semibold">Mentionök</h3>
                <div className="mt-4 space-y-3">
                  {selectedSentenceInterpretation.mentions.length ? (
                    selectedSentenceInterpretation.mentions.map((mention) => (
                      <div key={mention.id} className="rounded-lg border border-[var(--color-border)] p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="font-medium">{mention.text_content}</div>
                          <div className="text-xs text-[var(--color-muted)]">{getMentionTypeLabel(mention.mention_type)}</div>
                        </div>
                        <div className="mt-2 text-xs text-[var(--color-muted)]">
                          span: {mention.char_start}-{mention.char_end}
                          {mention.normalized_value ? ` | normalizált: ${mention.normalized_value}` : ""}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-[var(--color-muted)]">Ehhez a mondathoz még nincs mention részlet.</div>
                  )}
                </div>
              </div>
              <div className="app-surface p-4">
                <h3 className="text-lg font-semibold">Claim-ek</h3>
                <div className="mt-4 space-y-3">
                  {selectedSentenceInterpretation.claims.length ? (
                    selectedSentenceInterpretation.claims.map((claim) => (
                      <div key={claim.id} className="rounded-lg border border-[var(--color-border)] p-3">
                        <div className="font-medium">
                          {claim.subject_text} {"->"} {claim.predicate_text}
                        </div>
                        <div className="mt-2 text-sm whitespace-pre-wrap">
                          {claim.object_text || "Nincs külön objektum / érték."}
                        </div>
                        <div className="mt-2 text-xs text-[var(--color-muted)]">
                          típus: {claim.claim_type} | mód: {claim.assertion_mode} | idő: {claim.time_mode}
                          {claim.time_label ? ` (${claim.time_label})` : ""}
                          {" | "}
                          tér: {claim.space_mode}
                          {claim.space_label ? ` (${claim.space_label})` : ""}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-[var(--color-muted)]">Ehhez a mondathoz még nincs claim részlet.</div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-sm text-[var(--color-muted)]">Ehhez a mondathoz még nincs értelmezési részlet.</div>
        )}
        <ModalFooter>
          <Button variant="secondary" onClick={() => setShowSentenceInterpretationModal(false)}>
            Bezárás
          </Button>
        </ModalFooter>
      </Modal>
    </div>
  );
}
