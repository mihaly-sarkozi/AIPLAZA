/**
 * Többnyelvű szövegek (hu, en, es). A t() ponttal elválasztott kulcsot vár, pl. "roles.title".
 */
export type Locale = "hu" | "en" | "es";

import { hu } from "./locales/hu";
import { en } from "./locales/en";
import { es } from "./locales/es";

/** Szekciók (common, nav, roles, ...) és beágyazott kulcsfa */
export interface TranslationTree {
  [key: string]: string | TranslationTree;
}

export const translations: Record<Locale, TranslationTree> = { hu, en, es };
