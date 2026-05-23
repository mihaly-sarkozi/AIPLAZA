/**
 * Full-screen overlay with spinner and progress percentage.
 * Shown during training and text cleaning (PII processing).
 * Fázis-alapú progress: 5 ütem, mindegyik 20%, egyenletesen 0→99%-ig.
 * 100% = kész (isActive false).
 */
import { useEffect, useState } from "react";
import { useTranslation } from "../i18n";

type ProcessProgressOverlayProps = {
  /** Whether the process is running */
  isActive: boolean;
  /** Label shown above the progress (e.g. "Feldolgozás…") */
  label: string;
  /** Optional: sub-label override (e.g. "Szöveg tisztítása…" PII confirm esetén) */
  subLabel?: string;
  /** Total sentences – ha megadva, becsült idő = mondatok * 1.2s; különben ~50s */
  totalSentences?: number | null;
};

/** 5 fázis, mindegyik 20% súllyal. Egyenletes progress 0→99%-ig. */
const PHASE_COUNT = 5;
const PHASE_WEIGHT = 100 / PHASE_COUNT; // 20%
/** Ha nincs totalSentences: ~50s becsült teljes idő */
const FALLBACK_DURATION_MS = 50_000;
/** Mondat-alapú becslés: sec/mondat (konzervatív, mert extraction+indexing lassabb) */
const SECONDS_PER_SENTENCE = 1.2;
/** Folyamat közben max 99%, hogy ne látszódjon 100% mielőtt tényleg kész */
const MAX_DURING_PROCESS = 99;

export function ProcessProgressOverlay({
  isActive,
  label,
  subLabel,
  totalSentences,
}: ProcessProgressOverlayProps) {
  const { t } = useTranslation();
  const [percent, setPercent] = useState(0);
  const [phaseIndex, setPhaseIndex] = useState(0);

  const phaseLabels: string[] = [
    t("kb.processingPhase1"),
    t("kb.processingPhase2"),
    t("kb.processingPhase3"),
    t("kb.processingPhase4"),
    t("kb.processingPhase5"),
  ];

  useEffect(() => {
    if (!isActive) {
      setPercent(100);
      const tId = setTimeout(() => {
        setPercent(0);
        setPhaseIndex(0);
      }, 600);
      return () => clearTimeout(tId);
    }
    setPercent(0);
    setPhaseIndex(0);
    const start = Date.now();
    const total = totalSentences ?? 0;
    const totalDurationMs =
      total > 0
        ? Math.max(10_000, total * SECONDS_PER_SENTENCE * 1000)
        : FALLBACK_DURATION_MS;
    const phaseDurationMs = totalDurationMs / PHASE_COUNT;

    const interval = setInterval(() => {
      const elapsed = Date.now() - start;
      const currentPhase = Math.min(
        PHASE_COUNT - 1,
        Math.floor(elapsed / phaseDurationMs)
      );
      const elapsedInPhase = elapsed - currentPhase * phaseDurationMs;
      const progressInPhase = Math.min(1, elapsedInPhase / phaseDurationMs);
      const rawPercent =
        currentPhase * PHASE_WEIGHT + progressInPhase * PHASE_WEIGHT;
      const p = Math.min(MAX_DURING_PROCESS, Math.round(rawPercent));
      setPercent(p);
      setPhaseIndex(currentPhase);
    }, 200);
    return () => clearInterval(interval);
  }, [isActive, totalSentences]);

  if (!isActive && percent === 0) return null;

  const displaySubLabel = subLabel ?? phaseLabels[phaseIndex];

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
          {displaySubLabel && (
            <p className="text-sm text-[var(--color-muted)]">
              {displaySubLabel}
            </p>
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
