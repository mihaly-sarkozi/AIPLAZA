import PageHeader from "../../../components/ui/PageHeader";
import type { IngestItem } from "../services";
import IngestRunActions from "./IngestRunActions";

type IngestRunHeaderProps = {
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

export default function IngestRunHeader(props: IngestRunHeaderProps) {
  return (
    <PageHeader
      eyebrow="Tanítás részletei"
      title={props.selectedItem ? props.selectedItem.title : "Tanítás részletei"}
      description="Ez az oldal most csak a fő adatokat mutatja. A későbbi értelmezés és feldolgozás ezen a nézeten jelenik majd meg."
      actions={<IngestRunActions {...props} />}
    />
  );
}
