// frontend/src/features/settings/sections/preferences/PreferencesSettingsSection.tsx
// Feladat: Preferences UI-only szekció komponens API hívás nélkül.
// Sárközi Mihály - 2026.05.29

import SettingsBlock from "../../components/SettingsBlock";
import { DATE_FORMAT_OPTIONS, TIMEZONE_OPTIONS, TIME_FORMAT_OPTIONS } from "../../components/settingsOptions";
import type { PreferencesFormState } from "./preferencesTypes";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../api/settingsService";

type PreferencesSettingsSectionProps = {
  title: string;
  description: string;
  timezoneLabel: string;
  dateFormatLabel: string;
  timeFormatLabel: string;
  disabled: boolean;
  form: PreferencesFormState;
  onTimezoneChange: (value: SettingsTimezone) => void;
  onDateFormatChange: (value: SettingsDateFormat) => void;
  onTimeFormatChange: (value: SettingsTimeFormat) => void;
};

export default function PreferencesSettingsSection({
  title,
  description,
  timezoneLabel,
  dateFormatLabel,
  timeFormatLabel,
  disabled,
  form,
  onTimezoneChange,
  onDateFormatChange,
  onTimeFormatChange,
}: PreferencesSettingsSectionProps) {
  return (
    <SettingsBlock title={title} description={description}>
      <div className="grid gap-4 md:grid-cols-3">
        <label className="block text-sm text-[var(--color-label)]">
          {timezoneLabel}
          <select
            value={form.timezone}
            onChange={(event) => onTimezoneChange(event.target.value as SettingsTimezone)}
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
            value={form.dateFormat}
            onChange={(event) => onDateFormatChange(event.target.value as SettingsDateFormat)}
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
            value={form.timeFormat}
            onChange={(event) => onTimeFormatChange(event.target.value as SettingsTimeFormat)}
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
