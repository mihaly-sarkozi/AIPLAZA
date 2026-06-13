// frontend/src/features/settings/model/settingsSections.ts
// Feladat: A settings szekciók kulcsainak és tab-listájának központi modellje.
// Sárközi Mihály - 2026.05.29

export type SettingsSectionKey = "security" | "preferences" | "billing" | "domains" | "reset";

export type SettingsSectionTab = {
  key: SettingsSectionKey;
  label: string;
};

export function buildSettingsSections(
  t: (key: string) => string,
  includeBusinessSections: boolean,
  includeResetSection: boolean
): SettingsSectionTab[] {
  return [
    { key: "security", label: t("settings.sectionSecurity") },
    { key: "preferences", label: t("settings.sectionPreferences") },
    ...(includeBusinessSections
      ? [
          { key: "billing" as const, label: t("settings.sectionBilling") },
          { key: "domains" as const, label: t("settings.sectionDomains") },
        ]
      : []),
    ...(includeResetSection ? [{ key: "reset" as const, label: t("settings.sectionReset") }] : []),
  ];
}
