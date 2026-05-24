import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { ParagraphRow, SentenceRow } from "../pages/ingestDetailTypes";
import {
  formatSplitConfidence,
  getBlockTypeLabel,
  getParagraphDebugDetails,
  getParagraphRoleSummary,
  getSentenceRefinementSummary,
  getSentenceSplitSummary,
} from "../pages/ingestDetailHelpers";

type IngestRunDiagnosticsProps = {
  showStructureModal: boolean;
  onCloseStructure: () => void;
  paragraphRows: ParagraphRow[];
  selectedStructureParagraphId: string | null;
  onToggleParagraph: (paragraphId: string) => void;
  showStructureSentencesModal: boolean;
  onCloseStructureSentences: () => void;
  selectedStructureParagraph: ParagraphRow | null;
  isLoadingStructureSentences: boolean;
  getStructureParagraphSentences: (paragraphId: string) => SentenceRow[];
  onOpenSentenceInterpretation: (sentenceId: string) => void;
};

export default function IngestRunDiagnostics({
  showStructureModal,
  onCloseStructure,
  paragraphRows,
  selectedStructureParagraphId,
  onToggleParagraph,
  showStructureSentencesModal,
  onCloseStructureSentences,
  selectedStructureParagraph,
  isLoadingStructureSentences,
  getStructureParagraphSentences,
  onOpenSentenceInterpretation,
}: IngestRunDiagnosticsProps) {
  return (
    <>
      <Modal open={showStructureModal} onClose={onCloseStructure} panelClassName="max-w-6xl">
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
                      onClick={() => onToggleParagraph(paragraph.id)}
                    >
                      <td className="px-3 py-2">{paragraph.order_index}</td>
                      <td className="px-3 py-2">{getBlockTypeLabel(paragraph.metadata?.block_type)}</td>
                      <td className="px-3 py-2">{getParagraphRoleSummary(paragraph)}</td>
                      <td className="px-3 py-2">{String(paragraph.metadata?.page_number ?? "-")}</td>
                      <td className="px-3 py-2">{paragraph.sentence_count}</td>
                      <td className="px-3 py-2">
                        {paragraph.char_start}-{paragraph.char_end}
                      </td>
                      <td className="px-3 py-2 text-xs text-[var(--color-muted)] whitespace-pre-wrap">{getParagraphDebugDetails(paragraph)}</td>
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
          <Button variant="secondary" onClick={onCloseStructure}>
            Bezárás
          </Button>
        </ModalFooter>
      </Modal>

      <Modal open={showStructureSentencesModal} onClose={onCloseStructureSentences} panelClassName="max-w-5xl">
        <ModalHeader
          title="A blokkból képzett mondatok"
          description="A kiválasztott szerkezeti sorból keletkező mondatok, a vágás okával és biztonságával együtt."
        />
        {selectedStructureParagraph ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-[var(--color-border)] p-4">
              <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Kiválasztott szerkezeti sor</div>
              <div className="mt-2 text-sm text-[var(--color-foreground)] whitespace-pre-wrap">{selectedStructureParagraph.text_content}</div>
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
                          onClick={() => onOpenSentenceInterpretation(sentence.id)}
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
          <Button variant="secondary" onClick={onCloseStructureSentences}>
            Bezárás
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
}
