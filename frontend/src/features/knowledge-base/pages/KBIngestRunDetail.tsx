import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";

import api from "../../../api/axiosClient";
import Alert from "../../../components/ui/Alert";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { useTranslation } from "../../../i18n";
import { useLocaleSettings } from "../../settings/hooks/useSettings";
import { useKbList } from "../hooks/useKb";
import {
  getItemProcessingSummary,
  getRunProgressSummary,
  getRunPrimaryItem,
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
import type { ParagraphRow, SentenceInterpretationDetail, SentenceRow, StructureDbDetail } from "./ingestDetailTypes";
import BlockUnitsModal from "../components/BlockUnitsModal";
import IngestRunDiagnostics from "../components/IngestRunDiagnostics";
import IngestRunHeader from "../components/IngestRunHeader";
import IngestRunItemList from "../components/IngestRunItemList";
import IngestRunLogs from "../components/IngestRunLogs";
import IngestRunProgress from "../components/IngestRunProgress";
import SentenceInterpretationModal from "../components/SentenceInterpretationModal";
import StructureDbDetailModal from "../components/StructureDbDetailModal";
import { useIngestRunPolling } from "../hooks/useIngestRunPolling";

export default function KBIngestRunDetail() {
  const { locale } = useTranslation();
  const { uuid, runId } = useParams();
  const navigate = useNavigate();
  const { data: settings } = useLocaleSettings();
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

  const runQuery = useIngestRunPolling(runId);

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
  const runProgressSummary = useMemo(() => getRunProgressSummary(run), [run]);
  const parserErrorMessage =
    (typeof processingSummary.modules.parser?.error_message === "string" && processingSummary.modules.parser.error_message.trim()) ||
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
      const response = await api.get<ArrayBuffer>(`/kb/ingest/items/${selectedItem.id}/raw`, {
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
        <IngestRunHeader
          selectedItem={selectedItem}
          isOpeningSource={isOpeningSource}
          isLoadingStructure={isLoadingStructure}
          isLoadingTrace={isLoadingTrace}
          isLoadingSentences={isLoadingSentences}
          openLabel={openLabel}
          onOpenSource={openSource}
          onOpenStructure={openStructure}
          onOpenBlocks={() => setShowBlockUnitsModal(true)}
          onOpenSentences={openSentences}
          onBack={() => navigate(`/kb/ingest/${uuid}`)}
        />

        {error ? <Alert tone="error">{error}</Alert> : null}

        {run ? (
          <section className="space-y-6">
            <IngestRunProgress
              run={run}
              selectedItem={selectedItem}
              kb={kb}
              parserErrorMessage={parserErrorMessage}
              locale={locale}
              timezone={settings?.timezone}
              dateFormat={settings?.date_format}
              timeFormat={settings?.time_format}
            />
            <IngestRunItemList uuid={uuid} run={run} selectedItem={selectedItem} onNavigate={(url) => navigate(url)} />
          </section>
        ) : (
          <div className="app-surface p-5 text-sm text-[var(--color-muted)]">A tanítás részletei betöltés alatt állnak.</div>
        )}
      </div>
      <IngestRunDiagnostics
        showStructureModal={showStructureModal}
        onCloseStructure={() => setShowStructureModal(false)}
        paragraphRows={paragraphRows}
        selectedStructureParagraphId={selectedStructureParagraphId}
        onToggleParagraph={(paragraphId) => void toggleStructureParagraph(paragraphId)}
        showStructureSentencesModal={showStructureSentencesModal}
        onCloseStructureSentences={() => setShowStructureSentencesModal(false)}
        selectedStructureParagraph={selectedStructureParagraph}
        isLoadingStructureSentences={isLoadingStructureSentences}
        getStructureParagraphSentences={getStructureParagraphSentences}
        onOpenSentenceInterpretation={(sentenceId) => void openSentenceInterpretation(sentenceId)}
      />
      <BlockUnitsModal
        open={showBlockUnitsModal}
        onClose={() => setShowBlockUnitsModal(false)}
        traceDetail={traceDetail}
        traceClaimLookup={traceClaimLookup}
        traceSentenceLookup={traceSentenceLookup}
        updatingBlockId={updatingBlockId}
        onSetBlockStatus={(blockId, status) => void setBlockStatus(blockId, status)}
        onShowDbDetail={setStructureDbDetail}
      />
      <StructureDbDetailModal detail={structureDbDetail} onClose={() => setStructureDbDetail(null)} />
      <IngestRunLogs
        open={showSentencesModal}
        onClose={() => setShowSentencesModal(false)}
        sentenceRows={sentenceRows}
        isLoadingSentenceInterpretation={isLoadingSentenceInterpretation}
        onOpenSentenceInterpretation={(sentenceId) => void openSentenceInterpretation(sentenceId)}
      />
      <SentenceInterpretationModal
        open={showSentenceInterpretationModal}
        onClose={() => setShowSentenceInterpretationModal(false)}
        detail={selectedSentenceInterpretation}
      />
    </div>
  );
}
