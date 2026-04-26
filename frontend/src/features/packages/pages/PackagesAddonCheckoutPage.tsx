import { useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview, usePurchaseAddonMutation, type BillingCatalogEntry } from "../../billing/hooks/useBilling";
import { isAddonCheckoutCode } from "../addonCheckoutAllowed";

function formatEuroLocaleFromCents(cents: number, locale: string): string {
  const value = Number(cents) / 100;
  const tag = locale === "es" ? "es-ES" : locale === "en" ? "en-GB" : "hu-HU";
  const whole = Math.round(value * 100) % 100 === 0;
  return value.toLocaleString(tag, whole ? { maximumFractionDigits: 0 } : { minimumFractionDigits: 1, maximumFractionDigits: 2 });
}

export default function PackagesAddonCheckoutPage() {
  const { t, locale } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const { data: billingOverview, isLoading } = useBillingOverview();
  const purchaseAddonMutation = usePurchaseAddonMutation();

  const addonCode = (searchParams.get("addon") ?? "").trim().toLowerCase();
  const quantity = Math.max(1, Math.min(99, parseInt(searchParams.get("qty") ?? "1", 10) || 1));

  const [cardNumber, setCardNumber] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvc, setCardCvc] = useState("");
  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [country, setCountry] = useState("");
  const [taxId, setTaxId] = useState("");
  const [acceptTerms, setAcceptTerms] = useState(false);

  const catalog = billingOverview?.catalog ?? [];
  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");
  const isFreeDemoBlocked = currentPlanCode === "free" && Boolean(billingOverview?.demo_mode);

  const addonEntry = useMemo((): BillingCatalogEntry | null => {
    if (!isAddonCheckoutCode(addonCode)) return null;
    const row = catalog.find((e) => e.entry_type === "addon" && e.code === addonCode);
    return row ?? null;
  }, [addonCode, catalog]);

  const lineTotalCents = addonEntry != null ? Number(addonEntry.price_cents) * quantity : 0;
  const lineTotalLabel = formatEuroLocaleFromCents(lineTotalCents, locale);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!addonEntry || isFreeDemoBlocked || !acceptTerms) return;
    try {
      await purchaseAddonMutation.mutateAsync({ addon_code: addonCode, quantity });
      navigate("/admin/csomagok", {
        state: { addonCheckoutComplete: true, message: t("packages.addonCheckoutSuccessMessage"), status: "addon" },
      });
    } catch {
      /* mutation error */
    }
  };

  if (!user || user.role !== "owner") {
    return (
      <div className="p-6 min-h-full bg-[var(--color-background)]">
        <div className="bg-[var(--color-card)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded max-w-lg mx-auto">
          {t("settings.ownerOnly")}
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
        <div>{t("common.loading")}</div>
      </div>
    );
  }

  if (!addonEntry || !isAddonCheckoutCode(addonCode)) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.addonCheckoutInvalidAddon")}</p>
        <button
          type="button"
          className="rounded-lg px-4 py-2 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-medium"
          onClick={() => navigate("/admin/csomagok")}
        >
          {t("packages.checkoutBackToPackages")}
        </button>
      </div>
    );
  }

  if (isFreeDemoBlocked) {
    return (
      <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)] max-w-lg mx-auto">
        <p className="text-[var(--color-muted)] mb-4">{t("packages.addonCheckoutDemoBlocked")}</p>
        <button
          type="button"
          className="rounded-lg px-4 py-2 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-medium"
          onClick={() => navigate("/admin/csomagok")}
        >
          {t("packages.checkoutBackToPackages")}
        </button>
      </div>
    );
  }

  const submitDisabled =
    !acceptTerms ||
    purchaseAddonMutation.isPending ||
    !fullName.trim() ||
    !cardNumber.trim() ||
    !cardExpiry.trim() ||
    !cardCvc.trim();

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="max-w-xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-center">{t("packages.addonCheckoutPageTitle")}</h1>
        <p className="text-sm text-[var(--color-muted)] text-center leading-relaxed">{t("packages.addonCheckoutIntro")}</p>

        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-sm space-y-2">
          <p className="font-medium">{t("packages.addonCheckoutSummaryHeading")}</p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.addonCheckoutItem")}</span>{" "}
            <span className="font-medium">{addonEntry.name}</span>
          </p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.addonCheckoutQuantity")}</span>{" "}
            <span className="font-medium tabular-nums">{quantity}</span>
          </p>
          <p>
            <span className="text-[var(--color-muted)]">{t("packages.addonCheckoutLineTotal")}</span>{" "}
            <span className="font-medium tabular-nums">{lineTotalLabel} €</span>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4">
          <h2 className="text-sm font-semibold">{t("packages.checkoutPaymentSection")}</h2>
          <div className="space-y-3">
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutCardNumber")}
              <input
                value={cardNumber}
                onChange={(e) => setCardNumber(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="cc-number"
                placeholder="4242 4242 4242 4242"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCardExpiry")}
                <input
                  value={cardExpiry}
                  onChange={(e) => setCardExpiry(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="cc-exp"
                  placeholder="MM/YY"
                />
              </label>
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCardCvc")}
                <input
                  value={cardCvc}
                  onChange={(e) => setCardCvc(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="cc-csc"
                  placeholder="CVC"
                />
              </label>
            </div>
          </div>

          <h2 className="text-sm font-semibold pt-2">{t("packages.checkoutBillingSection")}</h2>
          <div className="space-y-3">
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutFullName")}
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="name"
              />
            </label>
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutCompany")}
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="organization"
              />
            </label>
            <label className="block text-xs text-[var(--color-muted)]">
              {t("packages.checkoutAddress")}
              <input
                value={addressLine}
                onChange={(e) => setAddressLine(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                autoComplete="street-address"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutCountry")}
                <input
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                  autoComplete="country-name"
                />
              </label>
              <label className="block text-xs text-[var(--color-muted)]">
                {t("packages.checkoutTaxId")}
                <input
                  value={taxId}
                  onChange={(e) => setTaxId(e.target.value)}
                  className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2 text-sm"
                />
              </label>
            </div>
          </div>

          <label className="flex gap-2 items-start text-sm pt-2 cursor-pointer">
            <input type="checkbox" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} className="mt-1" />
            <span>{t("packages.checkoutAcceptSimulated")}</span>
          </label>

          {purchaseAddonMutation.isError ? (
            <p className="text-sm text-red-600 dark:text-red-400">{t("common.errorGeneric")}</p>
          ) : null}

          <p className="text-xs text-[var(--color-muted)] leading-relaxed">{t("packages.flexNoteFinePrint")}</p>

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              type="submit"
              disabled={submitDisabled}
              className="rounded-lg px-4 py-2.5 bg-[var(--color-primary)] text-[var(--color-on-primary)] text-sm font-semibold disabled:opacity-50"
            >
              {purchaseAddonMutation.isPending ? t("common.loading") : t("packages.addonCheckoutSubmit")}
            </button>
            <button
              type="button"
              className="rounded-lg px-4 py-2.5 border border-[var(--color-border)] text-sm"
              onClick={() => navigate("/admin/csomagok")}
            >
              {t("common.cancel")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
