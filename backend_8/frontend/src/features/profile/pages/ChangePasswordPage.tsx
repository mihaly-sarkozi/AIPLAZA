import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { useAuthStore, isDemoInitialPasswordMode } from "../../../store/authStore";
import { useChangePasswordMutation, useSetInitialPasswordMutation } from "../hooks";
import { validateRequired, validatePassword } from "../../../utils/formValidation";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import PageHeader from "../../../components/ui/PageHeader";

export default function ChangePasswordPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setToken = useAuthStore((s) => s.setToken);
  const loadUser = useAuthStore((s) => s.loadUser);
  const isInitialDemo = isDemoInitialPasswordMode(user);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const changePasswordMutation = useChangePasswordMutation();
  const setInitialPasswordMutation = useSetInitialPasswordMutation();
  const saving = isInitialDemo ? setInitialPasswordMutation.isPending : changePasswordMutation.isPending;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cur = currentPassword.trim();
    const newP = newPassword.trim();
    const conf = confirmPassword.trim();

    if (!isInitialDemo) {
      const requiredCur = validateRequired(cur);
      if (requiredCur) {
        toast.error(t(requiredCur));
        return;
      }
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

    if (isInitialDemo) {
      setInitialPasswordMutation.mutate(
        { new_password: newP },
        {
          onSuccess: async (data) => {
            setToken(data.access_token);
            await loadUser();
            toast.success(t("profile.setInitialPasswordSuccess"));
            navigate("/chat", { replace: true });
          },
          onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("common.errorGeneric")),
        }
      );
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
        },
        onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("common.errorGeneric")),
      }
    );
  };

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)] flex flex-col items-center justify-center">
      <div className="w-full max-w-md space-y-6">
        <PageHeader
          eyebrow={t("nav.settings")}
          title={isInitialDemo ? t("profile.setInitialPasswordTitle") : t("profile.changePassword")}
          description={isInitialDemo ? t("profile.setInitialPasswordIntro") : t("profile.changePasswordIntro")}
        />

        <div className="w-full bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-6">
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {!isInitialDemo && (
            <div>
              <label className="block mb-1 text-[var(--color-label)]">
                {t("profile.currentPassword")}
                {t("common.required")}
              </label>
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
          )}
          <div>
            <label className="block mb-1 text-[var(--color-label)]">
              {isInitialDemo ? t("profile.passwordField") : t("profile.newPassword")}
              {t("common.required")}
            </label>
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
            <label className="block mb-1 text-[var(--color-label)]">
              {isInitialDemo ? t("profile.passwordConfirmField") : t("profile.confirmPassword")}
              {t("common.required")}
            </label>
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

          <button
            type="submit"
            disabled={saving}
            className="w-full py-2 rounded bg-[var(--color-primary)] text-[var(--color-on-primary)] hover:opacity-90 disabled:opacity-60 font-semibold"
          >
            {saving ? t("common.loading") : isInitialDemo ? t("profile.setInitialPasswordSubmit") : t("common.save")}
          </button>
          {isInitialDemo && (
            <p className="text-xs text-[var(--color-muted)] text-center pt-1">{t("profile.setInitialPasswordFooter")}</p>
          )}
          </form>
        </div>
      </div>
    </div>
  );
}
