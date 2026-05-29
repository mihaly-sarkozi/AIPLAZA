// frontend/src/features/settings/hooks/useClipboard.ts
// Feladat: Egységes vágólap-segéd hook fallback másolási logikával.
// Sárközi Mihály - 2026.05.29

import { useCallback } from "react";

export function useClipboard() {
  const copy = useCallback(async (value: string): Promise<boolean> => {
    const text = value.trim();
    if (!text) return false;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
      if (typeof document !== "undefined") {
        const el = document.createElement("textarea");
        el.value = text;
        el.style.position = "fixed";
        el.style.opacity = "0";
        document.body.appendChild(el);
        el.focus();
        el.select();
        document.execCommand("copy");
        document.body.removeChild(el);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }, []);

  return { copy };
}
