/**
 * Full-screen overlay with spinner and progress percentage.
 * Shown during training and text cleaning (PII processing).
 * 100% = összes mondat; százalék = feldolgozott mondatok / összes mondat.
 */
import { useEffect, useState } from "react";

type ProcessProgressOverlayProps = {
  /** Whether the process is running */
  isActive: boolean;
  /** Label shown above the progress (e.g. "Feldolgozás…") */
  label: string;
  /** Optional: sub-label (e.g. "Szöveg tisztítása…") */
  subLabel?: string;
  /** Total sentences – 100% = mind; ha megadva, mondat-alapú százalék */
  totalSentences?: number | null;
};

/** Ha nincs totalSentences: időalapú szimuláció ~45s alatt 95%-ig */
const PROGRESS_DURATION_MS = 45_000;
const TARGET_BEFORE_DONE = 95;
/** Becsült másodperc per mondat (backend feldolgozási sebesség) */
const SECONDS_PER_SENTENCE = 0.4;

export function ProcessProgressOverlay({
  isActive,
  label,
  subLabel,
  totalSentences,
}: ProcessProgressOverlayProps) {
  const [percent, setPercent] = useState(0);

  useEffect(() => {
    if (!isActive) {
      setPercent(100);
      const t = setTimeout(() => setPercent(0), 600);
      return () => clearTimeout(t);
    }
    setPercent(0);
    const start = Date.now();
    const total = totalSentences ?? 0;
    const interval = setInterval(() => {
      const elapsed = Date.now() - start;
      let p: number;
      if (total > 0) {
        const estimatedProcessed = elapsed / (SECONDS_PER_SENTENCE * 1000);
        const processed = Math.min(total, estimatedProcessed);
        p = Math.min(TARGET_BEFORE_DONE, (processed / total) * 100);
      } else {
        p = Math.min(
          TARGET_BEFORE_DONE,
          (elapsed / PROGRESS_DURATION_MS) * TARGET_BEFORE_DONE
        );
      }
      setPercent(Math.round(p));
    }, 200);
    return () => clearInterval(interval);
  }, [isActive, totalSentences]);

  if (!isActive && percent === 0) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-black/60 backdrop-blur-sm"
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <div className="flex flex-col items-center gap-6 p-8 rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] shadow-2xl max-w-sm w-full mx-4">
        {/* Spinner */}
        <div
          className="w-14 h-14 rounded-full border-4 border-[var(--color-border)] border-t-[var(--color-primary)] animate-spin"
          aria-hidden="true"
        />
        <div className="text-center space-y-1">
          <p className="text-lg font-semibold text-[var(--color-foreground)]">
            {label}
          </p>
          {subLabel && (
            <p className="text-sm text-[var(--color-muted)]">{subLabel}</p>
          )}
        </div>
        {/* Progress bar + percentage */}
        <div className="w-full space-y-2">
          <div className="h-2 w-full rounded-full bg-[var(--color-input-bg)] overflow-hidden">
            <div
              className="h-full bg-[var(--color-primary)] transition-all duration-300 ease-out"
              style={{ width: `${percent}%` }}
            />
          </div>
          <p className="text-center text-sm font-medium text-[var(--color-foreground)]">
            {percent}%
          </p>
        </div>
      </div>
    </div>
  );
}
