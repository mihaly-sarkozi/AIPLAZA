import { useState } from "react";
import { useTranslation } from "../i18n";
import { useChangePasswordMutation } from "../hooks/useApi";
import { validateRequired, validatePassword } from "../utils/formValidation";
import { getApiErrorMessage } from "../utils/getApiErrorMessage";

export default function ChangePasswordPage() {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const changePasswordMutation = useChangePasswordMutation();
  const saving = changePasswordMutation.isPending;

  const getErrorMsg = (err: unknown) => getApiErrorMessage(err) ?? t("common.errorGeneric");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const cur = currentPassword.trim();
    const newP = newPassword.trim();
    const conf = confirmPassword.trim();
    const requiredCur = validateRequired(cur);
    if (requiredCur) {
      setError(t(requiredCur));
      return;
    }
    const requiredNew = validateRequired(newP);
    if (requiredNew) {
      setError(t(requiredNew));
      return;
    }
    const requiredConf = validateRequired(conf);
    if (requiredConf) {
      setError(t(requiredConf));
      return;
    }
    if (newP !== conf) {
      setError(t("profile.passwordMismatch"));
      return;
    }
    const passwordError = validatePassword(newP);
    if (passwordError) {
      setError(t(passwordError));
      return;
    }
    changePasswordMutation.mutate(
      { current_password: cur, new_password: newP },
      {
        onSuccess: () => {
          setSuccess(true);
          setCurrentPassword("");
          setNewPassword("");
          setConfirmPassword("");
        },
        onError: (err) => setError(getErrorMsg(err)),
      }
    );
  };

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)] flex flex-col items-center justify-center">
      <h1 className="text-3xl font-bold mb-6 text-[var(--color-foreground)]">{t("profile.changePassword")}</h1>

      <div className="w-full max-w-md bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-6">
        {success && (
          <div className="mb-4 p-3 rounded bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-300 text-sm">
            {t("profile.passwordChanged")}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {error && (
            <div className="p-3 rounded bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
              {error}
            </div>
          )}

          <div>
            <label className="block mb-1 text-[var(--color-label)]">{t("profile.currentPassword")}{t("common.required")}</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
              autoComplete="current-password"
              disabled={saving || success}
              required
            />
          </div>
          <div>
            <label className="block mb-1 text-[var(--color-label)]">{t("profile.newPassword")}{t("common.required")}</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
              autoComplete="new-password"
              disabled={saving || success}
              required
            />
            <p className="text-sm text-[var(--color-muted)] mt-1">{t("profile.passwordRules")}</p>
          </div>
          <div>
            <label className="block mb-1 text-[var(--color-label)]">{t("profile.confirmPassword")}{t("common.required")}</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
              autoComplete="new-password"
              disabled={saving || success}
              required
            />
          </div>

          <button
            type="submit"
            disabled={saving}
            className="w-full py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90 disabled:opacity-60 font-semibold"
          >
            {saving ? t("common.loading") : t("common.save")}
          </button>
        </form>
      </div>
    </div>
  );
}
