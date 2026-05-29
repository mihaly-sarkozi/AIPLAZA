type ChatBillingRestrictionPanelProps = {
  freeTrialExpired: boolean;
  canManageBilling: boolean;
  t: (key: string) => string;
};

export default function ChatBillingRestrictionPanel({ freeTrialExpired, canManageBilling, t }: ChatBillingRestrictionPanelProps) {
  return (
    <div className="flex-1 bg-[var(--color-background)] px-6 py-10 text-[var(--color-foreground)]">
      <div className="mx-auto flex min-h-[60vh] max-w-lg items-center justify-center text-center">
        <div className="rounded-3xl border border-[var(--color-danger-border)] bg-[var(--color-danger-bg)] p-8 text-[var(--color-danger-text)] shadow-sm">
          <h1 className="text-2xl font-semibold">
            {freeTrialExpired ? t("billing.chatUnavailableTrialExpired") : t("billing.chatUnavailablePayment")}
          </h1>
          {freeTrialExpired ? (
            <>
              <p className="mt-3 text-sm leading-relaxed">{t("billing.chatUnavailableTrialExpiredHint")}</p>
              {canManageBilling ? (
                <a
                  href="/admin/pricing"
                  className="mt-5 inline-flex rounded-xl bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[var(--color-on-primary)] hover:opacity-90"
                >
                  {t("billing.choosePackageCta")}
                </a>
              ) : null}
            </>
          ) : canManageBilling ? (
            <a
              href="/admin/szamlak/kiegyenlites"
              className="mt-5 inline-flex rounded-xl bg-[var(--color-primary)] px-4 py-2 text-sm font-semibold text-[var(--color-on-primary)] hover:opacity-90"
            >
              {t("billing.settlePayment")}
            </a>
          ) : (
            <p className="mt-3 text-sm leading-relaxed">{t("billing.systemUnavailablePaymentHint")}</p>
          )}
        </div>
      </div>
    </div>
  );
}
