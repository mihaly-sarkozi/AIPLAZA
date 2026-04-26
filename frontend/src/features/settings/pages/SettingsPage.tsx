import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useSettings, usePatchSettingsMutation } from "../hooks/useSettings";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import type {
  SettingsDateFormat,
  SettingsTimeFormat,
  SettingsTimezone,
} from "../../../api/services/settingsService";

const TIMEZONE_OPTIONS: { value: SettingsTimezone; label: string }[] = [
  { value: "UTC", label: "UTC" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "Europe/Paris", label: "Europe/Paris" },
  { value: "Europe/Berlin", label: "Europe/Berlin" },
  { value: "Europe/Madrid", label: "Europe/Madrid" },
  { value: "Europe/Rome", label: "Europe/Rome" },
  { value: "Europe/Amsterdam", label: "Europe/Amsterdam" },
  { value: "Europe/Zurich", label: "Europe/Zurich" },
  { value: "Europe/Vienna", label: "Europe/Vienna" },
  { value: "Europe/Prague", label: "Europe/Prague" },
  { value: "Europe/Warsaw", label: "Europe/Warsaw" },
  { value: "Europe/Budapest", label: "Europe/Budapest" },
  { value: "Europe/Athens", label: "Europe/Athens" },
  { value: "Europe/Bucharest", label: "Europe/Bucharest" },
  { value: "Europe/Istanbul", label: "Europe/Istanbul" },
  { value: "Asia/Dubai", label: "Asia/Dubai" },
  { value: "Asia/Kolkata", label: "Asia/Kolkata" },
  { value: "Asia/Singapore", label: "Asia/Singapore" },
  { value: "Asia/Hong_Kong", label: "Asia/Hong_Kong" },
  { value: "Asia/Shanghai", label: "Asia/Shanghai" },
  { value: "Asia/Seoul", label: "Asia/Seoul" },
  { value: "America/New_York", label: "America/New_York" },
  { value: "America/Toronto", label: "America/Toronto" },
  { value: "America/Chicago", label: "America/Chicago" },
  { value: "America/Denver", label: "America/Denver" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles" },
  { value: "America/Mexico_City", label: "America/Mexico_City" },
  { value: "America/Sao_Paulo", label: "America/Sao_Paulo" },
  { value: "Africa/Cairo", label: "Africa/Cairo" },
  { value: "Africa/Johannesburg", label: "Africa/Johannesburg" },
  { value: "Australia/Sydney", label: "Australia/Sydney" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo" },
];

const DATE_FORMAT_OPTIONS: { value: SettingsDateFormat; label: string }[] = [
  { value: "YYYY-MM-DD", label: "2026-04-19" },
  { value: "DD.MM.YYYY", label: "19.04.2026" },
  { value: "DD/MM/YYYY", label: "19/04/2026" },
  { value: "MM/DD/YYYY", label: "04/19/2026" },
];

const TIME_FORMAT_OPTIONS: { value: SettingsTimeFormat; label: string }[] = [
  { value: "HH:mm", label: "17:45" },
  { value: "HH:mm:ss", label: "17:45:30" },
  { value: "hh:mm A", label: "05:45 PM" },
];

interface SystemSecurityBodyProps {
  onSaved?: () => void;
  onCancel?: () => void;
}

export function SystemSecurityBody({ onSaved, onCancel }: SystemSecurityBodyProps) {
  const { t } = useTranslation();
  const { data: settings, isLoading: loading, error: settingsError } = useSettings();
  const patchMutation = usePatchSettingsMutation();
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [timezone, setTimezone] = useState<SettingsTimezone>("UTC");
  const [dateFormat, setDateFormat] = useState<SettingsDateFormat>("YYYY-MM-DD");
  const [timeFormat, setTimeFormat] = useState<SettingsTimeFormat>("HH:mm");

  const settingsErrMsg =
    settingsError && typeof (settingsError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (settingsError as { response?: { data?: { detail?: string } } }).response!.data!.detail
      : settingsError
        ? t("settings.errorLoad")
        : null;
  const patchErrMsg = patchMutation.error
    ? typeof (patchMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (patchMutation.error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      : t("common.errorGeneric")
    : null;
  const displayError = patchErrMsg ?? settingsErrMsg;

  useEffect(() => {
    if (!settings) return;
    setTwoFactorEnabled(settings.two_factor_enabled);
    setTimezone(settings.timezone);
    setDateFormat(settings.date_format);
    setTimeFormat(settings.time_format);
  }, [settings]);

  const resetForm = () => {
    if (!settings) return;
    setTwoFactorEnabled(settings.two_factor_enabled);
    setTimezone(settings.timezone);
    setDateFormat(settings.date_format);
    setTimeFormat(settings.time_format);
  };

  const handleSave = () => {
    if (patchMutation.isPending) return;
    patchMutation.mutate(
      {
        two_factor_enabled: twoFactorEnabled,
        timezone,
        date_format: dateFormat,
        time_format: timeFormat,
      },
      {
        onSuccess: () => {
          toast.success(t("profile.saved"));
          onSaved?.();
        },
      }
    );
  };

  const handleCancel = () => {
    if (patchMutation.isPending) return;
    resetForm();
    onCancel?.();
  };

  if (loading) {
    return <div>{t("common.loading")}</div>;
  }

  return (
    <>
      {displayError && (
        <Alert tone="error">{displayError}</Alert>
      )}
      <section className="w-full max-w-md">
        <div className="space-y-4">
          <div>
            <label className="block mb-1 text-[var(--color-label)]">{t("settings.twoFactorTitle")}</label>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setTwoFactorEnabled(true)}
                disabled={patchMutation.isPending}
                className={`px-4 py-2 rounded text-sm border ${
                  twoFactorEnabled
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)] hover:opacity-90"
                    : "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-button-hover)]"
                } disabled:opacity-60`}
              >
                {t("settings.twoFactorOn")}
              </button>
              <button
                type="button"
                onClick={() => setTwoFactorEnabled(false)}
                disabled={patchMutation.isPending}
                className={`px-4 py-2 rounded text-sm border ${
                  !twoFactorEnabled
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)] hover:opacity-90"
                    : "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-button-hover)]"
                } disabled:opacity-60`}
              >
                {t("settings.twoFactorOff")}
              </button>
            </div>
          </div>

          <div>
            <label className="block mb-1 text-[var(--color-label)]">{t("settings.timezoneLabel")}</label>
            <select
              value={timezone}
              onChange={(e) => setTimezone(e.target.value as SettingsTimezone)}
              className="w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
              disabled={patchMutation.isPending}
            >
              {TIMEZONE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block mb-1 text-[var(--color-label)]">{t("settings.dateFormatLabel")}</label>
            <select
              value={dateFormat}
              onChange={(e) => setDateFormat(e.target.value as SettingsDateFormat)}
              className="w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
              disabled={patchMutation.isPending}
            >
              {DATE_FORMAT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block mb-1 text-[var(--color-label)]">{t("settings.timeFormatLabel")}</label>
            <select
              value={timeFormat}
              onChange={(e) => setTimeFormat(e.target.value as SettingsTimeFormat)}
              className="w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
              disabled={patchMutation.isPending}
            >
              {TIME_FORMAT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="secondary" onClick={handleCancel} disabled={patchMutation.isPending}>
              {t("common.cancel")}
            </Button>
            <Button type="button" onClick={handleSave} disabled={patchMutation.isPending}>
              {patchMutation.isPending ? t("common.loading") : t("common.save")}
            </Button>
          </div>
        </div>
      </section>
    </>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const rawSection = searchParams.get("section");

  useEffect(() => {
    if (!user || user.role !== "owner") return;
    if (rawSection === "packages") {
      navigate("/admin/csomagok", { replace: true });
      return;
    }
    if (rawSection === "billing") {
      navigate("/admin/szamlak", { replace: true });
      return;
    }
    if (rawSection != null && rawSection !== "" && rawSection !== "system") {
      navigate("/admin/settings?section=system", { replace: true });
    }
  }, [user, rawSection, navigate]);

  useEffect(() => {
    if (!user || user.role !== "owner") return;
    if (rawSection == null || rawSection === "") {
      navigate("/admin/settings?section=system", { replace: true });
    }
  }, [user, rawSection, navigate]);

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)]">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (rawSection === "packages" || rawSection === "billing") {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  if (rawSection !== "system" && rawSection != null && rawSection !== "") {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  return (
    <div className="app-page">
      <div className="mx-auto max-w-md space-y-8">
        <PageHeader
          eyebrow={t("settings.systemLabel")}
          title={t("settings.title")}
          description={t("settings.pageIntro")}
        />
        <SystemSecurityBody />
      </div>
    </div>
  );
}
