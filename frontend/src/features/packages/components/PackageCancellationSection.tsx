import { useMemo, useState } from "react";

const CANCELLATION_REASONS = [
  "too_expensive",
  "not_using",
  "not_satisfied",
  "missing_features",
  "other",
] as const;

type PackageCancellationSectionProps = {
  activeKnowledgeBaseCount: number;
  autoRenewal: boolean;
  cancellationRequest: Record<string, unknown> | null;
  validUntilLabel: string;
  currentHost: string;
  locale: string;
  t: (key: string) => string;
  cancelPending: boolean;
  restorePending: boolean;
  deletePending: boolean;
  errorMessage: string | null;
  onCancel: (body: { reason_code: string; reason_text: string }) => void;
  onRestoreRenewal: () => void;
  onDeleteAccess: () => void;
  onOpenKnowledgeBases: () => void;
};

export default function PackageCancellationSection({
  activeKnowledgeBaseCount,
  autoRenewal,
  cancellationRequest,
  validUntilLabel,
  currentHost,
  locale,
  t,
  cancelPending,
  restorePending,
  deletePending,
  errorMessage,
  onCancel,
  onRestoreRenewal,
  onDeleteAccess,
  onOpenKnowledgeBases,
}: PackageCancellationSectionProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedReasonCodes, setSelectedReasonCodes] = useState<(typeof CANCELLATION_REASONS)[number][]>(["too_expensive"]);
  const [reasonText, setReasonText] = useState("");
  const [confirmationText, setConfirmationText] = useState("");
  const hasActiveKnowledgeBases = activeKnowledgeBaseCount > 0;
  const alreadyRequested = cancellationRequest != null || !autoRenewal;
  const confirmationTenantName = useMemo(() => {
    const rawHost = (currentHost || "").trim();
    if (!rawHost) return "";
    const firstDot = rawHost.indexOf(".");
    if (firstDot <= 0) return rawHost;
    return rawHost.slice(0, firstDot);
  }, [currentHost]);
  const normalizedConfirmation = confirmationText.trim().toLocaleLowerCase(locale);
  const normalizedTenantName = confirmationTenantName.trim().toLocaleLowerCase(locale);
  const confirmationAccepted = normalizedConfirmation.length > 0 && normalizedTenantName.length > 0 && normalizedConfirmation === normalizedTenantName;

  return (
    <section className="w-full max-w-6xl mx-auto mb-6 px-2">
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <p className="text-[var(--color-muted)]">
              {t("packages.cancellationRenewalStatusLabel")}{" "}
              <span className="font-semibold text-[var(--color-foreground)]">
                {alreadyRequested ? t("packages.cancellationStatusRequested") : t("packages.cancellationStatusActive")}
              </span>
              <span className="text-[var(--color-muted)]">
                {" "}
                ({alreadyRequested ? t("packages.cancellationRenewalTitleDisabled") : t("packages.cancellationRenewalTitle")})
              </span>
            </p>
            <p className="text-[var(--color-muted)]">
              {t("packages.cancellationValidUntilPrefix")}{" "}
              <span className="font-semibold text-[var(--color-foreground)]">{validUntilLabel}</span>
            </p>
            <p className="max-w-2xl text-[var(--color-muted)]">
              {t("packages.cancellationInfoText")}
            </p>
            {alreadyRequested && hasActiveKnowledgeBases ? (
              <p className="max-w-2xl text-amber-900 dark:text-amber-200">
                {t("packages.cancellationDeleteKbBlockMessage").replace("{{count}}", String(activeKnowledgeBaseCount))}
              </p>
            ) : null}
            {errorMessage ? <p className="text-sm text-red-600 dark:text-red-400">{errorMessage}</p> : null}
          </div>
          <div className="flex shrink-0 flex-col gap-2 md:min-w-56">
            {alreadyRequested ? (
              <>
                <button
                  type="button"
                  disabled={restorePending || deletePending}
                  onClick={onRestoreRenewal}
                  className="rounded-lg px-4 py-2.5 text-sm font-semibold border border-[var(--color-border)] bg-[var(--color-card)] text-[var(--color-foreground)] hover:bg-[var(--color-border)]/25 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {restorePending ? t("packages.cancellationRestorePending") : t("packages.cancellationRestoreBillingButton")}
                </button>
                <button
                  type="button"
                  disabled={deletePending || restorePending || hasActiveKnowledgeBases}
                  onClick={onDeleteAccess}
                  className="rounded-lg px-4 py-2.5 text-sm font-semibold bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deletePending ? t("packages.cancellationDeletePending") : t("packages.cancellationDeleteServiceButton")}
                </button>
                {hasActiveKnowledgeBases ? (
                  <button
                    type="button"
                    onClick={onOpenKnowledgeBases}
                    className="rounded-lg px-4 py-2.5 text-sm font-semibold bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
                  >
                    {t("packages.cancellationOpenKnowledgeBases")}
                  </button>
                ) : null}
              </>
            ) : (
              <button
                type="button"
                disabled={cancelPending}
                onClick={() => setDialogOpen(true)}
                className="px-1 py-1 text-sm font-semibold underline underline-offset-2 text-[var(--color-primary)] hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {t("packages.cancellationAutoRenewalLink")}
              </button>
            )}
          </div>
        </div>
      </div>

      {dialogOpen ? (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/40 px-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-xl">
            <h3 className="text-lg font-semibold mb-3">{t("packages.cancellationReasonTitle")}</h3>
            <div className="space-y-2">
              {CANCELLATION_REASONS.map((reason) => (
                <label key={reason} className="flex items-start gap-3 text-sm leading-5">
                  <input
                    type="checkbox"
                    checked={selectedReasonCodes.includes(reason)}
                    onChange={(event) => {
                      setSelectedReasonCodes((prev) => {
                        if (event.target.checked) {
                          if (prev.includes(reason)) return prev;
                          return [...prev, reason];
                        }
                        const next = prev.filter((item) => item !== reason);
                        return next;
                      });
                    }}
                    className="shrink-0"
                    style={{ width: "auto" }}
                  />
                  <span>{t(`packages.cancellationReason_${reason}`)}</span>
                </label>
              ))}
            </div>
            <label className="mt-4 block text-sm">
              <span className="text-[var(--color-muted)]">{t("packages.cancellationFeedbackLabel")}</span>
              <textarea
                value={reasonText}
                onChange={(event) => setReasonText(event.target.value.slice(0, 2000))}
                className="mt-1 min-h-28 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
              />
            </label>
            <label className="mt-4 block text-sm">
              <span className="text-[var(--color-muted)]">
                {t("packages.cancellationConfirmTypeLabel")}{" "}
                <span className="font-semibold text-[var(--color-foreground)]">{confirmationTenantName}</span>
              </span>
              <input
                type="text"
                value={confirmationText}
                onChange={(event) => setConfirmationText(event.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                autoComplete="off"
              />
            </label>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                disabled={cancelPending}
                onClick={() => {
                  setConfirmationText("");
                  setDialogOpen(false);
                }}
                className="rounded-lg px-3 py-2 text-sm font-medium border border-[var(--color-border)] hover:bg-[var(--color-border)]/25 disabled:opacity-50"
              >
                {t("common.cancel")}
              </button>
              <button
                type="button"
                disabled={cancelPending || !confirmationAccepted || selectedReasonCodes.length === 0}
                onClick={() => {
                  const primaryReasonCode = selectedReasonCodes[0] ?? "other";
                  const reasonCodesSummary = selectedReasonCodes.join(",");
                  const normalizedReasonText = reasonText.trim();
                  const combinedReasonText =
                    normalizedReasonText.length > 0
                      ? `[selected:${reasonCodesSummary}] ${normalizedReasonText}`
                      : `[selected:${reasonCodesSummary}]`;
                  onCancel({ reason_code: primaryReasonCode, reason_text: combinedReasonText });
                  setConfirmationText("");
                  setSelectedReasonCodes(["too_expensive"]);
                  setDialogOpen(false);
                }}
                className="rounded-lg px-3 py-2 text-sm font-semibold bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {cancelPending ? t("packages.cancellationPending") : t("packages.cancellationConfirmButton")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
