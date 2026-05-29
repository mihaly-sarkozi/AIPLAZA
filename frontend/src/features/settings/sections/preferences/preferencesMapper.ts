// frontend/src/features/settings/sections/preferences/preferencesMapper.ts
// Feladat: Preferences API payload és UI form state közötti leképzések.
// Sárközi Mihály - 2026.05.29

import type { LocaleSettingsResponse, PatchLocaleSettingsPayload } from "../../api/settingsService";
import type { PreferencesFormState } from "./preferencesTypes";

export function mapLocaleResponseToPreferencesForm(response: LocaleSettingsResponse): PreferencesFormState {
  return {
    timezone: response.timezone,
    dateFormat: response.date_format,
    timeFormat: response.time_format,
  };
}

export function mapPreferencesFormToLocalePayload(form: PreferencesFormState): PatchLocaleSettingsPayload {
  return {
    timezone: form.timezone,
    date_format: form.dateFormat,
    time_format: form.timeFormat,
  };
}
