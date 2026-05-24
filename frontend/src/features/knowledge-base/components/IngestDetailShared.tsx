export function DetailField({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] p-4">
      <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">{label}</div>
      <div className="mt-2 text-sm text-[var(--color-foreground)]">{value}</div>
    </div>
  );
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--color-card-muted)]">
      <div className="h-full rounded-full bg-[var(--color-primary)] transition-all" style={{ width: `${value}%` }} />
    </div>
  );
}
