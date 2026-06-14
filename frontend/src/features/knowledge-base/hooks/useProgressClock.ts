import { useEffect, useState } from "react";

/** Futó progress interpolációhoz: másodpercenként frissülő időbélyeg. */
export function useProgressClock(active: boolean, intervalMs = 1000): number {
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    if (!active) return undefined;
    setNowMs(Date.now());
    const timer = window.setInterval(() => setNowMs(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [active, intervalMs]);

  return nowMs;
}
