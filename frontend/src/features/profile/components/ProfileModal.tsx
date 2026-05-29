import { useState, useEffect } from "react";
import { t as translate, useTranslation } from "../../../i18n";
import type { Locale } from "../../../i18n";
import type { Theme } from "../../../i18n";
import { useAuthStore, type User } from "../../../store/authStore";
import { usePatchProfileMutation, useProfileQuery } from "../hooks";
import { toast } from "sonner";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { validateRequired } from "../../../utils/formValidation";
import Button from "../../../components/ui/Button";
import Modal, { ModalFooter, ModalHeader } from "../../../components/ui/Modal";

const LOCALE_OPTIONS: { value: Locale; label: string }[] = [
  { value: "hu", label: "Magyar" },
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
];

interface ProfileModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function ProfileModal({ isOpen, onClose }: ProfileModalProps) {
  const { t, setLocale, setTheme } = useTranslation();
  const { user, setUser } = useAuthStore();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [preferredLocale, setPreferredLocale] = useState<Locale>("hu");
  const [preferredTheme, setPreferredTheme] = useState<Theme>("light");
  const profileQuery = useProfileQuery({ enabled: isOpen && !!user });
  const patchProfile = usePatchProfileMutation();
  const saving = patchProfile.isPending;
  const profile = profileQuery.data;

  useEffect(() => {
    if (isOpen) {
      const source = profile ?? user;
      if (!source) return;
      setName((source.name as string)?.trim() ?? "");
      setEmail("");
      setPreferredLocale(((source.preferred_locale || source.locale) as Locale) || "hu");
      setPreferredTheme(((source.preferred_theme || source.theme) as Theme) || "light");
    }
  }, [isOpen, profile, user]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    const nameError = validateRequired(name);
    if (nameError) {
      toast.error(t(nameError));
      return;
    }

    const accountEmail = (((profile?.email as string) || (user?.email as string)) || "").trim();
    const emailTrim = email.trim();
    const emailChanged = emailTrim.length > 0 && emailTrim.toLowerCase() !== accountEmail.toLowerCase();

    try {
      const data = await patchProfile.mutateAsync({
        name: name.trim() || undefined,
        ...(emailChanged ? { email: emailTrim } : {}),
        preferred_locale: preferredLocale,
        preferred_theme: preferredTheme,
      });

      setUser({
        ...user,
        name: data.name ?? undefined,
        email: data.email,
        pending_email: data.pending_email,
        pending_email_expires_at: data.pending_email_expires_at,
        role: data.role as User["role"],
        is_active: data.is_active,
        preferred_locale: data.preferred_locale,
        preferred_theme: data.preferred_theme,
        locale: data.locale,
        theme: data.theme,
        credentials_password_set: data.credentials_password_set,
        tenant_demo_mode: data.tenant_demo_mode,
        tenant_kb_has_training: data.tenant_kb_has_training,
      });
      const savedLocale = (data.locale || preferredLocale) as Locale;
      if (data.locale) setLocale(savedLocale);
      if (data.theme) setTheme(data.theme as Theme);

      toast.success(
        data.pending_email
          ? translate("profile.savedWithEmailPending", savedLocale).replace("{{email}}", data.pending_email)
          : translate("profile.saved", savedLocale)
      );
      onClose();
    } catch (err: unknown) {
      toast.error(getApiErrorMessage(err) ?? t("common.errorGeneric"));
    }
  };

  const handleCancel = () => {
    if (!saving) onClose();
  };

  const accountEmail = (((profile?.email as string) || (user?.email as string)) || "").trim();
  const pendingEmail = (((profile?.pending_email as string) || (user?.pending_email as string)) || "").trim();
  const isOwner = user?.role === "owner";

  return (
    <Modal open={isOpen} onClose={handleCancel} panelClassName="max-w-md">
      <ModalHeader
        eyebrow={t("nav.settings")}
        title={t("profile.title")}
        description={t("profile.pageIntro")}
      />
      <form onSubmit={handleSave} className="space-y-4">
        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("profile.nameLabel")}</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
            placeholder={t("roles.placeholderName")}
            maxLength={100}
          />
        </div>

        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("profile.emailCurrentAccountLabel")}</label>
          <input
            type="email"
            readOnly
            value={accountEmail}
            className="w-full bg-[var(--color-muted)]/30 border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded cursor-not-allowed"
          />
        </div>

        {isOwner && pendingEmail ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-table-head)] p-3 text-sm">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">{t("profile.emailNewPendingLabel")}</div>
            <div className="mt-1 font-medium text-[var(--color-foreground)]">{pendingEmail}</div>
            <p className="mt-2 text-xs leading-relaxed text-[var(--color-muted)]">{t("profile.emailPendingExplain")}</p>
          </div>
        ) : null}

        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("profile.emailEditNewLabel")}</label>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded"
            placeholder={accountEmail}
            maxLength={100}
          />
          {isOwner ? (
            <p className="mt-1 text-xs text-[var(--color-muted)]">{t("profile.emailChangeHint")}</p>
          ) : null}
        </div>

        <div>
          <label className="block mb-2 text-[var(--color-label)]">{t("settings.languageLabel")}</label>
          <div className="flex flex-wrap gap-2">
            {LOCALE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  setPreferredLocale(opt.value);
                  setLocale(opt.value);
                }}
                className={`px-4 py-2 rounded text-sm border ${
                  preferredLocale === opt.value
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)] hover:opacity-90"
                    : "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-button-hover)]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="block mb-2 text-[var(--color-label)]">{t("profile.themeLabel")}</label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setPreferredTheme("light")}
              className={`px-4 py-2 rounded text-sm border ${
                preferredTheme === "light"
                  ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)] hover:opacity-90"
                  : "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-button-hover)]"
              }`}
            >
              {t("profile.themeLight")}
            </button>
            <button
              type="button"
              onClick={() => setPreferredTheme("dark")}
              className={`px-4 py-2 rounded text-sm border ${
                preferredTheme === "dark"
                  ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)] hover:opacity-90"
                  : "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-button-hover)]"
              }`}
            >
              {t("profile.themeDark")}
            </button>
          </div>
        </div>
        <ModalFooter className="pt-2">
          <Button type="button" variant="secondary" onClick={handleCancel} disabled={saving}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving || profileQuery.isLoading ? t("common.loading") : t("common.save")}
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
