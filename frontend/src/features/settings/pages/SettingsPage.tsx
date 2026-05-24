import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import Alert from "../../../components/ui/Alert";
import PageHeader from "../../../components/ui/PageHeader";
import type { AuthenticatorSetupResponse } from "../../../api/services/authenticatorService";
import type { DomainRecordResponse } from "../../../api/services/domainService";
import type { SettingsDateFormat, SettingsTimeFormat, SettingsTimezone } from "../../../api/services/settingsService";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import AuthenticatorSetupModal from "../components/AuthenticatorSetupModal";
import BillingSettingsSection from "../components/BillingSettingsSection";
import DomainsSettingsSection from "../components/DomainsSettingsSection";
import PreferencesSettingsSection from "../components/PreferencesSettingsSection";
import SecuritySettingsSection from "../components/SecuritySettingsSection";
import SettingsSaveBar from "../components/SettingsSaveBar";
import SettingsSectionTabs, { type SettingsSectionKey } from "../components/SettingsSectionTabs";
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
import { usePatchSettingsMutation, useSettings } from "../hooks/useSettings";

interface SystemSecurityBodyProps {
  onSaved?: () => void;
  onCancel?: () => void;
}

export function SystemSecurityBody({ onSaved, onCancel }: SystemSecurityBodyProps) {
  const { t } = useTranslation();
  const { data: settings, isLoading: loading, error: settingsError } = useSettings();
  const domainQuery = useDomainOverview();
  const patchMutation = usePatchSettingsMutation();
  const addDomainMutation = useAddCustomDomainMutation();
  const verifyDomainMutation = useVerifyCustomDomainMutation();
  const deleteDomainMutation = useDeleteCustomDomainMutation();
  const authenticatorStatusQuery = useAuthenticatorStatus();
  const startAuthenticatorSetupMutation = useStartAuthenticatorSetupMutation();
  const confirmAuthenticatorSetupMutation = useConfirmAuthenticatorSetupMutation();
  const disableAuthenticatorMutation = useDisableAuthenticatorMutation();

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
  const settingsSections = useMemo(
    () => [
      { key: "security" as const, label: t("settings.sectionSecurity") },
      { key: "preferences" as const, label: t("settings.sectionPreferences") },
      { key: "billing" as const, label: t("settings.sectionBilling") },
      { key: "domains" as const, label: t("settings.sectionDomains") },
    ],
    [t]
  );
  const authenticatorStatus = authenticatorStatusQuery.data;
  const authenticatorEnabled = Boolean(authenticatorStatus?.enabled);
  const authenticatorPending = Boolean(authenticatorStatus?.pending);
  const authenticatorSetupReady = !authenticatorEnabled && authenticatorWizardOpen && Boolean(authenticatorSetupData);
  const googleAuthenticatorAndroidUrl = "https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2";
  const googleAuthenticatorIosUrl = "https://apps.apple.com/app/google-authenticator/id388497605";

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
      onError: (error) => toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric")),
    });
  };

  const handleVerifyCustomDomain = (domain: string) => {
    verifyDomainMutation.mutate(domain, {
      onSuccess: () => toast.success(t("settings.domainVerifySuccess")),
      onError: (error) => toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric")),
    });
  };

  const handleDeleteCustomDomain = (domain: string) => {
    if (typeof window !== "undefined" && !window.confirm(t("settings.domainDeleteConfirm"))) return;
    deleteDomainMutation.mutate(domain, {
      onSuccess: () => toast.success(t("settings.domainDeleteSuccess")),
      onError: (error) => toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric")),
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

  const handleStartAuthenticatorSetup = () => {
    startAuthenticatorSetupMutation.mutate(undefined, {
      onSuccess: (data) => {
        setAuthenticatorSetupData(data);
        setAuthenticatorCode("");
        setAuthenticatorWizardStep(1);
        setAuthenticatorWizardOpen(true);
        toast.success("Authenticator setup elindítva.");
      },
      onError: (error) => toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric")),
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
      onError: (error) => toast.error(getApiErrorMessage(error) ?? "Érvénytelen authenticator kód."),
    });
  };

  const handleDisableAuthenticator = () => {
    if (typeof window !== "undefined" && !window.confirm("Biztosan kikapcsolod a Google Authenticator védelmet?")) return;
    disableAuthenticatorMutation.mutate(undefined, {
      onSuccess: () => {
        setAuthenticatorSetupData(null);
        setAuthenticatorCode("");
        setAuthenticatorWizardStep(1);
        setAuthenticatorWizardOpen(false);
        toast.success("Google Authenticator kikapcsolva.");
      },
      onError: (error) => toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric")),
    });
  };

  const getDomainStateLabel = (state: DomainRecordResponse["state"]): string => {
    if (state === "platform_primary") return t("settings.domainStatePlatformPrimary");
    if (state === "custom_verified") return t("settings.domainStateCustomVerified");
    return t("settings.domainStateCustomPending");
  };

  if (loading) {
    return <div>{t("common.loading")}</div>;
  }

  return (
    <>
      {displayError ? <Alert tone="error">{displayError}</Alert> : null}
      <div className="space-y-6">
        <SettingsSectionTabs sections={settingsSections} activeSection={activeSection} onChange={setActiveSection} />
        {activeSection === "security" ? (
          <SecuritySettingsSection
            title={t("settings.securityTitle")}
            description={t("settings.twoFactorCardIntro")}
            authenticatorEnabled={authenticatorEnabled}
            authenticatorPending={authenticatorPending}
            startPending={startAuthenticatorSetupMutation.isPending}
            confirmPending={confirmAuthenticatorSetupMutation.isPending}
            disablePending={disableAuthenticatorMutation.isPending}
            onStart={handleStartAuthenticatorSetup}
            onDisable={handleDisableAuthenticator}
          />
        ) : null}
        {activeSection === "preferences" ? (
          <PreferencesSettingsSection
            title={t("settings.preferencesTitle")}
            description={t("settings.preferencesIntro")}
            timezoneLabel={t("settings.timezoneLabel")}
            dateFormatLabel={t("settings.dateFormatLabel")}
            timeFormatLabel={t("settings.timeFormatLabel")}
            timezone={timezone}
            dateFormat={dateFormat}
            timeFormat={timeFormat}
            disabled={patchMutation.isPending}
            setTimezone={setTimezone}
            setDateFormat={setDateFormat}
            setTimeFormat={setTimeFormat}
          />
        ) : null}
        {activeSection === "billing" ? (
          <BillingSettingsSection
            title={t("settings.billingCompanyTitle")}
            disabled={patchMutation.isPending}
            fields={[
              { label: t("settings.billingCompanyName"), value: billingCompanyName, setter: setBillingCompanyName },
              { label: t("settings.billingTaxId"), value: billingTaxId, setter: setBillingTaxId },
              { label: t("settings.billingAddressLine"), value: billingAddressLine, setter: setBillingAddressLine },
              { label: t("settings.billingPostalCode"), value: billingPostalCode, setter: setBillingPostalCode },
              { label: t("settings.billingCity"), value: billingCity, setter: setBillingCity },
              { label: t("settings.billingRegion"), value: billingRegion, setter: setBillingRegion },
              { label: t("settings.billingCountry"), value: billingCountry, setter: setBillingCountry },
            ]}
          />
        ) : null}
        {activeSection === "domains" ? (
          <DomainsSettingsSection
            title={t("settings.domainTitle")}
            description={t("settings.domainIntro")}
            primaryDomain={primaryDomain}
            activeHost={domainQuery.data?.active_host}
            showActiveCustomHost={showActiveCustomHost}
            customDomainInput={customDomainInput}
            customDomains={customDomains}
            isLoading={domainQuery.isLoading}
            addPending={addDomainMutation.isPending}
            verifyPending={verifyDomainMutation.isPending}
            deletePending={deleteDomainMutation.isPending}
            patchPending={patchMutation.isPending}
            t={t}
            getDomainStateLabel={getDomainStateLabel}
            setCustomDomainInput={setCustomDomainInput}
            onAdd={handleAddCustomDomain}
            onVerify={handleVerifyCustomDomain}
            onDelete={handleDeleteCustomDomain}
            onCopy={(value) => void copyText(value)}
          />
        ) : null}
        {activeSection === "preferences" || activeSection === "billing" ? (
          <SettingsSaveBar
            cancelLabel={t("common.cancel")}
            saveLabel={t("common.save")}
            loadingLabel={t("common.loading")}
            disabled={patchMutation.isPending}
            onCancel={handleCancel}
            onSave={handleSave}
          />
        ) : null}
      </div>
      <AuthenticatorSetupModal
        open={authenticatorSetupReady}
        setupData={authenticatorSetupData}
        step={authenticatorWizardStep}
        code={authenticatorCode}
        confirmPending={confirmAuthenticatorSetupMutation.isPending}
        androidUrl={googleAuthenticatorAndroidUrl}
        iosUrl={googleAuthenticatorIosUrl}
        setStep={setAuthenticatorWizardStep}
        setCode={setAuthenticatorCode}
        onClose={() => {
          if (confirmAuthenticatorSetupMutation.isPending) return;
          setAuthenticatorWizardOpen(false);
          setAuthenticatorWizardStep(1);
        }}
        onCopy={(value) => void copyText(value)}
        onConfirm={handleConfirmAuthenticatorSetup}
      />
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
        <PageHeader eyebrow={t("settings.systemLabel")} title={t("nav.settings")} description={t("settings.pageIntro")} />
        <SystemSecurityBody />
      </div>
    </div>
  );
}
