/**
 * Többnyelvű szövegek (hu, en, es). A t() ponttal elválasztott kulcsot vár, pl. "roles.title".
 */
export type Locale = "hu" | "en" | "es";

import { hu } from "./locales/hu";
import { en } from "./locales/en";
import { es } from "./locales/es";

/** Szekciók (common, nav, roles, ...), minden szekción belül kulcs -> szöveg */
export const translations: Record<Locale, Record<string, Record<string, string>>> = { hu, en, es };
