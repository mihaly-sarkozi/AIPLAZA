import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../api/services/settingsService";

export function localeTag(locale: string): string {
  if (locale === "es") return "es-ES";
  if (locale === "en") return "en-GB";
  return "hu-HU";
}

export function dateOptionsFromFormat(): Intl.DateTimeFormatOptions {
  return { year: "numeric", month: "2-digit", day: "2-digit" };
}

export function timeOptionsFromFormat(format?: SettingsTimeFormat): Intl.DateTimeFormatOptions {
  if (format === "HH:mm:ss") return { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false };
  if (format === "hh:mm A") return { hour: "2-digit", minute: "2-digit", hour12: true };
  return { hour: "2-digit", minute: "2-digit", hour12: false };
}

function dateParts(
  date: Date,
  {
    locale,
    timezone,
  }: {
    locale: string;
    timezone?: SettingsTimezone | string;
  }
): Record<string, string> {
  const parts = new Intl.DateTimeFormat(localeTag(locale), {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: timezone || undefined,
  }).formatToParts(date);
  return Object.fromEntries(parts.map((part) => [part.type, part.value]));
}

function formatDateByPreference(
  date: Date,
  {
    locale,
    timezone,
    dateFormat,
  }: {
    locale: string;
    timezone?: SettingsTimezone | string;
    dateFormat?: SettingsDateFormat;
  }
): string {
  const parts = dateParts(date, { locale, timezone });
  const year = parts.year || "";
  const month = parts.month || "";
  const day = parts.day || "";
  if (dateFormat === "DD.MM.YYYY") return `${day}.${month}.${year}`;
  if (dateFormat === "DD/MM/YYYY") return `${day}/${month}/${year}`;
  if (dateFormat === "MM/DD/YYYY") return `${month}/${day}/${year}`;
  return `${year}-${month}-${day}`;
}

export function formatDateTime(
  value: unknown,
  {
    locale,
    timezone,
    dateFormat,
    timeFormat,
  }: {
    locale: string;
    timezone?: SettingsTimezone | string;
    dateFormat?: SettingsDateFormat;
    timeFormat?: SettingsTimeFormat;
  }
): string {
  if (value == null || value === "") return "—";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  const time = new Intl.DateTimeFormat(localeTag(locale), {
    ...timeOptionsFromFormat(timeFormat),
    timeZone: timezone || undefined,
  }).format(date);
  return `${formatDateByPreference(date, { locale, timezone, dateFormat })} ${time}`;
}

export function formatDateOnly(
  value: unknown,
  {
    locale,
    timezone,
    dateFormat,
    dateStyle,
  }: {
    locale: string;
    timezone?: SettingsTimezone | string;
    dateFormat?: SettingsDateFormat;
    dateStyle?: Intl.DateTimeFormatOptions["dateStyle"];
  }
): string {
  if (value == null || value === "") return "—";
  const raw = String(value);
  const date = /^\d{4}-\d{2}-\d{2}$/.test(raw) ? new Date(`${raw}T12:00:00Z`) : new Date(raw);
  if (Number.isNaN(date.getTime())) return String(value);
  if (!dateStyle) return formatDateByPreference(date, { locale, timezone, dateFormat });
  return new Intl.DateTimeFormat(localeTag(locale), {
    dateStyle,
    timeZone: timezone || undefined,
  }).format(date);
}
