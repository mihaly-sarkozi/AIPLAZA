// frontend/src/features/settings/sections/security/SecuritySettingsContainer.tsx
// Feladat: Security/authenticator container, amely a flow hookot és UI komponenseket összekapcsolja.
// Sárközi Mihály - 2026.05.29

import { useMemo } from "react";
import { toast } from "sonner";
import Alert from "../../../../components/ui/Alert";
import { useTranslation } from "../../../../i18n";
import { getApiErrorMessage } from "../../../../utils/getApiErrorMessage";
import { useClipboard } from "../../hooks/useClipboard";
import AuthenticatorSetupModal, { type AuthenticatorSetupModalLabels } from "./AuthenticatorSetupModal";
import SecuritySettingsSection from "./SecuritySettingsSection";
import { useAuthenticatorFlow } from "./useAuthenticatorFlow";

export default function SecuritySettingsContainer() {
  const { t } = useTranslation();
  const { copy } = useClipboard();
  const flow = useAuthenticatorFlow();
  const labels = useMemo(
    () => ({
      authenticatorTitle: t("settings.authenticatorTitle"),
      authenticatorDescription: t("settings.authenticatorDescription"),
      statusEnabled: t("settings.authenticatorStatusEnabled"),
      statusPending: t("settings.authenticatorStatusPending"),
      statusDisabled: t("settings.authenticatorStatusDisabled"),
      enableAction: t("settings.authenticatorEnableAction"),
      enablePending: t("settings.authenticatorEnablePending"),
      disableAction: t("settings.authenticatorDisableAction"),
      disablePending: t("settings.authenticatorDisablePending"),
      trialNotice: t("settings.authenticatorTrialNotice"),
    }),
    [t]
  );
  const modalLabels = useMemo<AuthenticatorSetupModalLabels>(
    () => ({
      eyebrow: t("settings.authenticatorWizardEyebrow"),
      title: t("settings.authenticatorWizardTitle"),
      description: t("settings.authenticatorWizardDescription"),
      back: t("settings.authenticatorWizardBack"),
      next: t("settings.authenticatorWizardNext"),
      close: t("settings.authenticatorWizardClose"),
      confirmPending: t("settings.authenticatorWizardConfirmPending"),
      confirmAction: t("settings.authenticatorWizardConfirmAction"),
      downloadTitle: t("settings.authenticatorDownloadTitle"),
      downloadDescription: t("settings.authenticatorDownloadDescription"),
      qrTitle: t("settings.authenticatorQrTitle"),
      qrManualHint: t("settings.authenticatorQrManualHint"),
      copySecret: t("settings.authenticatorCopySecret"),
      copyOtpUri: t("settings.authenticatorCopyOtpUri"),
      validateTitle: t("settings.authenticatorValidateTitle"),
      validateDescription: t("settings.authenticatorValidateDescription"),
      codeLabel: t("settings.authenticatorCodeLabel"),
    }),
    [t]
  );

  return (
    <div className="space-y-4">
      {flow.statusError ? <Alert tone="error">{getApiErrorMessage(flow.statusError) ?? t("common.errorGeneric")}</Alert> : null}
      <SecuritySettingsSection
        title={t("settings.securityTitle")}
        description={t("settings.twoFactorCardIntro")}
        labels={labels}
        authenticatorEnabled={flow.enabled}
        authenticatorPending={flow.pending}
        startPending={flow.startPending}
        confirmPending={flow.confirmPending}
        disablePending={flow.disablePending}
        onStart={() =>
          flow
            .startSetup()
            .then(() => {
              flow.openWizard();
              toast.success(t("settings.authenticatorSetupStarted"));
            })
            .catch((error) => toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric")))
        }
        onDisable={() => {
          if (typeof window !== "undefined" && !window.confirm(t("settings.authenticatorDisableConfirm"))) return;
          flow
            .disable()
            .then(() => toast.success(t("settings.authenticatorDisabledSuccess")))
            .catch((error) => toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric")));
        }}
      />
      <AuthenticatorSetupModal
        open={flow.setupReady}
        setupData={flow.setupData}
        labels={modalLabels}
        step={flow.wizardStep}
        code={flow.code}
        confirmPending={flow.confirmPending}
        androidUrl="https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2"
        iosUrl="https://apps.apple.com/app/google-authenticator/id388497605"
        setStep={flow.setWizardStep}
        setCode={flow.setCode}
        onClose={flow.closeWizard}
        onCopy={(value) =>
          copy(value).then((ok) => {
            if (ok) toast.success(t("settings.domainCopySuccess"));
            else toast.error(t("common.errorGeneric"));
          })
        }
        onConfirm={() => {
          if (!flow.isCodeValid) {
            toast.error(t("settings.authenticatorCodeRequired"));
            return;
          }
          flow
            .confirmSetup()
            .then(() => toast.success(t("settings.authenticatorEnabledSuccess")))
            .catch((error) => toast.error(getApiErrorMessage(error) ?? t("settings.authenticatorInvalidCode")));
        }}
      />
    </div>
  );
}
