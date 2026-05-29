// frontend/src/features/settings/sections/domains/DomainsSettingsContainer.tsx
// Feladat: Domains settings container a domain flow hook és UI komponens összekötésére.
// Sárközi Mihály - 2026.05.29

import { toast } from "sonner";
import Alert from "../../../../components/ui/Alert";
import { useTranslation } from "../../../../i18n";
import { getApiErrorMessage } from "../../../../utils/getApiErrorMessage";
import { useClipboard } from "../../hooks/useClipboard";
import DomainsSettingsSection from "./DomainsSettingsSection";
import { useDomainFlow } from "./useDomainFlow";
import type { DomainRow } from "./domainTypes";

export default function DomainsSettingsContainer() {
  const { t } = useTranslation();
  const { copy } = useClipboard();
  const {
    customDomainInput,
    setCustomDomainInput,
    overview,
    loading,
    error,
    addPending,
    verifyPending,
    deletePending,
    addDomain,
    verifyDomain,
    deleteDomain,
  } = useDomainFlow();
  return (
    <div className="space-y-4">
      {error ? <Alert tone="error">{getApiErrorMessage(error) ?? t("common.errorGeneric")}</Alert> : null}
      <DomainsSettingsSection
        title={t("settings.domainTitle")}
        description={t("settings.domainIntro")}
        primaryDomain={overview.primaryDomain}
        activeHost={overview.activeHost}
        showActiveCustomHost={overview.showActiveCustomHost}
        customDomainInput={customDomainInput}
        customDomains={overview.customDomains}
        isLoading={loading}
        addPending={addPending}
        verifyPending={verifyPending}
        deletePending={deletePending}
        t={t}
        getDomainStateLabel={(state) => getDomainStateLabel(state, t)}
        setCustomDomainInput={setCustomDomainInput}
        onAdd={() =>
          addDomain(customDomainInput.trim().toLowerCase())
            .then(() => {
              toast.success(t("settings.domainCreateSuccess"));
              setCustomDomainInput("");
            })
            .catch(() => undefined)
        }
        onVerify={(domain) => verifyDomain(domain).then(() => toast.success(t("settings.domainVerifySuccess"))).catch(() => undefined)}
        onDelete={(domain) => {
          if (typeof window !== "undefined" && !window.confirm(t("settings.domainDeleteConfirm"))) return;
          deleteDomain(domain).then(() => toast.success(t("settings.domainDeleteSuccess"))).catch(() => undefined);
        }}
        onCopy={(value) =>
          copy(value).then((ok) => {
            if (ok) toast.success(t("settings.domainCopySuccess"));
            else toast.error(t("common.errorGeneric"));
          })
        }
      />
    </div>
  );
}

function getDomainStateLabel(state: DomainRow["state"], t?: (key: string) => string): string {
  const translate = t ?? ((key: string) => key);
  if (state === "platform_primary") return translate("settings.domainStatePlatformPrimary");
  if (state === "custom_verified") return translate("settings.domainStateCustomVerified");
  return translate("settings.domainStateCustomPending");
}
