import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { SentenceInterpretationDetail } from "../pages/ingestDetailTypes";
import {
  getAssertionModeLabel,
  getClaimTypeLabel,
  getInformationValueStatusLabel,
  getMentionTypeLabel,
  getSentenceRefinementSummary,
  getSentenceSplitSummary,
} from "../pages/ingestDetailHelpers";
import { DetailField } from "./IngestDetailShared";

type SentenceInterpretationModalProps = {
  open: boolean;
  onClose: () => void;
  detail: SentenceInterpretationDetail | null;
};

export default function SentenceInterpretationModal({ open, onClose, detail }: SentenceInterpretationModalProps) {
  return (
    <Modal open={open} onClose={onClose} panelClassName="max-w-6xl">
      <ModalHeader title="Mondatértelmezés" description="A kiválasztott mondat strukturált szemantikai értelmezése." />
      {detail ? (
        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <DetailField label="Állítás összefoglaló" value={detail.interpretation.claim_summary || "n/a"} />
            <DetailField label="Állítás természete" value={getAssertionModeLabel(detail.interpretation.assertion_mode)} />
            <DetailField label="Claim típus" value={getClaimTypeLabel(detail.interpretation.claim_type)} />
            <DetailField
              label="Tér-idő keret"
              value={`${detail.interpretation.time_mode}${detail.interpretation.time_label ? ` / ${detail.interpretation.time_label}` : ""}${detail.interpretation.space_label ? ` / ${detail.interpretation.space_label}` : ""}`}
            />
            <DetailField label="Információérték" value={`${detail.interpretation.information_value_score}/10`} />
            <DetailField label="Információérték státusz" value={getInformationValueStatusLabel(detail.interpretation.information_value_status)} />
            <DetailField label="Információérték indok" value={detail.interpretation.information_value_reason || "n/a"} />
            <DetailField label="Mondatvágás" value={getSentenceSplitSummary(detail.interpretation.metadata)} />
            <DetailField label="Finomvágás részlet" value={getSentenceRefinementSummary(detail.interpretation.metadata)} />
          </div>
          <div className="app-surface p-4">
            <div className="text-sm text-[var(--color-muted)]">Mondat</div>
            <div className="mt-2 whitespace-pre-wrap text-sm">{detail.interpretation.sentence_text}</div>
          </div>
          <div className="grid gap-5 xl:grid-cols-2">
            <div className="app-surface p-4">
              <h3 className="text-lg font-semibold">Mentionök</h3>
              <div className="mt-4 space-y-3">
                {detail.mentions.length ? (
                  detail.mentions.map((mention) => (
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
                {detail.claims.length ? (
                  detail.claims.map((claim) => (
                    <div key={claim.id} className="rounded-lg border border-[var(--color-border)] p-3">
                      <div className="font-medium">
                        {claim.subject_text} {"->"} {claim.predicate_text}
                      </div>
                      <div className="mt-2 text-sm whitespace-pre-wrap">{claim.object_text || "Nincs külön objektum / érték."}</div>
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
        <Button variant="secondary" onClick={onClose}>
          Bezárás
        </Button>
      </ModalFooter>
    </Modal>
  );
}
