// frontend/src/features/settings/sections/preferences/preferencesTypes.ts
// Feladat: Preferences settings form állapotának és hibáinak típusai.
// Sárközi Mihály - 2026.05.29

import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../api/settingsService";

export type PreferencesFormState = {
  timezone: SettingsTimezone;
  dateFormat: SettingsDateFormat;
  timeFormat: SettingsTimeFormat;
};
