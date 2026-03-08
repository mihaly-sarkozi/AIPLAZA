import { useTranslation } from "../../i18n";
import { useAuthStore } from "../../store/authStore";
import { useSettings, usePatchSettingsMutation } from "../../hooks/useApi";

export default function SettingsPage() {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const { data: settings, isLoading: loading, error: settingsError } = useSettings();
  const patchMutation = usePatchSettingsMutation();
  const twoFactorEnabled = settings?.two_factor_enabled ?? true;
  const settingsErrMsg =
    settingsError && typeof (settingsError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (settingsError as { response?: { data?: { detail?: string } } }).response!.data!.detail
      : settingsError
        ? t("settings.errorLoad")
        : null;
  const patchErrMsg = patchMutation.error
    ? (typeof (patchMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
        ? (patchMutation.error as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : t("common.errorGeneric"))
    : null;
  const displayError = patchErrMsg ?? settingsErrMsg;

  const handleTwoFactorToggle = () => {
    if (patchMutation.isPending) return;
    patchMutation.mutate({ two_factor_enabled: !twoFactorEnabled });
  };

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)]">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
      <h1 className="text-3xl font-bold mb-6">{t("settings.title")}</h1>

      {displayError && (
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded mb-4">
          {displayError}
        </div>
      )}

      {loading ? (
        <div>{t("common.loading")}</div>
      ) : (
        <div className="w-full bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-6">
          <section className="w-full">
            <h2 className="text-2xl font-bold mb-4">{t("settings.securityTitle")}</h2>
            <div className="w-full flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-4 bg-[var(--color-table-head)] rounded-lg border border-[var(--color-border)]">
              <div className="min-w-0">
                <h3 className="font-semibold text-lg">{t("settings.twoFactorTitle")}</h3>
                <p className="text-[var(--color-foreground)] opacity-80 text-sm mt-1">
                  {twoFactorEnabled ? t("settings.twoFactorDesc") : t("settings.twoFactorDescOff")}
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-sm opacity-80 font-medium">
                  {twoFactorEnabled ? t("settings.twoFactorOn") : t("settings.twoFactorOff")}
                </span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={twoFactorEnabled}
                  disabled={patchMutation.isPending}
                  onClick={handleTwoFactorToggle}
                  className={`relative inline-flex h-6 w-11 shrink-0 rounded-full border border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[var(--color-primary)] disabled:opacity-50 ${
                    twoFactorEnabled ? "bg-[var(--color-primary)]" : "bg-[var(--color-border)]"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition duration-200 ${
                      twoFactorEnabled ? "translate-x-5" : "translate-x-0.5"
                    }`}
                  />
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
