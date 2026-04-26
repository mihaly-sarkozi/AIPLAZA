import { useMemo, useState } from "react";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview, usePurchaseAddonMutation, type BillingCatalogEntry } from "../../billing/hooks/useBilling";

export default function OrdersPage() {
  const { t } = useTranslation();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading, error: billingError } = useBillingOverview();
  const purchaseMutation = usePurchaseAddonMutation();
  const [extraKbQty, setExtraKbQty] = useState(1);
  const [extraStorageQty, setExtraStorageQty] = useState(1);

  const billingErrMsg =
    billingError && typeof (billingError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (billingError as { response?: { data?: { detail?: string } } }).response!.data!.detail
      : billingError
        ? t("common.errorGeneric")
        : null;
  const purchaseErrMsg = purchaseMutation.error ? t("common.errorGeneric") : null;

  const catalog = billingOverview?.catalog ?? [];
  const addonByCode = useMemo(() => {
    const m = new Map<string, BillingCatalogEntry>();
    for (const e of catalog) {
      if (e.entry_type === "addon") m.set(e.code, e);
    }
    return m;
  }, [catalog]);

  const buy = (code: string, quantity: number) => {
    purchaseMutation.mutate({ addon_code: code, quantity: Math.max(1, quantity) });
  };

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)] flex justify-center">
        <div className="w-full max-w-2xl bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] flex justify-center">
        <div className="max-w-2xl text-center">{t("common.loading")}</div>
      </div>
    );
  }

  const periodKey = billingOverview?.current_period_key ?? "—";
  const q100 = addonByCode.get("question_pack_100");
  const q500 = addonByCode.get("question_pack_500");
  const extraKb = addonByCode.get("extra_kb");
  const extraSt = addonByCode.get("extra_storage_gb");
  const trainInitial = addonByCode.get("training_initial_500k");
  const trainExtra = addonByCode.get("training_extra_500k");
  const pending = purchaseMutation.isPending;

  return (
    <div className="min-h-full w-full bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col items-center px-4 py-8">
      <div className="w-full max-w-2xl flex flex-col items-center">
        <h1 className="text-3xl font-bold mb-2 text-center">{t("nav.orders")}</h1>
        <p className="text-sm text-[var(--color-muted)] text-center mb-8">
          {t("traffic.billingPeriodLabel")}: <span className="text-[var(--color-foreground)] font-medium">{periodKey}</span>
        </p>

        {billingErrMsg || purchaseErrMsg ? (
          <div className="w-full bg-[var(--color-card)] border border-[var(--color-border)] p-4 rounded-lg mb-6 text-left">
            {billingErrMsg ?? purchaseErrMsg}
          </div>
        ) : null}

        <div className="w-full text-left space-y-6">
          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 w-full">
            <h2 className="text-lg font-semibold mb-4">{t("orders.sectionQuestions")}</h2>
            <div className="flex flex-wrap gap-2">
              {q100 ? (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => buy("question_pack_100", 1)}
                  className="text-xs sm:text-sm px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] hover:opacity-90 disabled:opacity-50"
                >
                  {q100.name} · {q100.price.toFixed(2)} €
                </button>
              ) : null}
              {q500 ? (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => buy("question_pack_500", 1)}
                  className="text-xs sm:text-sm px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] hover:opacity-90 disabled:opacity-50"
                >
                  {q500.name} · {q500.price.toFixed(2)} €
                </button>
              ) : null}
              {!q100 && !q500 ? <p className="text-sm text-[var(--color-muted)]">{t("orders.noneInCatalog")}</p> : null}
            </div>
          </section>

          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 w-full">
            <h2 className="text-lg font-semibold mb-4">{t("orders.sectionKbStorage")}</h2>
            <div className="flex flex-col gap-4">
              {extraKb ? (
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    value={extraKbQty}
                    onChange={(e) => setExtraKbQty(Math.max(1, Number(e.target.value) || 1))}
                    className="w-16 rounded border border-[var(--color-border)] px-2 py-1.5 text-sm"
                    aria-label={t("traffic.qtyExtraKb")}
                  />
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => buy("extra_kb", extraKbQty)}
                    className="text-xs sm:text-sm px-3 py-2 rounded-lg bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90 disabled:opacity-50"
                  >
                    {extraKb.name} · {extraKb.price.toFixed(2)} € / db
                  </button>
                </div>
              ) : null}
              {extraSt ? (
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="number"
                    min={1}
                    value={extraStorageQty}
                    onChange={(e) => setExtraStorageQty(Math.max(1, Number(e.target.value) || 1))}
                    className="w-16 rounded border border-[var(--color-border)] px-2 py-1.5 text-sm"
                    aria-label={t("traffic.qtyExtraGb")}
                  />
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => buy("extra_storage_gb", extraStorageQty)}
                    className="text-xs sm:text-sm px-3 py-2 rounded-lg bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90 disabled:opacity-50"
                  >
                    {extraSt.name} · {extraSt.price.toFixed(2)} € / GB
                  </button>
                </div>
              ) : null}
              {!extraKb && !extraSt ? <p className="text-sm text-[var(--color-muted)]">{t("orders.noneInCatalog")}</p> : null}
            </div>
          </section>

          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-6 w-full">
            <h2 className="text-lg font-semibold mb-4">{t("orders.sectionTraining")}</h2>
            <div className="flex flex-wrap gap-2">
              {trainInitial ? (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => buy("training_initial_500k", 1)}
                  className="text-xs sm:text-sm px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] hover:opacity-90 disabled:opacity-50"
                >
                  {trainInitial.name} · {trainInitial.price.toFixed(2)} €
                </button>
              ) : null}
              {trainExtra ? (
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => buy("training_extra_500k", 1)}
                  className="text-xs sm:text-sm px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] hover:opacity-90 disabled:opacity-50"
                >
                  {trainExtra.name} · {trainExtra.price.toFixed(2)} €
                </button>
              ) : null}
              {!trainInitial && !trainExtra ? <p className="text-sm text-[var(--color-muted)]">{t("orders.noneInCatalog")}</p> : null}
            </div>
          </section>

          <p className="text-xs text-[var(--color-muted)] text-center">{t("traffic.addonPurchaseHint")}</p>
        </div>
      </div>
    </div>
  );
}
