import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import api from "../../../api/axiosClient";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";
import { useTranslation } from "../../../i18n";
import { queryKeys } from "../../../queryKeys";
import { useAuthStore } from "../../../store/authStore";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";

export default function BillingDateSimulationPage() {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [debugDate, setDebugDate] = useState("");
  const [debugCurrentDate, setDebugCurrentDate] = useState<string | null>(null);
  const [debugDateSaving, setDebugDateSaving] = useState(false);
  const [debugBillingRunning, setDebugBillingRunning] = useState<"success" | "failed" | null>(null);
  const [debugBillingMessage, setDebugBillingMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const fallbackCurrentDate = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const loadDebugDate = async () => {
    try {
      const res = await api.get("/billing/debug/simulated-date");
      setDebugDate(String(res.data?.simulated_date ?? ""));
      setDebugCurrentDate(String(res.data?.current_date ?? ""));
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Valami hiba történt");
      setDebugCurrentDate(null);
    }
  };

  useEffect(() => {
    if (user?.role !== "owner") return;
    void loadDebugDate();
  }, [user?.role]);

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)] flex justify-center">
        <div className="w-full max-w-2xl bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  const refreshBillingQueries = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.billingOverview });
    await queryClient.invalidateQueries({ queryKey: queryKeys.billingAccessStatus });
    await queryClient.refetchQueries({ queryKey: queryKeys.billingAccessStatus });
  };

  const saveDebugDate = async () => {
    setDebugDateSaving(true);
    setError(null);
    try {
      await api.put("/billing/debug/simulated-date", { simulated_date: debugDate || null });
      await loadDebugDate();
      await refreshBillingQueries();
    } catch (err) {
      setError(getApiErrorMessage(err) ?? t("common.errorGeneric"));
    } finally {
      setDebugDateSaving(false);
    }
  };

  const clearDebugDate = async () => {
    setDebugDateSaving(true);
    setError(null);
    try {
      await api.delete("/billing/debug/simulated-date");
      setDebugDate("");
      await loadDebugDate();
      await refreshBillingQueries();
    } catch (err) {
      setError(getApiErrorMessage(err) ?? t("common.errorGeneric"));
    } finally {
      setDebugDateSaving(false);
    }
  };

  const runDebugBilling = async (outcome: "success" | "failed") => {
    setDebugBillingRunning(outcome);
    setDebugBillingMessage("");
    setError(null);
    try {
      const res = await api.post("/billing/debug/run-subscription-billing", { outcome });
      setDebugBillingMessage(String(res.data?.message ?? ""));
      await refreshBillingQueries();
    } catch (err) {
      setError(getApiErrorMessage(err) ?? t("common.errorGeneric"));
    } finally {
      setDebugBillingRunning(null);
    }
  };

  return (
    <div className="app-page">
      <div className="mx-auto max-w-3xl space-y-6">
        <PageHeader
          eyebrow={t("nav.dateSimulation")}
          title={t("billing.debugDateTitle")}
          description={t("billing.debugDateHint")}
        />

        {error ? <Alert tone="error">{error}</Alert> : null}

        <section className="app-surface p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--color-muted)]">{t("billing.debugCurrentDate")}</p>
              <p className="mt-1 text-2xl font-semibold text-[var(--color-foreground)]">{debugCurrentDate || fallbackCurrentDate}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="date"
                value={debugDate}
                onChange={(event) => setDebugDate(event.target.value)}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-input-bg)] px-3 py-2 text-sm text-[var(--color-foreground)]"
              />
              <Button type="button" size="sm" onClick={saveDebugDate} disabled={debugDateSaving}>
                {debugDateSaving ? t("common.loading") : t("billing.debugApplyDate")}
              </Button>
              <Button type="button" size="sm" variant="secondary" onClick={clearDebugDate} disabled={debugDateSaving}>
                {t("billing.debugClearDate")}
              </Button>
            </div>
          </div>
        </section>

        <section className="app-surface p-6">
          <p className="text-sm font-medium text-[var(--color-muted)]">{t("billing.debugBillingActionsTitle")}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" onClick={() => runDebugBilling("success")} disabled={debugBillingRunning !== null}>
              {debugBillingRunning === "success" ? t("common.loading") : t("billing.debugRunSuccessfulBilling")}
            </Button>
            <Button type="button" variant="danger" onClick={() => runDebugBilling("failed")} disabled={debugBillingRunning !== null}>
              {debugBillingRunning === "failed" ? t("common.loading") : t("billing.debugRunFailedBilling")}
            </Button>
          </div>
          {debugBillingMessage ? <p className="mt-3 text-sm font-medium text-[var(--color-muted)]">{debugBillingMessage}</p> : null}
        </section>
      </div>
    </div>
  );
}
