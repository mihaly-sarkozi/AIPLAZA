// frontend/src/features/settings/shell/SettingsShell.tsx
// Feladat: A settings oldal shell komponense tab state-tel és section container rendereléssel.
// Sárközi Mihály - 2026.05.29

import { useMemo, useState } from "react";
import { useTranslation } from "../../../i18n";
import type { User } from "../../../store/authStore";
import { canManageBillingAndDomains, canResetTenant } from "../model/settingsPermissions";
import { buildSettingsSections, type SettingsSectionKey } from "../model/settingsSections";
import BillingSettingsContainer from "../sections/billing/BillingSettingsContainer";
import DomainsSettingsContainer from "../sections/domains/DomainsSettingsContainer";
import PreferencesSettingsContainer from "../sections/preferences/PreferencesSettingsContainer";
import ResetSettingsContainer from "../sections/reset/ResetSettingsContainer";
import SecuritySettingsContainer from "../sections/security/SecuritySettingsContainer";
import SettingsHeader from "./SettingsHeader";
import SettingsSectionTabs from "./SettingsSectionTabs";

type SettingsShellProps = {
  user: User;
};

export default function SettingsShell({ user }: SettingsShellProps) {
  const { t } = useTranslation();
  const showBusinessSections = canManageBillingAndDomains(user);
  const showResetSection = canResetTenant(user);
  const sections = useMemo(
    () => buildSettingsSections(t, showBusinessSections, showResetSection),
    [showBusinessSections, showResetSection, t]
  );
  const [activeSection, setActiveSection] = useState<SettingsSectionKey>("security");

  return (
    <div className="app-page">
      <div className="mx-auto w-full max-w-6xl space-y-8">
        <SettingsHeader eyebrow={t("settings.systemLabel")} title={t("nav.settings")} description={t("settings.pageIntro")} />
        <SettingsSectionTabs sections={sections} activeSection={activeSection} onChange={setActiveSection} />
        {activeSection === "security" ? <SecuritySettingsContainer /> : null}
        {activeSection === "preferences" ? <PreferencesSettingsContainer /> : null}
        {activeSection === "billing" && showBusinessSections ? <BillingSettingsContainer /> : null}
        {activeSection === "domains" && showBusinessSections ? <DomainsSettingsContainer /> : null}
        {activeSection === "reset" && showResetSection ? <ResetSettingsContainer /> : null}
      </div>
    </div>
  );
}
