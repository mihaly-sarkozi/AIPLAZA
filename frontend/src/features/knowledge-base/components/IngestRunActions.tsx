import Button from "../../../components/ui/Button";
import type { IngestItem } from "../services";

type IngestRunActionsProps = {
  selectedItem: IngestItem | null;
  isOpeningSource: boolean;
  isLoadingStructure: boolean;
  isLoadingTrace: boolean;
  isLoadingSentences: boolean;
  openLabel: string;
  onOpenSource: () => void;
  onOpenStructure: () => void;
  onOpenBlocks: () => void;
  onOpenSentences: () => void;
  onBack: () => void;
};

export default function IngestRunActions({
  selectedItem,
  isOpeningSource,
  isLoadingStructure,
  isLoadingTrace,
  isLoadingSentences,
  openLabel,
  onOpenSource,
  onOpenStructure,
  onOpenBlocks,
  onOpenSentences,
  onBack,
}: IngestRunActionsProps) {
  return (
    <div className="flex gap-2">
      {selectedItem ? (
        <Button variant="primary" onClick={onOpenSource} disabled={isOpeningSource}>
          {isOpeningSource ? "Megnyitás..." : openLabel}
        </Button>
      ) : null}
      {selectedItem ? (
        <Button variant="secondary" onClick={onOpenStructure} disabled={isLoadingStructure}>
          {isLoadingStructure ? "Betöltés..." : "Szerkezet"}
        </Button>
      ) : null}
      {selectedItem ? (
        <Button variant="secondary" onClick={onOpenBlocks} disabled={isLoadingTrace}>
          {isLoadingTrace ? "Betöltés..." : "Mondat egységek / blokkok"}
        </Button>
      ) : null}
      {selectedItem ? (
        <Button variant="secondary" onClick={onOpenSentences} disabled={isLoadingSentences}>
          {isLoadingSentences ? "Betöltés..." : "Mondatok"}
        </Button>
      ) : null}
      <Button variant="secondary" onClick={onBack}>
        Vissza a naplóhoz
      </Button>
    </div>
  );
}
