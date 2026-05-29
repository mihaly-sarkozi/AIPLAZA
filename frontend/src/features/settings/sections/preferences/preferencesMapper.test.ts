// frontend/src/features/settings/sections/preferences/preferencesMapper.test.ts
// Feladat: Preferences mapper tesztek response->form és form->payload irányokra.
// Sárközi Mihály - 2026.05.29

import { describe, expect, it } from "vitest";
import { mapLocaleResponseToPreferencesForm, mapPreferencesFormToLocalePayload } from "./preferencesMapper";

describe("preferencesMapper", () => {
  it("maps locale API response to form", () => {
    const form = mapLocaleResponseToPreferencesForm({
      timezone: "Europe/Budapest",
      date_format: "DD.MM.YYYY",
      time_format: "HH:mm:ss",
    });
    expect(form).toEqual({
      timezone: "Europe/Budapest",
      dateFormat: "DD.MM.YYYY",
      timeFormat: "HH:mm:ss",
    });
  });

  it("maps form to locale payload", () => {
    const payload = mapPreferencesFormToLocalePayload({
      timezone: "UTC",
      dateFormat: "YYYY-MM-DD",
      timeFormat: "HH:mm",
    });
    expect(payload).toEqual({
      timezone: "UTC",
      date_format: "YYYY-MM-DD",
      time_format: "HH:mm",
    });
  });
});
