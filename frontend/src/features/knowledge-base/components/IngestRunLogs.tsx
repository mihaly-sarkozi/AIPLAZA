import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { SentenceRow } from "../pages/ingestDetailTypes";
import {
  getInformationValueBadgeClass,
  getInformationValueStatusLabel,
  getSentenceRefinementSummary,
  getSentenceSplitSummary,
} from "../pages/ingestDetailHelpers";

type IngestRunLogsProps = {
  open: boolean;
  onClose: () => void;
  sentenceRows: SentenceRow[];
  isLoadingSentenceInterpretation: boolean;
  onOpenSentenceInterpretation: (sentenceId: string) => void;
};

export default function IngestRunLogs({
  open,
  onClose,
  sentenceRows,
  isLoadingSentenceInterpretation,
  onOpenSentenceInterpretation,
}: IngestRunLogsProps) {
  return (
    <Modal open={open} onClose={onClose} panelClassName="max-w-5xl">
      <ModalHeader title="Mondatokra bontott rekordok" description="Az aktuális tanítási rekordhoz tartozó mondatok listája." />
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
                  onClick={() => onOpenSentenceInterpretation(sentence.id)}
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
                        {typeof sentence.metadata?.information_value_score === "number" ? `${sentence.metadata.information_value_score}/10` : "n/a"}
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
        <Button variant="secondary" onClick={onClose}>
          Bezárás
        </Button>
      </ModalFooter>
    </Modal>
  );
}
