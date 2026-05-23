import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview, type BillingCatalogEntry } from "../../billing/hooks/useBilling";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import PageHeader from "../../../components/ui/PageHeader";

function localeTag(locale: string): string {
  if (locale === "en") return "en-GB";
  if (locale === "es") return "es-ES";
  return "hu-HU";
}

function numberValue(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function percentValue(used: number, total: number): number {
  if (total <= 0) return 0;
  return Math.max(0, Math.min((used / total) * 100, 100));
}

function formatNumber(value: number, locale: string): string {
  return value.toLocaleString(localeTag(locale));
}

function formatCharsAsK(value: number, locale: string): string {
  const normalized = Math.max(0, Number(value || 0));
  const inThousands = normalized / 1000;
  const whole = Math.round(inThousands * 10) % 10 === 0;
  const formatted = inThousands.toLocaleString(
    localeTag(locale),
    whole ? { maximumFractionDigits: 0 } : { maximumFractionDigits: 1 }
  );
  return `${formatted}K`;
}

function formatEuroFromCents(cents: number, locale: string): string {
  const value = cents / 100;
  const whole = Math.round(value * 100) % 100 === 0;
  return value.toLocaleString(localeTag(locale), whole ? { maximumFractionDigits: 0 } : { maximumFractionDigits: 2 });
}

function formatDate(value: string | undefined, locale: string): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(localeTag(locale), { dateStyle: "long" });
}

function getUsageStatus(
  percent: number,
  t: (key: string) => string
): { tone: string; title: string; description: string } {
  if (percent >= 90) {
    return {
      tone: "alert-error",
      title: t("traffic.statusHighTitle"),
      description: t("traffic.statusHighDescription"),
    };
  }
  if (percent >= 60) {
    return {
      tone: "alert-warning",
      title: t("traffic.statusMediumTitle"),
      description: t("traffic.statusMediumDescription"),
    };
  }
  return {
    tone: "alert-success",
    title: t("traffic.statusLowTitle"),
    description: t("traffic.statusLowDescription"),
  };
}

function getResourceHint(percent: number, fullHint: string, lowHint: string): string {
  return percent >= 100 ? fullHint : lowHint;
}

function addonEntry(catalog: BillingCatalogEntry[], code: string): BillingCatalogEntry | null {
  return catalog.find((item) => item.entry_type === "addon" && item.code === code) ?? null;
}

function includedNumber(entry: BillingCatalogEntry | null, key: string, fallback: number): number {
  const raw = entry?.included && typeof entry.included === "object" ? entry.included[key] : null;
  const parsed = Number(raw ?? fallback);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export default function TrafficPage() {
  const { t, locale } = useTranslation();
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const { data: billingOverview, isLoading, error: billingError } = useBillingOverview();
  const [showQuestionsByUser, setShowQuestionsByUser] = useState(false);
  const [expandModalOpen, setExpandModalOpen] = useState(false);
  const [storageQuantity, setStorageQuantity] = useState(0);
  const [trainingQuantity, setTrainingQuantity] = useState(0);
  const [question100Quantity, setQuestion100Quantity] = useState(0);
  const [question500Quantity, setQuestion500Quantity] = useState(0);

  const billingErrMsg =
    billingError && typeof (billingError as { response?: { data?: { detail?: string } } })?.response?.data?.detail === "string"
      ? (billingError as { response?: { data?: { detail?: string } } }).response!.data!.detail
      : billingError
        ? t("common.errorGeneric")
        : null;

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

  const usage = billingOverview?.usage ?? {};
  const limits = billingOverview?.limits ?? {};
  const catalog = billingOverview?.catalog ?? [];
  const subscription = billingOverview?.subscription ?? {};
  const currentPlanCode = String(subscription.plan_code ?? "free");
  const showExpandButton = currentPlanCode !== "free";
  const nextPeriodStartLabel = formatDate(billingOverview?.current_period_end_iso, locale);
  const questions = (usage.questions as Record<string, unknown>) ?? {};
  const training = (usage.training as Record<string, unknown>) ?? {};
  const resources = (usage.resources as Record<string, unknown>) ?? {};
  const questionsByUser = Array.isArray(usage.questions_by_user)
    ? (usage.questions_by_user as Array<Record<string, unknown>>)
    : [];
  const usedQuestions = numberValue(questions.used_total);
  const totalQuestions = numberValue(questions.available_total);
  const knowledgeBasesUsed = numberValue(resources.knowledge_bases);
  const knowledgeBasesTotal = numberValue(limits.knowledge_bases);
  const storageUsed = numberValue(resources.storage_gb_used_rounded ?? training.storage_gb_used_rounded);
  const storageTotal = numberValue(limits.storage_gb);
  const trainingUsed = numberValue(training.trained_chars);
  const trainingTotal = numberValue(training.available_training_chars ?? limits.training_chars_available);
  const usersUsed = numberValue(resources.users);
  const usersTotal = limits.max_users == null ? null : numberValue(limits.max_users);
  const questionPercent = percentValue(usedQuestions, totalQuestions);
  const kbPercent = percentValue(knowledgeBasesUsed, knowledgeBasesTotal);
  const storagePercent = percentValue(storageUsed, storageTotal);
  const trainingPercent = percentValue(trainingUsed, trainingTotal);
  const usersPercent = usersTotal == null ? 0 : percentValue(usersUsed, usersTotal);
  const status = getUsageStatus(questionPercent, t);
  const storageAddon = addonEntry(catalog, "extra_storage_gb");
  const trainingAddon = addonEntry(catalog, "training_extra_500k");
  const question100Addon = addonEntry(catalog, "question_pack_100");
  const question500Addon = addonEntry(catalog, "question_pack_500");
  const storageUnitGb = includedNumber(storageAddon, "storage_gb", 1);
  const trainingUnitChars = includedNumber(trainingAddon, "training_chars", 500000);
  const question100Count = includedNumber(question100Addon, "questions", 100);
  const question500Count = includedNumber(question500Addon, "questions", 500);
  const storageUnitPriceCents = numberValue(storageAddon?.price_cents);
  const trainingUnitPriceCents = numberValue(trainingAddon?.price_cents);
  const question100PriceCents = numberValue(question100Addon?.price_cents);
  const question500PriceCents = numberValue(question500Addon?.price_cents);
  const storageTotalPriceCents = storageUnitPriceCents * storageQuantity;
  const trainingTotalPriceCents = trainingUnitPriceCents * trainingQuantity;
  const question100TotalPriceCents = question100PriceCents * question100Quantity;
  const question500TotalPriceCents = question500PriceCents * question500Quantity;
  const expansionTotalPriceCents =
    trainingTotalPriceCents + storageTotalPriceCents + question100TotalPriceCents + question500TotalPriceCents;
  const changeQuantity = (setter: (value: number) => void, current: number, delta: number) => {
    setter(Math.max(0, Math.min(99, current + delta)));
  };
  const expansionOptions = [
    {
      addonCode: "training_extra_500k",
      title: t("packages.expandTrainingTitle").replace("{{chars}}", formatCharsAsK(trainingUnitChars, locale)),
      unitLabel: `${formatCharsAsK(trainingUnitChars, locale)} ${t("traffic.expandCharactersUnit")}`,
      unitPriceCents: trainingUnitPriceCents,
      quantity: trainingQuantity,
      setQuantity: setTrainingQuantity,
      amountLabel: `${formatCharsAsK(trainingUnitChars * trainingQuantity, locale)} ${t("traffic.expandCharactersUnit")}`,
      totalCents: trainingTotalPriceCents,
    },
    {
      addonCode: "extra_storage_gb",
      title: t("packages.expandStorageTitle").replace("{{gb}}", String(storageUnitGb)),
      unitLabel: `${formatNumber(storageUnitGb, locale)} GB`,
      unitPriceCents: storageUnitPriceCents,
      priceSuffix: `/ ${t("packages.perMonthSuffix")}`,
      quantity: storageQuantity,
      setQuantity: setStorageQuantity,
      amountLabel: `${formatNumber(storageUnitGb * storageQuantity, locale)} GB`,
      totalCents: storageTotalPriceCents,
    },
    {
      addonCode: "question_pack_100",
      title: t("packages.expandQuestionsTitle").replace("{{count}}", String(question100Count)),
      unitLabel: `${formatNumber(question100Count, locale)} ${t("traffic.questionsByUserCount").toLowerCase()}`,
      unitPriceCents: question100PriceCents,
      quantity: question100Quantity,
      setQuantity: setQuestion100Quantity,
      amountLabel: `${formatNumber(question100Count * question100Quantity, locale)} ${t("traffic.questionsByUserCount").toLowerCase()}`,
      totalCents: question100TotalPriceCents,
    },
    {
      addonCode: "question_pack_500",
      title: t("packages.expandQuestionsTitle").replace("{{count}}", String(question500Count)),
      unitLabel: `${formatNumber(question500Count, locale)} ${t("traffic.questionsByUserCount").toLowerCase()}`,
      unitPriceCents: question500PriceCents,
      quantity: question500Quantity,
      setQuantity: setQuestion500Quantity,
      amountLabel: `${formatNumber(question500Count * question500Quantity, locale)} ${t("traffic.questionsByUserCount").toLowerCase()}`,
      totalCents: question500TotalPriceCents,
    },
  ];
  const selectedExpansionItems = expansionOptions.filter((item) => item.quantity > 0);
  const checkoutItemsParam = selectedExpansionItems
    .map((item) => `${item.addonCode}:${item.quantity}`)
    .join(",");
  const stats = [
    {
      title: t("traffic.usageKnowledgeBases"),
      value: `${knowledgeBasesUsed} / ${knowledgeBasesTotal}`,
      percent: kbPercent,
      hint: getResourceHint(kbPercent, t("traffic.kbHintFull"), t("traffic.kbHintAvailable")),
    },
    {
      title: t("traffic.usageStorage"),
      value: `${formatNumber(storageUsed, locale)} / ${formatNumber(storageTotal, locale)} GB`,
      percent: storagePercent,
      hint: getResourceHint(storagePercent, t("traffic.storageHintFull"), t("traffic.storageHintAvailable")),
    },
    {
      title: t("traffic.usageTrainingChars"),
      value: `${formatCharsAsK(trainingUsed, locale)} / ${formatCharsAsK(trainingTotal, locale)}`,
      percent: trainingPercent,
      hint: getResourceHint(trainingPercent, t("traffic.trainingHintFull"), t("traffic.trainingHintAvailable")),
    },
    {
      title: t("traffic.usageUsers"),
      value: `${usersUsed} / ${usersTotal == null ? t("traffic.unlimited") : usersTotal}`,
      percent: usersTotal == null ? 20 : usersPercent,
      hint: usersTotal == null ? t("traffic.usersUnlimitedHint") : t("traffic.usersAddonHint"),
    },
  ];

  return (
    <div className="app-page">
      <div className="app-page-container">
        <PageHeader
          eyebrow={t("nav.traffic")}
          title={t("traffic.overviewLabel")}
          description={t("traffic.currentPeriodUsage")}
          actions={
            <Button variant="secondary" onClick={() => navigate("/admin/csomagok")}>
              {t("nav.packages")}
            </Button>
          }
        />

        {billingErrMsg ? (
          <Alert tone="error">{billingErrMsg}</Alert>
        ) : null}

        <section className="app-surface p-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--color-muted)]">{t("traffic.questionsThisMonth")}</p>
              <div className="mt-2 flex flex-wrap items-end gap-3">
                <span className="text-4xl font-semibold tracking-tight text-[var(--color-foreground)]">{formatNumber(usedQuestions, locale)}</span>
                <span className="pb-1 text-base text-[var(--color-muted)]">/ {formatNumber(totalQuestions, locale)}</span>
              </div>
            </div>

            <div className={`alert-base rounded-2xl px-3 py-2 text-left md:text-right ${status.tone}`}>
              <p className="text-xs font-medium uppercase tracking-wide">{status.title}</p>
              <p className="mt-1 text-sm">{status.description}</p>
            </div>
          </div>

          <div className="mt-6">
            <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--color-card-muted)]">
              <div className="h-full rounded-full bg-[var(--color-accent)] transition-all" style={{ width: `${questionPercent}%` }} />
            </div>
            <div className="mt-3 flex flex-col gap-2 text-sm text-[var(--color-muted)] sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <span>{t("traffic.usedPercentLabel").replace("{{count}}", String(Math.round(questionPercent)))}</span>
                <Button
                  type="button"
                  onClick={() => setShowQuestionsByUser((v) => !v)}
                  aria-expanded={showQuestionsByUser}
                  variant="ghost"
                  size="sm"
                  className="px-1 py-0 text-xs font-medium text-[var(--color-muted-foreground)] hover:bg-transparent hover:text-[var(--color-foreground)] hover:underline"
                >
                  {t("traffic.questionsByUserShow")} {showQuestionsByUser ? "↑" : "↓"}
                </Button>
              </div>
              <span>
                {t("traffic.nextPeriodStart")}:{" "}
                <span className="font-medium text-[var(--color-foreground)]">{nextPeriodStartLabel}</span>
              </span>
            </div>

            {showQuestionsByUser ? (
              <div className="app-table-wrap mt-4">
                <table className="w-full text-sm">
                  <thead className="app-table-head">
                    <tr>
                      <th className="p-3 text-left font-medium">{t("traffic.questionsByUserName")}</th>
                      <th className="hidden p-3 text-left font-medium sm:table-cell">
                        {t("traffic.questionsByUserEmail")}
                      </th>
                      <th className="p-3 text-right font-medium">{t("traffic.questionsByUserCount")}</th>
                    </tr>
                  </thead>
                  <tbody className="bg-[var(--color-card)]">
                    {questionsByUser.length === 0 ? (
                      <tr className="border-t border-[var(--color-border)]">
                        <td className="p-3 text-[var(--color-muted)]" colSpan={3}>
                          {t("traffic.questionsByUserEmpty")}
                        </td>
                      </tr>
                    ) : (
                      questionsByUser.map((item) => (
                        <tr key={String(item.user_id)} className="border-t border-[var(--color-border)]">
                          <td className="p-3 text-[var(--color-foreground)]">{String(item.name ?? "—")}</td>
                          <td className="hidden p-3 text-[var(--color-muted)] sm:table-cell">{String(item.email ?? "")}</td>
                          <td className="p-3 text-right tabular-nums text-[var(--color-foreground)]">{String(item.question_count ?? 0)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        </section>

        <section className="app-surface p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">{t("traffic.resourcesTitle")}</h2>
            </div>
            {showExpandButton ? (
              <Button type="button" variant="secondary" onClick={() => setExpandModalOpen(true)}>
                {t("traffic.expandPackages")}
              </Button>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {stats.map((item) => (
              <div key={item.title} className="app-surface-muted p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-[var(--color-muted)]">{item.title}</p>
                    <p className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">{item.value}</p>
                  </div>
                  <div className="rounded-xl bg-[var(--color-card)] px-2 py-1 text-xs font-medium text-[var(--color-muted-foreground)]">
                    {Math.round(item.percent)}%
                  </div>
                </div>

                <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-[var(--color-card)]">
                  <div
                    className="h-full rounded-full bg-[var(--color-primary)]"
                    style={{ width: `${Math.min(item.percent, 100)}%` }}
                  />
                </div>

                <p className="mt-3 text-sm leading-5 text-[var(--color-muted)]">{item.hint}</p>
              </div>
            ))}
          </div>

        </section>

        {expandModalOpen && showExpandButton ? (
          <div
            className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4"
            role="presentation"
            onClick={() => setExpandModalOpen(false)}
          >
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
                  onClick={() => setExpandModalOpen(false)}
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
                      {formatEuroFromCents(expansionTotalPriceCents, locale)} € {t("traffic.taxSuffix")}
                    </span>
                  </div>
                  <Button
                    type="button"
                    fullWidth
                    className="mt-3"
                    disabled={selectedExpansionItems.length === 0}
                    onClick={() => {
                      setExpandModalOpen(false);
                      navigate(`/admin/csomagok/bovites-fizetes?items=${encodeURIComponent(checkoutItemsParam)}`);
                    }}
                  >
                    {t("traffic.expandPay")}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
