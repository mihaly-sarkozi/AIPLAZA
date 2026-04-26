import { useTranslation } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { useBillingOverview } from "../../billing/hooks/useBilling";
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

export default function TrafficPage() {
  const { t, locale } = useTranslation();
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const { data: billingOverview, isLoading, error: billingError } = useBillingOverview();
  const [showQuestionsByUser, setShowQuestionsByUser] = useState(false);

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
  const periodKey = billingOverview?.current_period_key ?? "—";
  const questions = (usage.questions as Record<string, unknown>) ?? {};
  const training = (usage.training as Record<string, unknown>) ?? {};
  const resources = (usage.resources as Record<string, unknown>) ?? {};
  const questionsByUser = Array.isArray(usage.questions_by_user)
    ? (usage.questions_by_user as Array<Record<string, unknown>>)
    : [];
  const usedQuestions = numberValue(questions.used_total);
  const totalQuestions = numberValue(questions.available_total);
  const packageRemaining = numberValue(questions.remaining_included);
  const addonRemaining = numberValue(questions.remaining_addons);
  const knowledgeBasesUsed = numberValue(resources.knowledge_bases);
  const knowledgeBasesTotal = numberValue(limits.knowledge_bases);
  const storageUsed = numberValue(training.storage_gb_used_rounded);
  const storageTotal = numberValue(limits.storage_gb);
  const trainingUsed = numberValue(training.trained_chars);
  const trainingTotal = numberValue(training.available_training_chars);
  const usersUsed = numberValue(resources.users);
  const usersTotal = limits.max_users == null ? null : numberValue(limits.max_users);
  const questionPercent = percentValue(usedQuestions, totalQuestions);
  const kbPercent = percentValue(knowledgeBasesUsed, knowledgeBasesTotal);
  const storagePercent = percentValue(storageUsed, storageTotal);
  const trainingPercent = percentValue(trainingUsed, trainingTotal);
  const usersPercent = usersTotal == null ? 0 : percentValue(usersUsed, usersTotal);
  const status = getUsageStatus(questionPercent, t);
  const topResourcePercent = Math.max(kbPercent, storagePercent, trainingPercent, usersPercent);
  const recommendationTitle =
    kbPercent >= 100
      ? t("traffic.recommendationTitleKbFull")
      : usersTotal != null && usersPercent >= 100
        ? t("traffic.recommendationTitleUsersFull")
        : topResourcePercent >= 80
          ? t("traffic.recommendationTitleWatch")
          : t("traffic.recommendationTitleStable");
  const recommendationText =
    kbPercent >= 100
      ? t("traffic.recommendationTextKbFull")
      : usersTotal != null && usersPercent >= 100
        ? t("traffic.recommendationTextUsersFull")
        : topResourcePercent >= 80
          ? t("traffic.recommendationTextWatch")
          : t("traffic.recommendationTextStable");
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
      value: `${formatNumber(trainingUsed, locale)} / ${formatNumber(trainingTotal, locale)}`,
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
          eyebrow={t("traffic.overviewLabel")}
          title={t("traffic.currentUsageTitle")}
          description={
            <>
              {t("traffic.usageIntro")} {t("traffic.billingPeriodLabel").toLowerCase()}:{" "}
              <span className="font-medium text-[var(--color-foreground)]">{periodKey}</span>
            </>
          }
          actions={
            <>
              <Button variant="secondary" onClick={() => navigate("/admin/csomagok")}>
                {t("nav.packages")}
              </Button>
              <Button onClick={() => navigate("/admin/megrendeles")}>{t("nav.orders")}</Button>
            </>
          }
        />

        {billingErrMsg ? (
          <Alert tone="error">{billingErrMsg}</Alert>
        ) : null}

        <div className="grid gap-6 lg:grid-cols-[1.4fr_0.9fr]">
          <section className="app-surface p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-[var(--color-muted)]">{t("traffic.usageQuestions")}</p>
                <div className="mt-2 flex flex-wrap items-end gap-3">
                  <span className="text-4xl font-semibold tracking-tight text-[var(--color-foreground)]">{formatNumber(usedQuestions, locale)}</span>
                  <span className="pb-1 text-base text-[var(--color-muted)]">/ {formatNumber(totalQuestions, locale)}</span>
                </div>
              </div>

              <div className={`alert-base rounded-2xl px-3 py-2 text-right ${status.tone}`}>
                <p className="text-xs font-medium uppercase tracking-wide">{status.title}</p>
                <p className="mt-1 text-sm">{status.description}</p>
              </div>
            </div>

            <div className="mt-6">
              <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--color-card-muted)]">
                <div className="h-full rounded-full bg-[var(--color-accent)] transition-all" style={{ width: `${questionPercent}%` }} />
              </div>
              <div className="mt-3 flex flex-col gap-1 text-sm text-[var(--color-muted)] sm:flex-row sm:items-center sm:justify-between">
                <span>{t("traffic.usedPercentLabel").replace("{{count}}", String(Math.round(questionPercent)))}</span>
                <span>
                  {t("traffic.questionsRemainingTotalLabel").replace(
                    "{{count}}",
                    formatNumber(Math.max(totalQuestions - usedQuestions, 0), locale)
                  )}
                </span>
              </div>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className="app-surface-muted p-4">
                <p className="text-sm text-[var(--color-muted)]">{t("traffic.usageQuestionsIncludedLeft")}</p>
                <p className="mt-1 text-2xl font-semibold text-[var(--color-foreground)]">{formatNumber(packageRemaining, locale)}</p>
              </div>
              <div className="app-surface-muted p-4">
                <p className="text-sm text-[var(--color-muted)]">{t("traffic.usageQuestionsAddonLeft")}</p>
                <p className="mt-1 text-2xl font-semibold text-[var(--color-foreground)]">{formatNumber(addonRemaining, locale)}</p>
              </div>
            </div>
          </section>

          <aside className="rounded-3xl border border-[var(--color-border)] bg-[var(--color-card-strong)] p-6 text-[var(--color-on-primary)] shadow-sm">
            <p className="text-sm font-medium opacity-70">{t("traffic.recommendationLabel")}</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">{recommendationTitle}</h2>
            <p className="mt-3 text-sm leading-6 opacity-80">{recommendationText}</p>

            <div className="mt-6 rounded-2xl border border-white/10 bg-white/10 p-4">
              <p className="text-sm opacity-80">{t("traffic.highlightLabel")}</p>
              <p className="mt-1 font-medium">
                {kbPercent >= 100 ? t("traffic.kbWarningFull") : t("traffic.ordersPageHint")}
              </p>
            </div>

            <Button
              onClick={() => navigate("/admin/csomagok")}
              variant="secondary"
              size="lg"
              fullWidth
              className="mt-6 bg-[var(--color-on-primary)] text-[var(--color-card-strong)]"
            >
              {t("nav.packages")}
            </Button>
          </aside>
        </div>

        <section className="app-surface p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-medium text-[var(--color-muted)]">{t("traffic.questionsByUserShow")}</p>
              <h2 className="mt-1 text-xl font-semibold text-[var(--color-foreground)]">{t("traffic.resourcesTitle")}</h2>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="badge-soft">
                {t("traffic.liveSummaryLabel")}
              </div>
              <Button
                type="button"
                onClick={() => setShowQuestionsByUser((v) => !v)}
                aria-expanded={showQuestionsByUser}
                variant="secondary"
                size="sm"
              >
                {showQuestionsByUser ? t("traffic.questionsByUserHide") : t("traffic.questionsByUserShow")}
              </Button>
            </div>
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

          {showQuestionsByUser ? (
            <div className="app-table-wrap mt-6">
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
        </section>

        <section className="rounded-3xl border border-amber-200 bg-amber-50 p-5">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-amber-800">{t("traffic.importantInfoTitle")}</h3>
          <p className="mt-2 text-sm leading-6 text-amber-900">{t("traffic.usersAddonHint")} {t("traffic.ordersPageHint")}</p>
        </section>
      </div>
    </div>
  );
}
