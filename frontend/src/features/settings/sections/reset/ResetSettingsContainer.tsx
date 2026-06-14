import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../../i18n";
import { queryKeys } from "../../../../queryKeys";
import { getApiErrorMessage } from "../../../../utils/getApiErrorMessage";
import { useTenantResetMutation } from "../../hooks/useTenantReset";
import ResetSettingsSection from "./ResetSettingsSection";

function tenantSlugFromHost(): string | null {
  const host = window.location.hostname.toLowerCase();
  const parts = host.split(".");
  if (parts.length < 3) return null;
  const slug = parts[0];
  return slug && slug !== "www" ? slug : null;
}

export default function ResetSettingsContainer() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirmSlug, setConfirmSlug] = useState("");
  const expectedSlug = useMemo(() => tenantSlugFromHost(), []);
  const resetMutation = useTenantResetMutation();

  const handleSubmit = () => {
    if (!expectedSlug || confirmSlug.trim().toLowerCase() !== expectedSlug.toLowerCase()) return;
    if (typeof window !== "undefined" && !window.confirm(t("settings.resetConfirmDialog"))) return;
    resetMutation
      .mutateAsync({ confirm_slug: confirmSlug.trim().toLowerCase() })
      .then((res) => {
        setConfirmSlug("");
        toast.success(res.message || t("settings.resetSuccess"));
        void queryClient.invalidateQueries({ queryKey: queryKeys.kb });
        void queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
        void queryClient.invalidateQueries({ queryKey: queryKeys.billingAccessStatus });
        const kbUuid = res.default_knowledge_base_uuid?.trim();
        navigate(kbUuid ? `/kb/ingest/${kbUuid}` : "/kb", { replace: true });
      })
      .catch((error) => toast.error(getApiErrorMessage(error) ?? t("common.errorGeneric")));
  };

  return (
    <ResetSettingsSection
      title={t("settings.resetTitle")}
      description={t("settings.resetIntro")}
      warning={t("settings.resetWarning")}
      confirmLabel={t("settings.resetConfirmLabel")}
      confirmPlaceholder={t("settings.resetConfirmPlaceholder")}
      confirmSlug={confirmSlug}
      expectedSlug={expectedSlug}
      slugHint={t("settings.resetSlugHint")}
      submitLabel={resetMutation.isPending ? t("settings.resetPending") : t("settings.resetSubmit")}
      pending={resetMutation.isPending}
      error={resetMutation.error ? getApiErrorMessage(resetMutation.error) ?? t("common.errorGeneric") : null}
      onConfirmSlugChange={setConfirmSlug}
      onSubmit={handleSubmit}
    />
  );
}
