import { useState } from "react";
import { useTranslation } from "../../../i18n";
import { useChangePasswordMutation } from "../hooks/useUsers";

interface ChangePasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ChangePasswordModal({ isOpen, onClose }: ChangePasswordModalProps) {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const changePasswordMutation = useChangePasswordMutation();
  const saving = changePasswordMutation.isPending;

  const getErrorMsg = (err: unknown) => {
    const res = err as { response?: { data?: { detail?: string | { message?: string } } } };
    const detail = res.response?.data?.detail;
    return typeof detail === "string"
      ? detail
      : (detail && typeof detail === "object" && "message" in detail ? String((detail as { message?: string }).message) : null) || t("common.errorGeneric");
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const cur = currentPassword.trim();
    const newP = newPassword.trim();
    const conf = confirmPassword.trim();
    if (!cur || !newP || !conf) {
      setError(t("profile.allFieldsRequired"));
      return;
    }
    if (newP !== conf) {
      setError(t("profile.passwordMismatch"));
      return;
    }
    if (newP.length < 6) {
      setError(t("profile.passwordMinLength"));
      return;
    }
    if (!/[a-z]/.test(newP)) {
      setError(t("profile.passwordRequiresLower"));
      return;
    }
    if (!/[A-Z]/.test(newP)) {
      setError(t("profile.passwordRequiresUpper"));
      return;
    }
    if (!/\d/.test(newP)) {
      setError(t("profile.passwordRequiresNumber"));
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
          setTimeout(() => {
            onClose();
            setSuccess(false);
          }, 1500);
        },
        onError: (err) => setError(getErrorMsg(err)),
      }
    );
  };

  const handleCancel = () => {
    if (!saving) {
      setError("");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-full max-w-md shadow-lg">
        <h2 className="text-2xl font-bold mb-4 text-[var(--color-foreground)]">{t("profile.changePassword")}</h2>
        {success && (
          <div className="mb-4 p-3 rounded bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-300 text-sm">
            {t("profile.passwordChanged")}
          </div>
        )}
        {error && (
          <div className="mb-4 p-3 rounded bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm">
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
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
          <div className="flex gap-2 pt-2 justify-end">
            <button
              type="button"
              onClick={handleCancel}
              disabled={saving || success}
              className="bg-[var(--color-card)] hover:opacity-80 text-[var(--color-foreground)] border border-[var(--color-border)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={saving || success}
              className="bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? t("common.loading") : t("common.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
