import Button from "../../../components/ui/Button";
import type { BillingCatalogEntry } from "../../billing/hooks/useBilling";

type PlanChangePending = { planCode: string; billingPeriod: string };
type PlanChangeSuccess = { message: string; status: string };

type PackageStatusModalsProps = {
  planChangePending: PlanChangePending | null;
  planChangeSuccess: PlanChangeSuccess | null;
  resourceBlockMessage: string | null;
  showAuthenticatorRequiredModal: boolean;
  pendingTargetPlan: BillingCatalogEntry | null;
  pendingBilledPhrase: string;
  pendingIsDowngrade: boolean;
  updatePending: boolean;
  t: (key: string) => string;
  onClosePending: () => void;
  onConfirmPlanChange: () => void;
  onCloseSuccess: () => void;
  onCloseResourceBlock: () => void;
  onCloseAuthenticatorRequired: () => void;
  onOpenSettings: () => void;
};

export default function PackageStatusModals({
  planChangePending,
  planChangeSuccess,
  resourceBlockMessage,
  showAuthenticatorRequiredModal,
  pendingTargetPlan,
  pendingBilledPhrase,
  pendingIsDowngrade,
  updatePending,
  t,
  onClosePending,
  onConfirmPlanChange,
  onCloseSuccess,
  onCloseResourceBlock,
  onCloseAuthenticatorRequired,
  onOpenSettings,
}: PackageStatusModalsProps) {
  return (
    <>
      {planChangePending ? (
        <BasicDialog
          zIndex="z-[85]"
          titleId="packages-change-confirm-title"
          title={t("packages.changeConfirmTitle")}
          onClose={() => {
            if (!updatePending) onClosePending();
          }}
          footer={
            <>
              <button
                type="button"
                className="rounded-lg px-3 py-2 text-sm font-medium border border-[var(--color-border)] text-[var(--color-foreground)] hover:bg-[var(--color-border)]/25 disabled:opacity-50"
                disabled={updatePending}
                onClick={onClosePending}
              >
                {t("packages.changeConfirmCancel")}
              </button>
              <button
                type="button"
                className="rounded-lg px-3 py-2 text-sm font-semibold bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90 disabled:opacity-50"
                disabled={updatePending}
                onClick={onConfirmPlanChange}
              >
                {updatePending ? t("common.loading") : t("packages.changeConfirmOk")}
              </button>
            </>
          }
        >
          <p>
            {t("packages.changeConfirmIntro")
              .replace("{{plan}}", pendingTargetPlan?.name ?? planChangePending.planCode)
              .replace("{{billed}}", pendingBilledPhrase)
              .replace("{{when}}", pendingIsDowngrade ? t("packages.changeConfirmWhenScheduled") : t("packages.changeConfirmWhenImmediate"))}
          </p>
        </BasicDialog>
      ) : null}

      {planChangeSuccess ? (
        <BasicDialog
          zIndex="z-[85]"
          titleId="packages-change-success-title"
          title={t("packages.changeSuccessTitle")}
          onClose={onCloseSuccess}
          footer={
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-sm font-semibold bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
              onClick={onCloseSuccess}
            >
              {t("packages.changeSuccessClose")}
            </button>
          }
        >
          <div className="whitespace-pre-wrap">{planChangeSuccess.message}</div>
        </BasicDialog>
      ) : null}

      {resourceBlockMessage ? (
        <BasicDialog
          zIndex="z-[86]"
          titleId="packages-resource-block-title"
          title={t("packages.planBlockedModalTitle")}
          onClose={onCloseResourceBlock}
          footer={
            <button
              type="button"
              className="rounded-lg px-3 py-2 text-sm font-semibold bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90"
              onClick={onCloseResourceBlock}
            >
              {t("packages.changeSuccessClose")}
            </button>
          }
        >
          <div className="whitespace-pre-wrap">{resourceBlockMessage}</div>
        </BasicDialog>
      ) : null}

      {showAuthenticatorRequiredModal ? (
        <BasicDialog
          zIndex="z-[87]"
          titleId="packages-authenticator-required-title"
          title="Authenticator szükséges az előfizetéshez"
          onClose={onCloseAuthenticatorRequired}
          footer={
            <>
              <Button type="button" variant="secondary" onClick={onCloseAuthenticatorRequired}>
                Később
              </Button>
              <Button type="button" onClick={onOpenSettings}>
                Authenticator beállítása
              </Button>
            </>
          }
        >
          <p>
            A próbaidőszak alatt a kétfaktoros hitelesítés opcionális, de előfizetés indításához kötelező a Google Authenticator
            aktiválása.
          </p>
        </BasicDialog>
      ) : null}
    </>
  );
}

function BasicDialog({
  zIndex,
  titleId,
  title,
  children,
  footer,
  onClose,
}: {
  zIndex: string;
  titleId: string;
  title: string;
  children: React.ReactNode;
  footer: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className={`fixed inset-0 ${zIndex} flex items-center justify-center p-4 bg-black/40`} role="presentation" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-xl max-w-md w-full shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="px-4 py-4 border-b border-[var(--color-border)]">
          <h2 id={titleId} className="text-base font-semibold text-[var(--color-foreground)]">
            {title}
          </h2>
        </div>
        <div className="px-4 py-4 text-sm text-[var(--color-foreground)] leading-relaxed">{children}</div>
        <div className="px-4 pb-4 flex flex-wrap gap-2 justify-end">{footer}</div>
      </div>
    </div>
  );
}
