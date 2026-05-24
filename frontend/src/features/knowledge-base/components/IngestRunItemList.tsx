import type { IngestItem, IngestRun } from "../services";
import IngestRunItemCard from "./IngestRunItemCard";

type IngestRunItemListProps = {
  uuid: string | undefined;
  run: IngestRun;
  selectedItem: IngestItem | null;
  onNavigate: (url: string) => void;
};

export default function IngestRunItemList({ uuid, run, selectedItem, onNavigate }: IngestRunItemListProps) {
  if (run.items.length <= 1) return null;
  return (
    <div className="app-surface p-5">
      <h2 className="text-xl font-semibold">Run tételek</h2>
      <div className="mt-4 space-y-3">
        {run.items.map((item) => {
          const detailUrl = `/kb/ingest/${uuid}/runs/${run.id}?item=${encodeURIComponent(item.id)}`;
          return (
            <IngestRunItemCard
              key={item.id}
              item={item}
              selected={selectedItem?.id === item.id}
              onSelect={() => onNavigate(detailUrl)}
            />
          );
        })}
      </div>
    </div>
  );
}
