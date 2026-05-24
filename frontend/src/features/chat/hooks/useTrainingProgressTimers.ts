import { useCallback, useEffect, useRef, type Dispatch, type MutableRefObject, type SetStateAction } from "react";

import type { FileCountingProgress } from "../types";
import {
  estimateCountingDurationMs,
  estimatedTrainingProgress,
  estimateFileCharactersForProgress,
  estimateTrainingDurationMs,
} from "../utils/chatTraining";

type UseTrainingProgressTimersOptions = {
  trainingStartedAtRef: MutableRefObject<number | null>;
  trainingEstimatedDurationMsRef: MutableRefObject<number | null>;
  setFileCountingProgress: Dispatch<SetStateAction<FileCountingProgress | null>>;
  setTrainingVisualProgress: Dispatch<SetStateAction<number>>;
};

export function useTrainingProgressTimers({
  trainingStartedAtRef,
  trainingEstimatedDurationMsRef,
  setFileCountingProgress,
  setTrainingVisualProgress,
}: UseTrainingProgressTimersOptions) {
  const fileCountingTimerRef = useRef<number | null>(null);
  const trainingProgressTimerRef = useRef<number | null>(null);

  const stopFileCountingProgress = useCallback(() => {
    if (fileCountingTimerRef.current !== null) {
      window.clearInterval(fileCountingTimerRef.current);
      fileCountingTimerRef.current = null;
    }
  }, []);

  const startFileCountingProgress = useCallback(
    (file: File) => {
      stopFileCountingProgress();
      const estimatedCharacters = estimateFileCharactersForProgress(file);
      const durationMs = estimateCountingDurationMs(file);
      const startedAt = Date.now();
      setFileCountingProgress({ filename: file.name, percent: 3, estimatedCharacters });
      fileCountingTimerRef.current = window.setInterval(() => {
        const elapsed = Date.now() - startedAt;
        const ratio = Math.min(0.95, elapsed / durationMs);
        const eased = 1 - Math.pow(1 - ratio, 2);
        setFileCountingProgress((current) =>
          current ? { ...current, percent: Math.max(current.percent, Math.min(95, Math.round(eased * 95))) } : current
        );
      }, 180);
    },
    [setFileCountingProgress, stopFileCountingProgress]
  );

  const stopTrainingProgress = useCallback(() => {
    if (trainingProgressTimerRef.current !== null) {
      window.clearInterval(trainingProgressTimerRef.current);
      trainingProgressTimerRef.current = null;
    }
    trainingStartedAtRef.current = null;
    trainingEstimatedDurationMsRef.current = null;
  }, [trainingEstimatedDurationMsRef, trainingStartedAtRef]);

  const startTrainingProgress = useCallback(
    (characterCount: number, startedAt = Date.now()) => {
      stopTrainingProgress();
      const durationMs = estimateTrainingDurationMs(characterCount);
      trainingStartedAtRef.current = startedAt;
      trainingEstimatedDurationMsRef.current = durationMs;
      setTrainingVisualProgress((current) => Math.max(current, estimatedTrainingProgress(Date.now() - startedAt, durationMs), 6));
      trainingProgressTimerRef.current = window.setInterval(() => {
        const effectiveStartedAt = trainingStartedAtRef.current ?? startedAt;
        const effectiveDurationMs = trainingEstimatedDurationMsRef.current ?? durationMs;
        const elapsed = Date.now() - effectiveStartedAt;
        const nextProgress = estimatedTrainingProgress(elapsed, effectiveDurationMs);
        setTrainingVisualProgress((current) => Math.max(current, Math.min(99, nextProgress)));
      }, 500);
    },
    [setTrainingVisualProgress, stopTrainingProgress, trainingEstimatedDurationMsRef, trainingStartedAtRef]
  );

  const resumeTrainingProgress = useCallback(
    (activeTrainingRunId: string | undefined, activeTrainingTitle: string | null) => {
      if (!activeTrainingRunId || !activeTrainingTitle || trainingProgressTimerRef.current !== null) return;
      const startedAt = trainingStartedAtRef.current;
      const durationMs = trainingEstimatedDurationMsRef.current;
      if (!startedAt || !durationMs) return;
      setTrainingVisualProgress((current) => Math.max(current, estimatedTrainingProgress(Date.now() - startedAt, durationMs), 6));
      trainingProgressTimerRef.current = window.setInterval(() => {
        const effectiveStartedAt = trainingStartedAtRef.current ?? startedAt;
        const effectiveDurationMs = trainingEstimatedDurationMsRef.current ?? durationMs;
        const nextProgress = estimatedTrainingProgress(Date.now() - effectiveStartedAt, effectiveDurationMs);
        setTrainingVisualProgress((current) => Math.max(current, Math.min(99, nextProgress)));
      }, 500);
    },
    [setTrainingVisualProgress, trainingEstimatedDurationMsRef, trainingStartedAtRef]
  );

  useEffect(
    () => () => {
      stopFileCountingProgress();
      stopTrainingProgress();
    },
    [stopFileCountingProgress, stopTrainingProgress]
  );

  return {
    startFileCountingProgress,
    stopFileCountingProgress,
    startTrainingProgress,
    stopTrainingProgress,
    resumeTrainingProgress,
  };
}
