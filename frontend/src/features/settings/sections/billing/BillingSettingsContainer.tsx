// frontend/src/features/settings/sections/billing/BillingSettingsContainer.tsx
// Feladat: Billing settings container, amely a form hookot és UI komponenst összeköti.
// Sárközi Mihály - 2026.05.29

import { toast } from "sonner";
import Alert from "../../../../components/ui/Alert";
import { useTranslation } from "../../../../i18n";
import { getApiErrorMessage } from "../../../../utils/getApiErrorMessage";
import SettingsSaveBar from "../../shell/SettingsSaveBar";
import BillingSettingsSection from "./BillingSettingsSection";
import { useBillingForm } from "./useBillingForm";

export default function BillingSettingsContainer() {
  const { t, locale } = useTranslation();
  const { form, errors, loading, saving, error, isDirty, updateField, save, reset } = useBillingForm(t);

  if (loading) return <div>{t("common.loading")}</div>;
  return (
    <div className="space-y-4">
      {error ? <Alert tone="error">{getApiErrorMessage(error) ?? t("settings.errorLoad")}</Alert> : null}
      <BillingSettingsSection
        title={t("settings.billingCompanyTitle")}
        disabled={saving}
        locale={locale}
        t={t}
        form={form}
        errors={errors}
        onFieldChange={updateField}
      />
      <SettingsSaveBar
        cancelLabel={t("common.cancel")}
        saveLabel={t("common.save")}
        loadingLabel={t("common.loading")}
        disabled={saving || !isDirty}
        onCancel={reset}
        onSave={() =>
          save()
            .then((result) => {
              if (result.ok) toast.success(t("profile.saved"));
            })
            .catch(() => undefined)
        }
      />
    </div>
  );
}
