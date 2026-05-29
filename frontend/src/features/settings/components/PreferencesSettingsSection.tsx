// frontend/src/features/settings/components/PreferencesSettingsSection.tsx
// Feladat: Legacy preferences settings UI komponens (section-only, API nélkül).
// Sárközi Mihály - 2026.05.29

import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../api/services/settingsService";
import SettingsBlock from "./SettingsBlock";
import { DATE_FORMAT_OPTIONS, TIMEZONE_OPTIONS, TIME_FORMAT_OPTIONS } from "./settingsOptions";

type PreferencesSettingsSectionProps = {
  title: string;
  description: string;
  timezoneLabel: string;
  dateFormatLabel: string;
  timeFormatLabel: string;
  timezone: SettingsTimezone;
  dateFormat: SettingsDateFormat;
  timeFormat: SettingsTimeFormat;
  disabled: boolean;
  setTimezone: (value: SettingsTimezone) => void;
  setDateFormat: (value: SettingsDateFormat) => void;
  setTimeFormat: (value: SettingsTimeFormat) => void;
};

export default function PreferencesSettingsSection({
  title,
  description,
  timezoneLabel,
  dateFormatLabel,
  timeFormatLabel,
  timezone,
  dateFormat,
  timeFormat,
  disabled,
  setTimezone,
  setDateFormat,
  setTimeFormat,
}: PreferencesSettingsSectionProps) {
  return (
    <SettingsBlock title={title} description={description}>
      <div className="grid gap-4 md:grid-cols-3">
        <label className="block text-sm text-[var(--color-label)]">
          {timezoneLabel}
          <select
            value={timezone}
            onChange={(event) => setTimezone(event.target.value as SettingsTimezone)}
            className="mt-1 w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
            disabled={disabled}
          >
            {TIMEZONE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm text-[var(--color-label)]">
          {dateFormatLabel}
          <select
            value={dateFormat}
            onChange={(event) => setDateFormat(event.target.value as SettingsDateFormat)}
            className="mt-1 w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
            disabled={disabled}
          >
            {DATE_FORMAT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm text-[var(--color-label)]">
          {timeFormatLabel}
          <select
            value={timeFormat}
            onChange={(event) => setTimeFormat(event.target.value as SettingsTimeFormat)}
            className="mt-1 w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
            disabled={disabled}
          >
            {TIME_FORMAT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
    </SettingsBlock>
  );
}
