export const EU_COUNTRIES = [
  "Ausztria",
  "Belgium",
  "Bulgária",
  "Ciprus",
  "Csehország",
  "Dánia",
  "Észtország",
  "Finnország",
  "Franciaország",
  "Görögország",
  "Hollandia",
  "Horvátország",
  "Írország",
  "Lengyelország",
  "Lettország",
  "Litvánia",
  "Luxemburg",
  "Magyarország",
  "Málta",
  "Németország",
  "Olaszország",
  "Portugália",
  "Románia",
  "Spanyolország",
  "Svédország",
  "Szlovákia",
  "Szlovénia",
];

const EU_VAT_PATTERNS: Record<string, RegExp> = {
  Ausztria: /^ATU\d{8}$/,
  Belgium: /^BE0\d{9}$/,
  Bulgária: /^BG\d{9,10}$/,
  Ciprus: /^CY\d{8}[A-Z]$/,
  Csehország: /^CZ\d{8,10}$/,
  Dánia: /^DK\d{8}$/,
  Észtország: /^EE\d{9}$/,
  Finnország: /^FI\d{8}$/,
  Franciaország: /^FR[A-Z0-9]{2}\d{9}$/,
  Görögország: /^EL\d{9}$/,
  Hollandia: /^NL\d{9}B\d{2}$/,
  Horvátország: /^HR\d{11}$/,
  Írország: /^IE\d[A-Z0-9]\d{5}[A-Z]{1,2}$/,
  Lengyelország: /^PL\d{10}$/,
  Lettország: /^LV\d{11}$/,
  Litvánia: /^LT(\d{9}|\d{12})$/,
  Luxemburg: /^LU\d{8}$/,
  Magyarország: /^HU\d{8}$/,
  Málta: /^MT\d{8}$/,
  Németország: /^DE\d{9}$/,
  Olaszország: /^IT\d{11}$/,
  Portugália: /^PT\d{9}$/,
  Románia: /^RO\d{2,10}$/,
  Spanyolország: /^ES[A-Z0-9]\d{7}[A-Z0-9]$/,
  Svédország: /^SE\d{12}$/,
  Szlovákia: /^SK\d{10}$/,
  Szlovénia: /^SI\d{8}$/,
};

export function normalizePostalCode(value: string): string {
  return value.replace(/\D/g, "").slice(0, 5);
}

export function isValidPostalCode(value: string): boolean {
  return /^\d{1,5}$/.test(value.trim());
}

export function normalizeEuVatId(value: string): string {
  return value.replace(/[\s.-]/g, "").toUpperCase();
}

export function isValidEuVatId(country: string, value: string): boolean {
  const pattern = EU_VAT_PATTERNS[country];
  if (!pattern) return false;
  return pattern.test(normalizeEuVatId(value));
}
