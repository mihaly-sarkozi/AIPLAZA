import Button from "../../../components/ui/Button";
import { formatEuroLocaleFromCents } from "./packageUtils";

type ExpansionOption = {
  addonCode: string;
  title: string;
  unitLabel: string;
  unitPriceCents: number;
  priceSuffix?: string;
  quantity: number;
  setQuantity: (value: number) => void;
  totalCents: number;
};

type PackageExpansionModalProps = {
  open: boolean;
  expansionOptions: ExpansionOption[];
  selectedExpansionItemsCount: number;
  expansionTotalPriceCents: number;
  checkoutItemsParam: string;
  locale: string;
  t: (key: string) => string;
  onClose: () => void;
  onCheckout: (checkoutItemsParam: string) => void;
};

export default function PackageExpansionModal({
  open,
  expansionOptions,
  selectedExpansionItemsCount,
  expansionTotalPriceCents,
  checkoutItemsParam,
  locale,
  t,
  onClose,
  onCheckout,
}: PackageExpansionModalProps) {
  if (!open) return null;
  const changeQuantity = (setter: (value: number) => void, current: number, delta: number) => {
    setter(Math.max(0, Math.min(99, current + delta)));
  };

  return (
    <div className="fixed inset-0 z-[83] flex items-center justify-center p-4 bg-black/40" role="presentation" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="packages-banner-expand-title"
        className="w-full max-w-2xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[var(--color-muted)]">{t("packages.bannerExpandCta")}</p>
            <h2 id="packages-banner-expand-title" className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">
              {t("traffic.expandModalTitle")}
            </h2>
          </div>
          <button
            type="button"
            className="rounded-lg px-2 py-1 text-sm text-[var(--color-muted)] hover:bg-[var(--color-card-muted)] hover:text-[var(--color-foreground)]"
            onClick={onClose}
          >
            {t("common.close")}
          </button>
        </div>

        <div className="mt-5 grid gap-2">
          {expansionOptions.map((item) => (
            <div key={item.addonCode} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium text-[var(--color-foreground)]">{item.title}</p>
                  <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                    {t("traffic.expandUnitPrice")
                      .replace("{{unit}}", item.unitLabel)
                      .replace("{{price}}", `${formatEuroLocaleFromCents(item.unitPriceCents, locale)} €`)}
                    {item.priceSuffix ? ` ${item.priceSuffix}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-4">
                  <div className="flex items-center rounded-lg border border-[var(--color-border)]">
                    <button type="button" className="px-2 py-1 text-sm" onClick={() => changeQuantity(item.setQuantity, item.quantity, -1)}>
                      -
                    </button>
                    <span className="min-w-8 px-2 text-center text-sm tabular-nums">{item.quantity}</span>
                    <button type="button" className="px-2 py-1 text-sm" onClick={() => changeQuantity(item.setQuantity, item.quantity, 1)}>
                      +
                    </button>
                  </div>
                  <span className="min-w-24 text-right text-sm font-medium text-[var(--color-foreground)]">
                    {formatEuroLocaleFromCents(item.totalCents, locale)} € {t("packages.taxSuffix")}
                  </span>
                </div>
              </div>
            </div>
          ))}

          <p className="px-1 text-xs text-[var(--color-muted)]">{t("traffic.expandOtherOptionsHint")}</p>
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card-muted)] px-3 py-2.5">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-medium text-[var(--color-muted)]">{t("traffic.expandTotal")}</span>
              <span className="text-lg font-semibold text-[var(--color-foreground)]">
                {formatEuroLocaleFromCents(expansionTotalPriceCents, locale)} € {t("packages.taxSuffix")}
              </span>
            </div>
            <Button type="button" fullWidth className="mt-3" disabled={selectedExpansionItemsCount === 0} onClick={() => onCheckout(checkoutItemsParam)}>
              {t("traffic.expandPay")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
