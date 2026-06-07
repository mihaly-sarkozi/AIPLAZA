// Feladat: A forgalom oldal csomagbővítő felugrója. Addon tételeket választat, majd checkout paraméterként átadja a számlázási flow-nak.

import { useState } from "react";
import Button from "../../../components/ui/Button";
import { useTranslation } from "../../../i18n";
import type { TrafficCatalogEntry } from "../types/trafficTypes";

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

type TrafficExpansionModalProps = {
  catalog: TrafficCatalogEntry[];
  onClose: () => void;
  onCheckout: (itemsParam: string) => void;
};

function localeTag(locale: string): string {
  if (locale === "en") return "en-GB";
  if (locale === "es") return "es-ES";
  return "hu-HU";
}

function numberValue(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatNumber(value: number, locale: string): string {
  return value.toLocaleString(localeTag(locale));
}

function formatCharsAsK(value: number, locale: string): string {
  const normalized = Math.max(0, Number(value || 0));
  const inThousands = normalized / 1000;
  const whole = Math.round(inThousands * 10) % 10 === 0;
  const formatted = inThousands.toLocaleString(localeTag(locale), whole ? { maximumFractionDigits: 0 } : { maximumFractionDigits: 1 });
  return `${formatted}K`;
}

function formatEuroFromCents(cents: number, locale: string): string {
  const value = cents / 100;
  const whole = Math.round(value * 100) % 100 === 0;
  return value.toLocaleString(localeTag(locale), whole ? { maximumFractionDigits: 0 } : { maximumFractionDigits: 2 });
}

function addonEntry(catalog: TrafficCatalogEntry[], code: string): TrafficCatalogEntry | null {
  return catalog.find((item) => item.entry_type === "addon" && item.code === code) ?? null;
}

function includedNumber(entry: TrafficCatalogEntry | null, key: string, fallback: number): number {
  const raw = entry?.included && typeof entry.included === "object" ? entry.included[key] : null;
  const parsed = Number(raw ?? fallback);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function changeQuantity(setter: (value: number) => void, current: number, delta: number) {
  setter(Math.max(0, Math.min(99, current + delta)));
}

export default function TrafficExpansionModal({ catalog, onClose, onCheckout }: TrafficExpansionModalProps) {
  const { t, locale } = useTranslation();
  const [storageQuantity, setStorageQuantity] = useState(0);
  const [trainingQuantity, setTrainingQuantity] = useState(0);
  const [question100Quantity, setQuestion100Quantity] = useState(0);
  const [question500Quantity, setQuestion500Quantity] = useState(0);

  const storageAddon = addonEntry(catalog, "extra_storage_gb");
  const trainingAddon = addonEntry(catalog, "training_extra_500k");
  const question100Addon = addonEntry(catalog, "question_pack_100");
  const question500Addon = addonEntry(catalog, "question_pack_500");
  const storageUnitGb = includedNumber(storageAddon, "storage_gb", 1);
  const trainingUnitChars = includedNumber(trainingAddon, "training_chars", 500000);
  const question100Count = includedNumber(question100Addon, "questions", 100);
  const question500Count = includedNumber(question500Addon, "questions", 500);

  const options: ExpansionOption[] = [
    {
      addonCode: "training_extra_500k",
      title: t("packages.expandTrainingTitle").replace("{{chars}}", formatCharsAsK(trainingUnitChars, locale)),
      unitLabel: `${formatCharsAsK(trainingUnitChars, locale)} ${t("traffic.expandCharactersUnit")}`,
      unitPriceCents: numberValue(trainingAddon?.price_cents),
      quantity: trainingQuantity,
      setQuantity: setTrainingQuantity,
      totalCents: numberValue(trainingAddon?.price_cents) * trainingQuantity,
    },
    {
      addonCode: "extra_storage_gb",
      title: t("packages.expandStorageTitle").replace("{{gb}}", String(storageUnitGb)),
      unitLabel: `${formatNumber(storageUnitGb, locale)} GB`,
      unitPriceCents: numberValue(storageAddon?.price_cents),
      priceSuffix: `/ ${t("packages.perMonthSuffix")}`,
      quantity: storageQuantity,
      setQuantity: setStorageQuantity,
      totalCents: numberValue(storageAddon?.price_cents) * storageQuantity,
    },
    {
      addonCode: "question_pack_100",
      title: t("packages.expandQuestionsTitle").replace("{{count}}", String(question100Count)),
      unitLabel: `${formatNumber(question100Count, locale)} ${t("traffic.questionsByUserCount").toLowerCase()}`,
      unitPriceCents: numberValue(question100Addon?.price_cents),
      quantity: question100Quantity,
      setQuantity: setQuestion100Quantity,
      totalCents: numberValue(question100Addon?.price_cents) * question100Quantity,
    },
    {
      addonCode: "question_pack_500",
      title: t("packages.expandQuestionsTitle").replace("{{count}}", String(question500Count)),
      unitLabel: `${formatNumber(question500Count, locale)} ${t("traffic.questionsByUserCount").toLowerCase()}`,
      unitPriceCents: numberValue(question500Addon?.price_cents),
      quantity: question500Quantity,
      setQuantity: setQuestion500Quantity,
      totalCents: numberValue(question500Addon?.price_cents) * question500Quantity,
    },
  ];
  const selectedItems = options.filter((item) => item.quantity > 0);
  const totalCents = selectedItems.reduce((sum, item) => sum + item.totalCents, 0);
  const checkoutItemsParam = selectedItems.map((item) => `${item.addonCode}:${item.quantity}`).join(",");

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4" role="presentation" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="traffic-expand-title"
        className="w-full max-w-2xl rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[var(--color-muted)]">{t("traffic.expandPackages")}</p>
            <h2 id="traffic-expand-title" className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">
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
          {options.map((item) => (
            <div key={item.addonCode} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2.5">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium text-[var(--color-foreground)]">{item.title}</p>
                  <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                    {t("traffic.expandUnitPrice")
                      .replace("{{unit}}", item.unitLabel)
                      .replace("{{price}}", `${formatEuroFromCents(item.unitPriceCents, locale)} €`)}
                    {item.priceSuffix ? ` ${item.priceSuffix}` : ""}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-4">
                  <div className="flex items-center rounded-lg border border-[var(--color-border)]">
                    <button type="button" className="px-2 py-1 text-sm" onClick={() => changeQuantity(item.setQuantity, item.quantity, -1)}>-</button>
                    <span className="min-w-8 px-2 text-center text-sm tabular-nums">{item.quantity}</span>
                    <button type="button" className="px-2 py-1 text-sm" onClick={() => changeQuantity(item.setQuantity, item.quantity, 1)}>+</button>
                  </div>
                  <span className="min-w-24 text-right text-sm font-medium text-[var(--color-foreground)]">
                    {formatEuroFromCents(item.totalCents, locale)} € {t("traffic.taxSuffix")}
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
                {formatEuroFromCents(totalCents, locale)} € {t("traffic.taxSuffix")}
              </span>
            </div>
            <Button
              type="button"
              fullWidth
              className="mt-3"
              disabled={selectedItems.length === 0}
              onClick={() => onCheckout(checkoutItemsParam)}
            >
              {t("traffic.expandPay")}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
