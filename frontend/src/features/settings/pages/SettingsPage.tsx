// frontend/src/features/settings/pages/SettingsPage.tsx
// Feladat: A settings oldal belépési pontja; csak jogosultság ellenőrzést és shell renderelést végez.
// Sárközi Mihály - 2026.05.29

import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { canAccessSettings } from "../model/settingsPermissions";
import SettingsAccessDenied from "../shell/SettingsAccessDenied";
import SettingsShell from "../shell/SettingsShell";

export default function SettingsPage() {
  const { t } = useTranslation();
  const { user } = useAuthStore();

  if (!canAccessSettings(user)) return <SettingsAccessDenied message={t("settings.ownerOnly")} />;
  return <SettingsShell user={user} />;
}
