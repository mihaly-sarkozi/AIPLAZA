// frontend/src/features/settings/components/settingsOptions.ts
// Feladat: Settings locale/date/time opciólisták központi konstansai.
// Sárközi Mihály - 2026.05.29

import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../api/services/settingsService";

export const TIMEZONE_OPTIONS: { value: SettingsTimezone; label: string }[] = [
  { value: "UTC", label: "UTC" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "Europe/Paris", label: "Europe/Paris" },
  { value: "Europe/Berlin", label: "Europe/Berlin" },
  { value: "Europe/Madrid", label: "Europe/Madrid" },
  { value: "Europe/Rome", label: "Europe/Rome" },
  { value: "Europe/Amsterdam", label: "Europe/Amsterdam" },
  { value: "Europe/Zurich", label: "Europe/Zurich" },
  { value: "Europe/Vienna", label: "Europe/Vienna" },
  { value: "Europe/Prague", label: "Europe/Prague" },
  { value: "Europe/Warsaw", label: "Europe/Warsaw" },
  { value: "Europe/Budapest", label: "Europe/Budapest" },
  { value: "Europe/Athens", label: "Europe/Athens" },
  { value: "Europe/Bucharest", label: "Europe/Bucharest" },
  { value: "Europe/Istanbul", label: "Europe/Istanbul" },
  { value: "Asia/Dubai", label: "Asia/Dubai" },
  { value: "Asia/Kolkata", label: "Asia/Kolkata" },
  { value: "Asia/Singapore", label: "Asia/Singapore" },
  { value: "Asia/Hong_Kong", label: "Asia/Hong_Kong" },
  { value: "Asia/Shanghai", label: "Asia/Shanghai" },
  { value: "Asia/Seoul", label: "Asia/Seoul" },
  { value: "America/New_York", label: "America/New_York" },
  { value: "America/Toronto", label: "America/Toronto" },
  { value: "America/Chicago", label: "America/Chicago" },
  { value: "America/Denver", label: "America/Denver" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles" },
  { value: "America/Mexico_City", label: "America/Mexico_City" },
  { value: "America/Sao_Paulo", label: "America/Sao_Paulo" },
  { value: "Africa/Cairo", label: "Africa/Cairo" },
  { value: "Africa/Johannesburg", label: "Africa/Johannesburg" },
  { value: "Australia/Sydney", label: "Australia/Sydney" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo" },
];

export const DATE_FORMAT_OPTIONS: { value: SettingsDateFormat; label: string }[] = [
  { value: "YYYY-MM-DD", label: "2026-04-19" },
  { value: "DD.MM.YYYY", label: "19.04.2026" },
  { value: "DD/MM/YYYY", label: "19/04/2026" },
  { value: "MM/DD/YYYY", label: "04/19/2026" },
];

export const TIME_FORMAT_OPTIONS: { value: SettingsTimeFormat; label: string }[] = [
  { value: "HH:mm", label: "17:45" },
  { value: "HH:mm:ss", label: "17:45:30" },
  { value: "hh:mm A", label: "05:45 PM" },
];
