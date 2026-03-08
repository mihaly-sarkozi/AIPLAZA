import { useState } from "react";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { useChangePasswordMutation } from "../hooks";
import { validateRequired, validatePassword } from "../../../utils/formValidation";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";

interface ChangePasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ChangePasswordModal({ isOpen, onClose }: ChangePasswordModalProps) {
  const { t } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const changePasswordMutation = useChangePasswordMutation();
  const saving = changePasswordMutation.isPending;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cur = currentPassword.trim();
    const newP = newPassword.trim();
    const conf = confirmPassword.trim();
    const requiredCur = validateRequired(cur);
    if (requiredCur) {
      toast.error(t(requiredCur));
      return;
    }
    const requiredNew = validateRequired(newP);
    if (requiredNew) {
      toast.error(t(requiredNew));
      return;
    }
    const requiredConf = validateRequired(conf);
    if (requiredConf) {
      toast.error(t(requiredConf));
      return;
    }
    if (newP !== conf) {
      toast.error(t("profile.passwordMismatch"));
      return;
    }
    const passwordError = validatePassword(newP);
    if (passwordError) {
      toast.error(t(passwordError));
      return;
    }
    changePasswordMutation.mutate(
      { current_password: cur, new_password: newP },
      {
        onSuccess: () => {
          toast.success(t("profile.passwordChanged"));
          setCurrentPassword("");
          setNewPassword("");
          setConfirmPassword("");
          setTimeout(onClose, 300);
        },
        onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("common.errorGeneric")),
      }
    );
  };

  const handleCancel = () => {
    if (!saving) {
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
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          <div>
            <label className="block mb-1 text-[var(--color-label)]">{t("profile.currentPassword")}{t("common.required")}</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full p-2 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
              autoComplete="current-password"
              disabled={saving}
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
              disabled={saving}
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
              disabled={saving}
              required
            />
          </div>
          <div className="flex gap-2 pt-2 justify-end">
            <button
              type="button"
              onClick={handleCancel}
              disabled={saving}
              className="bg-[var(--color-card)] hover:bg-[var(--color-button-hover)] text-[var(--color-foreground)] border border-[var(--color-border)] px-4 py-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("common.cancel")}
            </button>
            <button
              type="submit"
              disabled={saving}
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
