export type BillingCustomerType = "company" | "private";

export type BillingCountryOption = {
  code: string;
  label: string;
  eu: boolean;
  disabled?: boolean;
};

export const BILLING_COUNTRY_OTHER = "OTHER";
type BillingCountryLocale = "hu" | "en" | "es";

const BILLING_COUNTRY_META: Array<Omit<BillingCountryOption, "label">> = [
  { code: "AL", eu: false },
  { code: "AD", eu: false },
  { code: "AT", eu: true },
  { code: "BE", eu: true },
  { code: "BA", eu: false },
  { code: "BG", eu: true },
  { code: "CY", eu: true },
  { code: "CZ", eu: true },
  { code: "DK", eu: true },
  { code: "GB", eu: false },
  { code: "EE", eu: true },
  { code: "FI", eu: true },
  { code: "FR", eu: true },
  { code: "GR", eu: true },
  { code: "NL", eu: true },
  { code: "HR", eu: true },
  { code: "IE", eu: true },
  { code: "IS", eu: false },
  { code: "PL", eu: true },
  { code: "LV", eu: true },
  { code: "LI", eu: false },
  { code: "LT", eu: true },
  { code: "LU", eu: true },
  { code: "HU", eu: true },
  { code: "MT", eu: true },
  { code: "MD", eu: false },
  { code: "MC", eu: false },
  { code: "ME", eu: false },
  { code: "DE", eu: true },
  { code: "NO", eu: false },
  { code: "IT", eu: true },
  { code: "PT", eu: true },
  { code: "RO", eu: true },
  { code: "SM", eu: false },
  { code: "ES", eu: true },
  { code: "CH", eu: false },
  { code: "SE", eu: true },
  { code: "RS", eu: false },
  { code: "SK", eu: true },
  { code: "SI", eu: true },
  { code: "TR", eu: false },
  { code: "UA", eu: false },
  { code: "VA", eu: false },
  { code: "XK", eu: false },
  { code: BILLING_COUNTRY_OTHER, eu: false, disabled: true },
];

const OTHER_COUNTRY_LABELS: Record<BillingCountryLocale, string> = {
  hu: "Egyéb",
  en: "Other",
  es: "Otro",
};

const COUNTRY_LABEL_FALLBACKS: Record<BillingCountryLocale, Record<string, string>> = {
  hu: { XK: "Koszovó" },
  en: { XK: "Kosovo" },
  es: { XK: "Kosovo" },
};

export const BILLING_COUNTRIES: BillingCountryOption[] = getBillingCountryOptions("hu");

export function getBillingCountryOptions(locale: BillingCountryLocale): BillingCountryOption[] {
  const displayNames = new Intl.DisplayNames([locale], { type: "region" });
  const collator = new Intl.Collator(locale, { sensitivity: "base" });
  const countries = BILLING_COUNTRY_META.filter((country) => country.code !== BILLING_COUNTRY_OTHER)
    .map((country) => ({
      ...country,
      label: COUNTRY_LABEL_FALLBACKS[locale][country.code] ?? displayNames.of(country.code) ?? country.code,
    }))
    .sort((left, right) => collator.compare(left.label, right.label));
  return [
    ...countries,
    {
      code: BILLING_COUNTRY_OTHER,
      label: OTHER_COUNTRY_LABELS[locale],
      eu: false,
      disabled: true,
    },
  ];
}

export const BILLING_REGIONS_BY_COUNTRY: Record<string, string[]> = {
  CH: ["Aargau", "Bern", "Basel-Landschaft", "Basel-Stadt", "Genf", "Graubünden", "Luzern", "Ticino", "Vaud", "Zürich"],
  ES: [
    "A Coruña",
    "Álava",
    "Albacete",
    "Alicante",
    "Almería",
    "Asturias",
    "Ávila",
    "Badajoz",
    "Barcelona",
    "Burgos",
    "Cáceres",
    "Cádiz",
    "Cantabria",
    "Castellón",
    "Ceuta",
    "Ciudad Real",
    "Córdoba",
    "Cuenca",
    "Girona",
    "Granada",
    "Guadalajara",
    "Gipuzkoa",
    "Huelva",
    "Huesca",
    "Illes Balears",
    "Jaén",
    "La Rioja",
    "Las Palmas",
    "León",
    "Lleida",
    "Lugo",
    "Madrid",
    "Málaga",
    "Melilla",
    "Murcia",
    "Navarra",
    "Ourense",
    "Palencia",
    "Pontevedra",
    "Salamanca",
    "Santa Cruz de Tenerife",
    "Segovia",
    "Sevilla",
    "Soria",
    "Tarragona",
    "Teruel",
    "Toledo",
    "Valencia",
    "Valladolid",
    "Bizkaia",
    "Zamora",
    "Zaragoza",
  ],
  GB: ["Anglia", "Észak-Írország", "Skócia", "Wales"],
  IT: ["Abruzzo", "Lazio", "Lombardia", "Piemonte", "Sicilia", "Toscana", "Veneto"],
};

const EU_VAT_PATTERNS: Record<string, RegExp> = {
  AT: /^ATU\d{8}$/,
  BE: /^BE0\d{9}$/,
  BG: /^BG\d{9,10}$/,
  CY: /^CY\d{8}[A-Z]$/,
  CZ: /^CZ\d{8,10}$/,
  DE: /^DE\d{9}$/,
  DK: /^DK\d{8}$/,
  EE: /^EE\d{9}$/,
  ES: /^ES([A-Z]\d{8}|\d{8}[A-Z]|[A-Z]\d{7}[A-Z0-9])$/,
  FI: /^FI\d{8}$/,
  FR: /^FR[A-Z0-9]{2}\d{9}$/,
  GR: /^EL\d{9}$/,
  HR: /^HR\d{11}$/,
  HU: /^HU\d{8}$/,
  IE: /^IE\d[A-Z0-9]\d{5}[A-Z]{1,2}$/,
  IT: /^IT\d{11}$/,
  LT: /^LT(\d{9}|\d{12})$/,
  LU: /^LU\d{8}$/,
  LV: /^LV\d{11}$/,
  MT: /^MT\d{8}$/,
  NL: /^NL\d{9}B\d{2}$/,
  PL: /^PL\d{10}$/,
  PT: /^PT\d{9}$/,
  RO: /^RO\d{2,10}$/,
  SE: /^SE\d{12}$/,
  SI: /^SI\d{8}$/,
  SK: /^SK\d{10}$/,
};

const EU_VAT_PLACEHOLDERS: Record<string, string> = {
  AT: "ATU12345678",
  BE: "BE0123456789",
  BG: "BG123456789",
  CY: "CY12345678X",
  CZ: "CZ12345678",
  DE: "DE123456789",
  DK: "DK12345678",
  EE: "EE123456789",
  ES: "ESB12345678",
  FI: "FI12345678",
  FR: "FRXX123456789",
  GR: "EL123456789",
  HR: "HR12345678901",
  HU: "HU12345678",
  IE: "IE1X12345X",
  IT: "IT12345678901",
  LT: "LT123456789",
  LU: "LU12345678",
  LV: "LV12345678901",
  MT: "MT12345678",
  NL: "NL123456789B01",
  PL: "PL1234567890",
  PT: "PT123456789",
  RO: "RO123456789",
  SE: "SE123456789012",
  SI: "SI12345678",
  SK: "SK1234567890",
};

export function normalizePostalCode(value: string): string {
  return value.replace(/[^\dA-Za-z -]/g, "").slice(0, 16).toUpperCase();
}

export function isValidPostalCode(value: string): boolean {
  return /^[\dA-Za-z][\dA-Za-z -]{0,15}$/.test(value.trim());
}

export function normalizeEuVatId(value: string): string {
  return value.replace(/[\s.-]/g, "").toUpperCase();
}

export function isEuBillingCountry(countryCode: string): boolean {
  return BILLING_COUNTRIES.some((country) => country.code === countryCode && country.eu);
}

export function isValidEuropeanBillingCountry(countryCode: string): boolean {
  return BILLING_COUNTRIES.some((country) => country.code === countryCode && !country.disabled);
}

export function isRegionRequired(countryCode: string): boolean {
  return Object.prototype.hasOwnProperty.call(BILLING_REGIONS_BY_COUNTRY, countryCode);
}

export function isValidEuVatId(countryCode: string, value: string): boolean {
  const pattern = EU_VAT_PATTERNS[countryCode];
  if (!pattern) return false;
  return pattern.test(normalizeEuVatId(value));
}

export function getEuVatPlaceholder(countryCode: string): string {
  return EU_VAT_PLACEHOLDERS[countryCode] ?? "EU VAT ID";
}
