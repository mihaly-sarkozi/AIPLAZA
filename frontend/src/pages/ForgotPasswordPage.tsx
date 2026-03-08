import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "../i18n";
import { useForgotPasswordMutation } from "../hooks/useApi";

export default function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [requestError, setRequestError] = useState("");
  const forgotMutation = useForgotPasswordMutation();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (forgotMutation.isPending) return;
    setRequestError("");
    forgotMutation.mutate(
      { email: email.trim() },
      {
        onSuccess: () => setDone(true),
        onError: () => setRequestError(t("common.errorGeneric")),
      }
    );
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-8 rounded-lg shadow-sm w-full max-w-md">
        <h1 className="text-3xl font-bold text-center mb-6 text-[var(--color-foreground)]">{t("forgot.title")}</h1>

        {done ? (
          <div className="space-y-4">
            <p className="text-[var(--color-foreground)] text-center">
              {t("forgot.successMessage")}
            </p>
            <Link
              to="/login"
              className="block w-full text-center bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] font-semibold py-3 rounded-md transition"
            >
              {t("forgot.backToLogin")}
            </Link>
          </div>
        ) : (
          <>
            <p className="text-[var(--color-muted)] text-sm mb-4">{t("forgot.intro")}</p>
            <form onSubmit={submit} className="flex flex-col gap-4">
              {requestError && (
                <div className="bg-[var(--color-table-head)] border border-[var(--color-border)] text-[var(--color-foreground)] p-3 rounded-md text-sm text-center">
                  {requestError}
                </div>
              )}
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("forgot.emailLabel")}</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full p-3 rounded-md bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border)]"
                  placeholder={t("forgot.emailPlaceholder")}
                  autoComplete="email"
                  maxLength={100}
                  required
                />
              </div>
              <button
                type="submit"
                disabled={forgotMutation.isPending}
                className="w-full bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] disabled:opacity-60 disabled:cursor-not-allowed font-semibold py-3 rounded-md transition"
              >
                {forgotMutation.isPending ? t("common.loading") : t("forgot.send")}
              </button>
            </form>
            <p className="mt-4 text-center">
              <Link to="/login" className="text-sm text-[var(--color-muted)] hover:text-[var(--color-foreground)] underline">
                {t("forgot.backToLogin")}
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
