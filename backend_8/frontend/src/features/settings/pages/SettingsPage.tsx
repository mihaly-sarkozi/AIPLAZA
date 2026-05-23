import { useEffect, useMemo, useState, type ReactNode } from "react";
import { QRCodeSVG } from "qrcode.react";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useSettings, usePatchSettingsMutation } from "../hooks/useSettings";
import {
  useAuthenticatorStatus,
  useConfirmAuthenticatorSetupMutation,
  useDisableAuthenticatorMutation,
  useStartAuthenticatorSetupMutation,
} from "../hooks/useAuthenticator";
import {
  useAddCustomDomainMutation,
  useDeleteCustomDomainMutation,
  useDomainOverview,
  useVerifyCustomDomainMutation,
} from "../hooks/useDomainSettings";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";
import PageHeader from "../../../components/ui/PageHeader";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import type {
  SettingsDateFormat,
  SettingsTimeFormat,
  SettingsTimezone,
} from "../../../api/services/settingsService";
import type { DomainRecordResponse } from "../../../api/services/domainService";
import type { AuthenticatorSetupResponse } from "../../../api/services/authenticatorService";

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

function SettingsBlock({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-sm">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-[var(--color-foreground)]">{title}</h2>
        {description ? <p className="mt-1 text-sm text-[var(--color-muted)]">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function SystemSecurityBody({ onSaved, onCancel }: SystemSecurityBodyProps) {
  const { t } = useTranslation();
  type SettingsSectionKey = "security" | "preferences" | "billing" | "domains";
  const { data: settings, isLoading: loading, error: settingsError } = useSettings();
  const domainQuery = useDomainOverview();
  const patchMutation = usePatchSettingsMutation();
  const addDomainMutation = useAddCustomDomainMutation();
  const verifyDomainMutation = useVerifyCustomDomainMutation();
  const deleteDomainMutation = useDeleteCustomDomainMutation();
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [timezone, setTimezone] = useState<SettingsTimezone>("UTC");
  const [dateFormat, setDateFormat] = useState<SettingsDateFormat>("YYYY-MM-DD");
  const [timeFormat, setTimeFormat] = useState<SettingsTimeFormat>("HH:mm");
  const [billingCompanyName, setBillingCompanyName] = useState("");
  const [billingTaxId, setBillingTaxId] = useState("");
  const [billingAddressLine, setBillingAddressLine] = useState("");
  const [billingPostalCode, setBillingPostalCode] = useState("");
  const [billingCity, setBillingCity] = useState("");
  const [billingRegion, setBillingRegion] = useState("");
  const [billingCountry, setBillingCountry] = useState("");
  const [customDomainInput, setCustomDomainInput] = useState("");
  const [activeSection, setActiveSection] = useState<SettingsSectionKey>("security");
  const [authenticatorSetupData, setAuthenticatorSetupData] = useState<AuthenticatorSetupResponse | null>(null);
  const [authenticatorCode, setAuthenticatorCode] = useState("");
  const [authenticatorWizardOpen, setAuthenticatorWizardOpen] = useState(false);
  const [authenticatorWizardStep, setAuthenticatorWizardStep] = useState<1 | 2 | 3>(1);
  const authenticatorStatusQuery = useAuthenticatorStatus();
  const startAuthenticatorSetupMutation = useStartAuthenticatorSetupMutation();
  const confirmAuthenticatorSetupMutation = useConfirmAuthenticatorSetupMutation();
  const disableAuthenticatorMutation = useDisableAuthenticatorMutation();

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
  const customDomains = domainQuery.data?.custom_domains ?? [];
  const primaryDomain = domainQuery.data?.primary_domain?.domain ?? "-";
  const showActiveCustomHost =
    Boolean(domainQuery.data?.active_custom_domain) &&
    Boolean(domainQuery.data?.active_host) &&
    domainQuery.data?.active_host !== primaryDomain;
  const settingsSections: Array<{ key: SettingsSectionKey; label: string }> = useMemo(
    () => [
      { key: "security", label: t("settings.sectionSecurity") },
      { key: "preferences", label: t("settings.sectionPreferences") },
      { key: "billing", label: t("settings.sectionBilling") },
      { key: "domains", label: t("settings.sectionDomains") },
    ],
    [t]
  );

  const getDomainStateLabel = (state: DomainRecordResponse["state"]): string => {
    if (state === "platform_primary") return t("settings.domainStatePlatformPrimary");
    if (state === "custom_verified") return t("settings.domainStateCustomVerified");
    return t("settings.domainStateCustomPending");
  };

  useEffect(() => {
    if (!settings) return;
    setTwoFactorEnabled(settings.two_factor_enabled);
    setTimezone(settings.timezone);
    setDateFormat(settings.date_format);
    setTimeFormat(settings.time_format);
    setBillingCompanyName(settings.billing_company_name ?? "");
    setBillingTaxId(settings.billing_tax_id ?? "");
    setBillingAddressLine(settings.billing_address_line ?? "");
    setBillingPostalCode(settings.billing_postal_code ?? "");
    setBillingCity(settings.billing_city ?? "");
    setBillingRegion(settings.billing_region ?? "");
    setBillingCountry(settings.billing_country ?? "");
  }, [settings]);

  const resetForm = () => {
    if (!settings) return;
    setTwoFactorEnabled(settings.two_factor_enabled);
    setTimezone(settings.timezone);
    setDateFormat(settings.date_format);
    setTimeFormat(settings.time_format);
    setBillingCompanyName(settings.billing_company_name ?? "");
    setBillingTaxId(settings.billing_tax_id ?? "");
    setBillingAddressLine(settings.billing_address_line ?? "");
    setBillingPostalCode(settings.billing_postal_code ?? "");
    setBillingCity(settings.billing_city ?? "");
    setBillingRegion(settings.billing_region ?? "");
    setBillingCountry(settings.billing_country ?? "");
  };

  const handleSave = () => {
    if (patchMutation.isPending) return;
    patchMutation.mutate(
      {
        two_factor_enabled: twoFactorEnabled,
        timezone,
        date_format: dateFormat,
        time_format: timeFormat,
        billing_company_name: billingCompanyName,
        billing_tax_id: billingTaxId,
        billing_address_line: billingAddressLine,
        billing_postal_code: billingPostalCode,
        billing_city: billingCity,
        billing_region: billingRegion,
        billing_country: billingCountry,
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

  const handleAddCustomDomain = () => {
    const normalizedDomain = customDomainInput.trim().toLowerCase();
    if (!normalizedDomain) return;
    addDomainMutation.mutate(normalizedDomain, {
      onSuccess: () => {
        toast.success(t("settings.domainCreateSuccess"));
        setCustomDomainInput("");
      },
      onError: (error) => {
        toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric"));
      },
    });
  };

  const handleVerifyCustomDomain = (domain: string) => {
    verifyDomainMutation.mutate(domain, {
      onSuccess: () => {
        toast.success(t("settings.domainVerifySuccess"));
      },
      onError: (error) => {
        toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric"));
      },
    });
  };

  const handleDeleteCustomDomain = (domain: string) => {
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(t("settings.domainDeleteConfirm"));
      if (!confirmed) return;
    }
    deleteDomainMutation.mutate(domain, {
      onSuccess: () => {
        toast.success(t("settings.domainDeleteSuccess"));
      },
      onError: (error) => {
        toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric"));
      },
    });
  };

  const copyText = async (value: string) => {
    const text = value.trim();
    if (!text) return;
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else if (typeof document !== "undefined") {
        const el = document.createElement("textarea");
        el.value = text;
        el.style.position = "fixed";
        el.style.opacity = "0";
        document.body.appendChild(el);
        el.focus();
        el.select();
        document.execCommand("copy");
        document.body.removeChild(el);
      }
      toast.success(t("settings.domainCopySuccess"));
    } catch {
      toast.error(t("common.errorGeneric"));
    }
  };

  const authenticatorStatus = authenticatorStatusQuery.data;
  const authenticatorEnabled = !!authenticatorStatus?.enabled;
  const authenticatorPending = !!authenticatorStatus?.pending;
  const authenticatorSetupReady = !authenticatorEnabled && authenticatorWizardOpen && !!authenticatorSetupData;
  const googleAuthenticatorAndroidUrl =
    "https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2";
  const googleAuthenticatorIosUrl = "https://apps.apple.com/app/google-authenticator/id388497605";

  const handleStartAuthenticatorSetup = () => {
    startAuthenticatorSetupMutation.mutate(undefined, {
      onSuccess: (data) => {
        setAuthenticatorSetupData(data);
        setAuthenticatorCode("");
        setAuthenticatorWizardStep(1);
        setAuthenticatorWizardOpen(true);
        toast.success("Authenticator setup elindítva.");
      },
      onError: (error) => {
        toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric"));
      },
    });
  };

  const handleConfirmAuthenticatorSetup = () => {
    const code = authenticatorCode.trim();
    if (code.length !== 6) {
      toast.error("Adj meg egy 6 jegyű Google Authenticator kódot.");
      return;
    }
    confirmAuthenticatorSetupMutation.mutate(code, {
      onSuccess: () => {
        setAuthenticatorSetupData(null);
        setAuthenticatorCode("");
        setAuthenticatorWizardStep(1);
        setAuthenticatorWizardOpen(false);
        toast.success("Google Authenticator sikeresen bekapcsolva.");
      },
      onError: (error) => {
        toast.error(getApiErrorMessage(error) ?? "Érvénytelen authenticator kód.");
      },
    });
  };

  const handleDisableAuthenticator = () => {
    if (typeof window !== "undefined" && !window.confirm("Biztosan kikapcsolod a Google Authenticator védelmet?")) {
      return;
    }
    disableAuthenticatorMutation.mutate(undefined, {
      onSuccess: () => {
        setAuthenticatorSetupData(null);
        setAuthenticatorCode("");
        setAuthenticatorWizardStep(1);
        setAuthenticatorWizardOpen(false);
        toast.success("Google Authenticator kikapcsolva.");
      },
      onError: (error) => {
        toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric"));
      },
    });
  };

  if (loading) {
    return <div>{t("common.loading")}</div>;
  }

  return (
    <>
      {displayError && (
        <Alert tone="error">{displayError}</Alert>
      )}
      <div className="space-y-6">
        <div className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-2 shadow-sm">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {settingsSections.map((section) => (
              <button
                key={section.key}
                type="button"
                onClick={() => setActiveSection(section.key)}
                className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
                  activeSection === section.key
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] shadow-sm"
                    : "text-[var(--color-muted)] hover:bg-[var(--color-card-muted)] hover:text-[var(--color-foreground)]"
                }`}
              >
                {section.label}
              </button>
            ))}
          </div>
        </div>

        {activeSection === "security" ? (
          <SettingsBlock title={t("settings.securityTitle")} description={t("settings.twoFactorCardIntro")}>
            <div className="mt-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--color-foreground)]">Google Authenticator (TOTP)</p>
                  <p className="text-xs text-[var(--color-muted)]">
                    Belépéskor email kód helyett Google Authenticator alkalmazás kódját használod.
                  </p>
                </div>
                <span
                  className={`rounded-full px-2 py-1 text-xs ${
                    authenticatorEnabled
                      ? "bg-emerald-500/15 text-emerald-600"
                      : "bg-amber-500/15 text-amber-600"
                  }`}
                >
                  {authenticatorEnabled ? "Bekapcsolva" : authenticatorPending ? "Folyamatban" : "Kikapcsolva"}
                </span>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {!authenticatorEnabled ? (
                  <Button
                    type="button"
                    onClick={handleStartAuthenticatorSetup}
                    disabled={startAuthenticatorSetupMutation.isPending || confirmAuthenticatorSetupMutation.isPending}
                  >
                    {startAuthenticatorSetupMutation.isPending ? "Bekapcsolás..." : "Google Authenticator bekapcsolása"}
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="danger"
                    onClick={handleDisableAuthenticator}
                    disabled={disableAuthenticatorMutation.isPending}
                  >
                    {disableAuthenticatorMutation.isPending ? "Kikapcsolás..." : "Google Authenticator kikapcsolása"}
                  </Button>
                )}
              </div>
              <p className="mt-3 text-xs text-[var(--color-muted)]">
                Próbaidőszak alatt opcionális a 2FA, de előfizetés indításához kötelező az Authenticator aktiválása.
              </p>
            </div>
          </SettingsBlock>
        ) : null}

        {activeSection === "preferences" ? (
          <SettingsBlock title={t("settings.preferencesTitle")} description={t("settings.preferencesIntro")}>
            <div className="grid gap-4 md:grid-cols-3">
              <label className="block text-sm text-[var(--color-label)]">
                {t("settings.timezoneLabel")}
                <select
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value as SettingsTimezone)}
                  className="mt-1 w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
                  disabled={patchMutation.isPending}
                >
                  {TIMEZONE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-sm text-[var(--color-label)]">
                {t("settings.dateFormatLabel")}
                <select
                  value={dateFormat}
                  onChange={(e) => setDateFormat(e.target.value as SettingsDateFormat)}
                  className="mt-1 w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
                  disabled={patchMutation.isPending}
                >
                  {DATE_FORMAT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block text-sm text-[var(--color-label)]">
                {t("settings.timeFormatLabel")}
                <select
                  value={timeFormat}
                  onChange={(e) => setTimeFormat(e.target.value as SettingsTimeFormat)}
                  className="mt-1 w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
                  disabled={patchMutation.isPending}
                >
                  {TIME_FORMAT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </SettingsBlock>
        ) : null}

        {activeSection === "billing" ? (
          <SettingsBlock title={t("settings.billingCompanyTitle")}>
            <div className="grid gap-4 md:grid-cols-2">
              {[
                [t("settings.billingCompanyName"), billingCompanyName, setBillingCompanyName],
                [t("settings.billingTaxId"), billingTaxId, setBillingTaxId],
                [t("settings.billingAddressLine"), billingAddressLine, setBillingAddressLine],
                [t("settings.billingPostalCode"), billingPostalCode, setBillingPostalCode],
                [t("settings.billingCity"), billingCity, setBillingCity],
                [t("settings.billingRegion"), billingRegion, setBillingRegion],
                [t("settings.billingCountry"), billingCountry, setBillingCountry],
              ].map(([label, value, setter]) => (
                <label key={String(label)} className="block text-sm text-[var(--color-label)]">
                  {String(label)}
                  <input
                    value={String(value)}
                    onChange={(event) => (setter as (value: string) => void)(event.target.value)}
                    className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
                    disabled={patchMutation.isPending}
                  />
                </label>
              ))}
            </div>
          </SettingsBlock>
        ) : null}

        {activeSection === "domains" ? (
          <SettingsBlock title={t("settings.domainTitle")} description={t("settings.domainIntro")}>
            <div className="space-y-4">
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-3 text-sm">
                <p className="font-semibold text-[var(--color-foreground)]">{t("settings.domainHowToTitle")}</p>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-[var(--color-muted)]">
                  <li>{t("settings.domainHowToStep1")}</li>
                  <li>{t("settings.domainHowToStep2")}</li>
                  <li>{t("settings.domainHowToStep3")}</li>
                </ol>
                <p className="mt-3 text-[var(--color-muted)]">{t("settings.domainDnsTargetHint")}</p>
              </div>

              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-3 text-sm">
                <p className="text-[var(--color-muted)]">{t("settings.domainPrimary")}</p>
                <p className="font-medium text-[var(--color-foreground)]">{primaryDomain}</p>
                {showActiveCustomHost ? (
                  <>
                    <p className="mt-2 text-[var(--color-muted)]">{t("settings.domainActiveHost")}</p>
                    <p className="font-medium text-[var(--color-foreground)]">{domainQuery.data?.active_host ?? "-"}</p>
                  </>
                ) : null}
              </div>

              <div className="grid gap-2 md:grid-cols-[1fr_auto]">
                <label className="block text-sm text-[var(--color-label)]">
                  {t("settings.domainInputLabel")}
                  <input
                    value={customDomainInput}
                    onChange={(event) => setCustomDomainInput(event.target.value)}
                    placeholder={t("settings.domainPlaceholder")}
                    className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
                    disabled={addDomainMutation.isPending || patchMutation.isPending}
                  />
                </label>
                <div className="flex items-end pb-1">
                  <Button
                    type="button"
                    onClick={handleAddCustomDomain}
                    disabled={!customDomainInput.trim() || addDomainMutation.isPending || patchMutation.isPending}
                  >
                    {addDomainMutation.isPending ? t("common.loading") : t("settings.domainAddButton")}
                  </Button>
                </div>
              </div>

              {domainQuery.isLoading ? <p className="text-sm text-[var(--color-muted)]">{t("common.loading")}</p> : null}
              {!domainQuery.isLoading && customDomains.length === 0 ? (
                <p className="text-sm text-[var(--color-muted)]">{t("settings.domainEmpty")}</p>
              ) : null}

              {customDomains.length > 0 ? (
                <div className="overflow-x-auto rounded-lg border border-[var(--color-border)]">
                  <table className="w-full text-sm">
                    <thead className="border-b border-[var(--color-border)] text-left text-[var(--color-muted)]">
                      <tr>
                        <th className="px-3 py-2">{t("settings.domainInputLabel")}</th>
                        <th className="px-3 py-2">{t("settings.domainStatusLabel")}</th>
                        <th className="px-3 py-2 text-right">{t("settings.domainActionLabel")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {customDomains.map((domain) => (
                        <tr key={domain.domain} className="border-b border-[var(--color-border)]/60 last:border-b-0 align-top">
                          <td className="px-3 py-2">{domain.domain}</td>
                          <td className="px-3 py-2">
                            <span className="rounded-full bg-[var(--color-card-muted)] px-2 py-1 text-xs">
                              {getDomainStateLabel(domain.state)}
                            </span>
                            {domain.state === "custom_pending" ? (
                              <div className="mt-2 space-y-1 text-xs text-[var(--color-muted)]">
                                <p>
                                  {t("settings.domainHostInstruction")}{" "}
                                  <span className="font-medium text-[var(--color-foreground)]">
                                    {domain.dns_record_name ?? "-"}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => void copyText(`${domain.dns_record_name ?? "-"}`)}
                                    className="ml-2 inline-flex items-center rounded border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-foreground)] hover:bg-[var(--color-card)]"
                                  >
                                    {t("settings.domainCopyButton")}
                                  </button>
                                </p>
                                <p>
                                  {t("settings.domainTokenInstruction")}{" "}
                                  <span className="font-medium text-[var(--color-foreground)]">
                                    {domain.dns_record_value ?? "-"}
                                  </span>
                                  <button
                                    type="button"
                                    onClick={() => void copyText(`${domain.dns_record_value ?? "-"}`)}
                                    className="ml-2 inline-flex items-center rounded border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-foreground)] hover:bg-[var(--color-card)]"
                                  >
                                    {t("settings.domainCopyButton")}
                                  </button>
                                </p>
                              </div>
                            ) : null}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <div className="inline-flex gap-2">
                              {domain.state === "custom_pending" ? (
                                <Button
                                  type="button"
                                  variant="secondary"
                                  onClick={() => handleVerifyCustomDomain(domain.domain)}
                                  disabled={verifyDomainMutation.isPending || deleteDomainMutation.isPending}
                                >
                                  {verifyDomainMutation.isPending ? t("common.loading") : t("settings.domainVerifyButton")}
                                </Button>
                              ) : null}
                              <Button
                                type="button"
                                variant="danger"
                                onClick={() => handleDeleteCustomDomain(domain.domain)}
                                disabled={deleteDomainMutation.isPending || verifyDomainMutation.isPending}
                              >
                                {deleteDomainMutation.isPending ? t("common.loading") : t("settings.domainDeleteButton")}
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          </SettingsBlock>
        ) : null}

        {(activeSection === "preferences" || activeSection === "billing") ? (
          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={handleCancel} disabled={patchMutation.isPending}>
              {t("common.cancel")}
            </Button>
            <Button type="button" onClick={handleSave} disabled={patchMutation.isPending}>
              {patchMutation.isPending ? t("common.loading") : t("common.save")}
            </Button>
          </div>
        ) : null}
      </div>
      {authenticatorSetupReady && authenticatorSetupData ? (
        <Modal
          open
          onClose={() => {
            if (confirmAuthenticatorSetupMutation.isPending) return;
            setAuthenticatorWizardOpen(false);
            setAuthenticatorWizardStep(1);
          }}
          closeOnOverlay={!confirmAuthenticatorSetupMutation.isPending}
          panelClassName="max-w-2xl bg-[var(--color-background)]"
        >
          <ModalHeader
            eyebrow="Authenticator varázsló"
            title="Kétfaktoros hitelesítés beállítása"
            description="Kövesd a lépéseket: app letöltés, QR beolvasás, majd a 6 jegyű kód megerősítése."
          />
          <div className="space-y-4">
          {authenticatorWizardStep === 1 ? (
            <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
              <p className="text-sm font-semibold text-[var(--color-foreground)]">1) Töltsd le az Authenticator alkalmazást</p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Kérlek töltsd le az appot, majd lépj tovább a QR-kód beolvasásához.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <a
                  href={googleAuthenticatorAndroidUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm text-[var(--color-foreground)] hover:bg-[var(--color-card-muted)]"
                >
                  Google Authenticator (Android)
                </a>
                <a
                  href={googleAuthenticatorIosUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md border border-[var(--color-border)] bg-[var(--color-card)] px-3 py-2 text-sm text-[var(--color-foreground)] hover:bg-[var(--color-card-muted)]"
                >
                  Google Authenticator (iOS)
                </a>
              </div>
            </div>
          ) : null}

          {authenticatorWizardStep === 2 ? (
            <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
              <p className="text-sm font-semibold text-[var(--color-foreground)]">2) Olvasd be a QR-kódot</p>
              <div className="mt-3 inline-flex rounded border border-[var(--color-border)] bg-white p-2">
                <QRCodeSVG
                  value={authenticatorSetupData.otpauth_uri}
                  size={190}
                  includeMargin
                  bgColor="#ffffff"
                  fgColor="#111827"
                />
              </div>
              <p className="mt-3 text-xs text-[var(--color-muted)]">
                Ha nem tudod beolvasni, add meg kézzel ezt a kulcsot:
              </p>
              <div className="mt-2 rounded border border-[var(--color-border)] bg-[var(--color-card)] p-2">
                <code className="break-all text-xs text-[var(--color-foreground)]">{authenticatorSetupData.secret}</code>
              </div>
              <div className="mt-2 flex gap-2">
                <Button type="button" variant="secondary" onClick={() => void copyText(authenticatorSetupData.secret)}>
                  Titkos kulcs másolása
                </Button>
                <Button type="button" variant="secondary" onClick={() => void copyText(authenticatorSetupData.otpauth_uri)}>
                  OTP URI másolása
                </Button>
              </div>
            </div>
          ) : null}

          {authenticatorWizardStep === 3 ? (
            <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-card-muted)] p-4">
              <p className="text-sm font-semibold text-[var(--color-foreground)]">3) Validálás</p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                Írd be az appban látható 6 jegyű kódot.
              </p>
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <label className="block text-sm text-[var(--color-label)]">
                  Authenticator kód
                  <input
                    value={authenticatorCode}
                    onChange={(event) => setAuthenticatorCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="123456"
                    maxLength={6}
                    className="mt-1 w-40 rounded-md border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
                    disabled={confirmAuthenticatorSetupMutation.isPending}
                  />
                </label>
              </div>
            </div>
          ) : null}
          </div>
          <ModalFooter>
            {authenticatorWizardStep > 1 ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setAuthenticatorWizardStep((prev) => (prev === 3 ? 2 : 1))}
                disabled={confirmAuthenticatorSetupMutation.isPending}
              >
                Vissza
              </Button>
            ) : null}
            {authenticatorWizardStep < 3 ? (
              <Button
                type="button"
                onClick={() => setAuthenticatorWizardStep((prev) => (prev === 1 ? 2 : 3))}
                disabled={confirmAuthenticatorSetupMutation.isPending}
              >
                Tovább
              </Button>
            ) : (
              <Button
                type="button"
                onClick={handleConfirmAuthenticatorSetup}
                disabled={authenticatorCode.length !== 6 || confirmAuthenticatorSetupMutation.isPending}
              >
                {confirmAuthenticatorSetupMutation.isPending ? "Megerősítés..." : "Hitelesítés befejezése"}
              </Button>
            )}
            <Button
              type="button"
              variant="secondary"
              onClick={() => {
                setAuthenticatorWizardOpen(false);
                setAuthenticatorWizardStep(1);
              }}
              disabled={confirmAuthenticatorSetupMutation.isPending}
            >
              Bezárás
            </Button>
          </ModalFooter>
        </Modal>
      ) : null}
    </>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation();
  const { user } = useAuthStore();

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
    <div className="app-page">
      <div className="mx-auto w-full max-w-6xl space-y-8">
        <PageHeader
          eyebrow={t("settings.systemLabel")}
          title={t("nav.settings")}
          description={t("settings.pageIntro")}
        />
        <SystemSecurityBody />
      </div>
    </div>
  );
}
