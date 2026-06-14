import { create } from "zustand";
import type { Locale, TranslationTree } from "./translations";
import { translations } from "./translations";

const DEFAULT_LOCALE: Locale = "hu";
const THEME_STORAGE_KEY = "AIPLAZA_theme";
export type Theme = "light" | "dark";

function applyThemeToDocument(theme: Theme) {
  if (typeof document !== "undefined") {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }
}

function getStoredTheme(): Theme {
  if (typeof localStorage === "undefined") return "light";
  const v = localStorage.getItem(THEME_STORAGE_KEY);
  return v === "dark" || v === "light" ? v : "light";
}

function initTheme(): Theme {
  const theme = getStoredTheme();
  applyThemeToDocument(theme);
  return theme;
}

/** Ponttal elválasztott kulcs, pl. "common.loading" vagy "kb.processingMonitor.title" */
function getTranslation(locale: Locale, key: string): string {
  const parts = key.split(".");
  let current: string | TranslationTree | undefined = translations[locale];
  for (const part of parts) {
    if (!current || typeof current !== "object") {
      if (locale !== DEFAULT_LOCALE) return getTranslation(DEFAULT_LOCALE, key);
      return key;
    }
    current = current[part];
  }
  if (typeof current === "string") return current;
  if (locale !== DEFAULT_LOCALE) return getTranslation(DEFAULT_LOCALE, key);
  return key;
}

interface LocaleState {
  locale: Locale;
  theme: Theme;
  setLocale: (locale: Locale) => void;
  setTheme: (theme: Theme) => void;
  /** Szerverről jövő értékek (belépés / default-settings) – nem mentjük localStorage-ba */
  setLocaleAndTheme: (locale: Locale, theme: Theme) => void;
}

export const useLocaleStore = create<LocaleState>((set) => ({
  locale: DEFAULT_LOCALE,
  theme: typeof window !== "undefined" ? initTheme() : "light",
  setLocale: (locale) => set({ locale }),
  setTheme: (theme) => {
    applyThemeToDocument(theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      void 0;
    }
    set({ theme });
  },
  setLocaleAndTheme: (locale, theme) => {
    applyThemeToDocument(theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      void 0;
    }
    set({ locale, theme });
  },
}));

/** Aktuális nyelv alapján fordít; hiányzó kulcsnál fallback hu, majd a kulcs maga */
export function t(key: string, locale?: Locale): string {
  const current = locale ?? useLocaleStore.getState().locale;
  return getTranslation(current, key);
}

/** React hook: t függvény + locale/theme + setters */
export function useTranslation() {
  const locale = useLocaleStore((s) => s.locale);
  const theme = useLocaleStore((s) => s.theme);
  const setLocale = useLocaleStore((s) => s.setLocale);
  const setTheme = useLocaleStore((s) => s.setTheme);
  const translate = (key: string) => getTranslation(locale, key);
  return { t: translate, locale, setLocale, theme, setTheme };
}

export type { Locale };
export { translations };
