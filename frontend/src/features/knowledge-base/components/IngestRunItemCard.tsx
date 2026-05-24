import type { IngestItem } from "../services";
import { formatModuleProgress, getItemPreview, getItemProcessingSummary, getStatusBadgeClass, getStatusLabel } from "../pages/ingestLogHelpers";

type IngestRunItemCardProps = {
  item: IngestItem;
  selected: boolean;
  onSelect: () => void;
};

export default function IngestRunItemCard({ item, selected, onSelect }: IngestRunItemCardProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full rounded-lg border p-4 text-left transition-colors ${
        selected ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5" : "border-[var(--color-border)] hover:bg-[var(--color-primary)]/5"
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
}
