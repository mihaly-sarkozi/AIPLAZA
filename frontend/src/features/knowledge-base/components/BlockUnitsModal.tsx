import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import type { StructureDbDetail } from "../pages/ingestDetailTypes";
import type { IngestRunTrace, IngestRunTraceClaim } from "../services";
import { claimTextForBlockClaim, getSemanticBlockContextLabel, sourceLabelForBlock } from "../pages/ingestDetailHelpers";

type BlockStatus = "draft" | "approved" | "rejected" | "withdrawn" | "outdated" | "disputed";

type BlockUnitsModalProps = {
  open: boolean;
  onClose: () => void;
  traceDetail: IngestRunTrace | null;
  traceClaimLookup: Map<string, IngestRunTraceClaim>;
  traceSentenceLookup: Map<string, NonNullable<IngestRunTrace["sentences"]>[number]>;
  updatingBlockId: string | null;
  onSetBlockStatus: (blockId: string | undefined, status: BlockStatus) => void;
  onShowDbDetail: (detail: StructureDbDetail) => void;
};

export default function BlockUnitsModal({
  open,
  onClose,
  traceDetail,
  traceClaimLookup,
  traceSentenceLookup,
  updatingBlockId,
  onSetBlockStatus,
  onShowDbDetail,
}: BlockUnitsModalProps) {
  return (
    <Modal open={open} onClose={onClose} panelClassName="max-w-6xl">
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
              const blockId = String(block.id ?? "");
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
                      <span className="rounded bg-red-500/10 px-2 py-1 text-red-700">Konfliktus: {Number(block.conflict_count ?? 0)}</span>
                    ) : null}
                    <button
                      type="button"
                      disabled={updatingBlockId === blockId}
                      className="rounded bg-emerald-500/10 px-2 py-1 text-emerald-700 hover:bg-emerald-500/20 disabled:opacity-50"
                      onClick={() => onSetBlockStatus(blockId, "approved")}
                    >
                      Jóváhagyás
                    </button>
                    <button
                      type="button"
                      disabled={updatingBlockId === blockId}
                      className="rounded bg-amber-500/10 px-2 py-1 text-amber-700 hover:bg-amber-500/20 disabled:opacity-50"
                      onClick={() => onSetBlockStatus(blockId, "outdated")}
                    >
                      Elavult
                    </button>
                    <button
                      type="button"
                      disabled={updatingBlockId === blockId}
                      className="rounded bg-red-500/10 px-2 py-1 text-red-700 hover:bg-red-500/20 disabled:opacity-50"
                      onClick={() => onSetBlockStatus(blockId, "withdrawn")}
                    >
                      Visszavonás
                    </button>
                    <button
                      type="button"
                      className="rounded bg-[var(--color-card-muted)] px-2 py-1 underline hover:text-[var(--color-primary)]"
                      onClick={() =>
                        onShowDbDetail({
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
                              onShowDbDetail({
                                title: "Állítás részletei",
                                description: claimTextForBlockClaim(claim, claimId),
                                data: {
                                  block_id: block.id ?? null,
                                  source_name: traceDetail?.source_name ?? null,
                                  source_id: traceDetail?.source_id ?? block.source_id ?? null,
                                  claim_id: claimId,
                                  claim: claim ?? null,
                                  source_sentence: claim?.claim_id
                                    ? traceDetail?.sentences.find((sentence) => sentence.claims.some((item) => item.claim_id === claim.claim_id)) ?? null
                                    : null,
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
        <Button variant="secondary" onClick={onClose}>
          Bezárás
        </Button>
      </ModalFooter>
    </Modal>
  );
}
