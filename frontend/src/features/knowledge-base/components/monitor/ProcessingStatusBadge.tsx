import { cn } from "../../../../utils/cn";

type ProcessingStatusBadgeProps = {
  status: string;
  label: string;
};

const STATUS_CLASS: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-800",
  failed: "bg-red-100 text-red-800",
  partial: "bg-amber-100 text-amber-900",
  running: "bg-sky-100 text-sky-800",
  started: "bg-sky-100 text-sky-800",
  skipped: "bg-slate-100 text-slate-700",
  unknown: "bg-slate-100 text-slate-700",
};

export default function ProcessingStatusBadge({ status, label }: ProcessingStatusBadgeProps) {
  const normalized = status.trim().toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
        STATUS_CLASS[normalized] ?? STATUS_CLASS.unknown
      )}
    >
      {label}
    </span>
  );
}
