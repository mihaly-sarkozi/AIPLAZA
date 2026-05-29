// frontend/src/features/settings/sections/preferences/PreferencesSettingsContainer.tsx
// Feladat: Preferences settings container, amely a hook állapotát UI propsokra fordítja.
// Sárközi Mihály - 2026.05.29

import { toast } from "sonner";
import Alert from "../../../../components/ui/Alert";
import { useTranslation } from "../../../../i18n";
import { getApiErrorMessage } from "../../../../utils/getApiErrorMessage";
import SettingsSaveBar from "../../shell/SettingsSaveBar";
import PreferencesSettingsSection from "./PreferencesSettingsSection";
import { usePreferencesForm } from "./usePreferencesForm";

export default function PreferencesSettingsContainer() {
  const { t } = useTranslation();
  const { form, setForm, loading, saving, error, save, reset, isDirty } = usePreferencesForm();

  if (loading) return <div>{t("common.loading")}</div>;
  return (
    <div className="space-y-4">
      {error ? <Alert tone="error">{getApiErrorMessage(error) ?? t("settings.errorLoad")}</Alert> : null}
      <PreferencesSettingsSection
        title={t("settings.preferencesTitle")}
        description={t("settings.preferencesIntro")}
        timezoneLabel={t("settings.timezoneLabel")}
        dateFormatLabel={t("settings.dateFormatLabel")}
        timeFormatLabel={t("settings.timeFormatLabel")}
        disabled={saving}
        form={form}
        onTimezoneChange={(value) => setForm((prev) => ({ ...prev, timezone: value }))}
        onDateFormatChange={(value) => setForm((prev) => ({ ...prev, dateFormat: value }))}
        onTimeFormatChange={(value) => setForm((prev) => ({ ...prev, timeFormat: value }))}
      />
      <SettingsSaveBar
        cancelLabel={t("common.cancel")}
        saveLabel={t("common.save")}
        loadingLabel={t("common.loading")}
        disabled={saving || !isDirty}
        onCancel={reset}
        onSave={() =>
          save()
            .then(() => toast.success(t("profile.saved")))
            .catch(() => undefined)
        }
      />
    </div>
  );
}
