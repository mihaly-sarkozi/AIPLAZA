import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { t as translate, useTranslation } from "../../../i18n";
import type { Locale } from "../../../i18n";
import type { Theme } from "../../../i18n";
import { useAuthStore, type User } from "../../../store/authStore";
import { usePatchProfileMutation, useProfileQuery, useDemoUnsubscribeMutation } from "../hooks";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { validateRequired } from "../../../utils/formValidation";
import PageHeader from "../../../components/ui/PageHeader";

const LOCALE_OPTIONS: { value: Locale; label: string }[] = [
  { value: "hu", label: "Magyar" },
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
];

export default function ProfilePage() {
  const navigate = useNavigate();
  const { t, locale, setLocale, theme, setTheme } = useTranslation();
  const { user, setUser, logout } = useAuthStore();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const originalNameRef = useRef("");
  const [preferredLocale, setPreferredLocale] = useState<Locale>(locale);
  const [preferredTheme, setPreferredTheme] = useState<Theme>(theme);
  const [nameError, setNameError] = useState<string | null>(null);
  const [unsubscribeOpen, setUnsubscribeOpen] = useState(false);
  const [unsubscribeEmail, setUnsubscribeEmail] = useState("");
  const [unsubscribeInfo, setUnsubscribeInfo] = useState("");
  const profileQuery = useProfileQuery({ enabled: !!user });
  const patchProfile = usePatchProfileMutation();
  const demoUnsubscribe = useDemoUnsubscribeMutation();
  const saving = patchProfile.isPending;
  const profile = profileQuery.data;
  const isOwner = user?.role === "owner";

  useEffect(() => {
    const source = profile ?? user;
    if (source) {
      const n = source.name?.trim() ?? "";
      setName(n);
      originalNameRef.current = n;
      setPreferredLocale(((source.preferred_locale || source.locale) as Locale) || locale);
      setPreferredTheme(((source.preferred_theme || source.theme) as Theme) || theme);
    }
  }, [profile, user, locale, theme]);

  const save = (payload: { name?: string | null; email?: string; preferred_locale?: Locale; preferred_theme?: Theme }) => {
    if (!user) return;
    const body = {
      name: payload.name !== undefined ? (payload.name ?? undefined) : (name.trim() || undefined),
      ...(payload.email !== undefined ? { email: payload.email } : {}),
      preferred_locale: payload.preferred_locale ?? preferredLocale,
      preferred_theme: payload.preferred_theme ?? preferredTheme,
    };
    patchProfile.mutate(body, {
      onSuccess: (data) => {
        const savedLocale = (data.locale || body.preferred_locale) as Locale;
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
        if (data.locale) setLocale(savedLocale);
        if (data.theme) setTheme(data.theme as Theme);
        if (payload.preferred_locale) {
          toast.success(translate("profile.saved", savedLocale));
        }
        if (payload.name !== undefined && data.name !== undefined) {
          const newName = (data.name as string)?.trim() ?? "";
          setName(newName);
          originalNameRef.current = newName;
          setNameError(null);
        }
        if (payload.email !== undefined) {
          setEmail("");
          toast.success(
            isOwner && data.pending_email
              ? translate("profile.savedWithEmailPending", savedLocale).replace("{{email}}", data.pending_email)
              : translate("profile.saved", savedLocale)
          );
        }
      },
      onError: (err: unknown) => {
        toast.error(getApiErrorMessage(err) ?? t("common.errorGeneric"));
      },
    });
  };

  const handleSaveName = () => {
    setNameError(null);
    const err = validateRequired(name);
    if (err) {
      setNameError(t(err));
      return;
    }
    save({ name: name.trim() || null });
  };

  const handleRevertName = () => {
    setName(originalNameRef.current);
  };

  const handleSaveEmail = () => {
    if (!user) return;
    const accountEmail = (((profile?.email as string) || (user?.email as string)) || "").trim();
    const emailTrim = email.trim();
    if (!emailTrim || emailTrim.toLowerCase() === accountEmail.toLowerCase()) return;
    save({ email: emailTrim });
  };

  const handleLocaleChange = (value: Locale) => {
    setPreferredLocale(value);
    setLocale(value);
    save({ preferred_locale: value });
  };

  const handleThemeChange = (value: Theme) => {
    setPreferredTheme(value);
    save({ preferred_theme: value });
  };

  const handleOpenUnsubscribe = (e: React.MouseEvent) => {
    e.preventDefault();
    setUnsubscribeEmail("");
    setUnsubscribeInfo("");
    setUnsubscribeOpen(true);
  };

  const handleConfirmUnsubscribe = () => {
    if (!user) return;
    const typed = unsubscribeEmail.trim().toLowerCase();
    const current = (user.email || "").trim().toLowerCase();
    if (!typed) {
      setUnsubscribeInfo("Az email cím megadása kötelező.");
      return;
    }
    if (typed !== current) {
      setUnsubscribeInfo("A beírt email cím nem egyezik a fiókod email címével.");
      return;
    }
    demoUnsubscribe.mutate(
      { email: typed },
      {
        onSuccess: (data) => {
          setUnsubscribeInfo(
            data.message ||
              "Leiratkozás rögzítve. 7 napon belül töröljük az összes tudástárat."
          );
          setTimeout(() => {
            logout();
            navigate("/login", { replace: true });
          }, 1200);
        },
        onError: (err: unknown) => {
          setUnsubscribeInfo(getApiErrorMessage(err) ?? t("common.errorGeneric"));
        },
      }
    );
  };

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)] flex flex-col items-center">
      <div className="w-full max-w-md space-y-6">
        <PageHeader
          eyebrow={t("nav.settings")}
          title={t("profile.title")}
          description={t("profile.pageIntro")}
        />

        <div className="w-full space-y-6 rounded-lg p-6 border border-[var(--color-border)]" style={{ backgroundColor: 'var(--color-card)' }}>
        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("profile.emailCurrentAccountLabel")}</label>
          <input
            type="email"
            readOnly
            value={(((profile?.email as string) || (user?.email as string)) || "").trim()}
            className="w-full bg-[var(--color-muted)]/30 border border-[var(--color-border)] text-[var(--color-foreground)] p-2 rounded cursor-not-allowed"
          />
        </div>
        {isOwner && (((profile?.pending_email as string) || (user?.pending_email as string)) || "").trim() ? (
          <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-table-head)] p-3 text-sm">
            <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">{t("profile.emailNewPendingLabel")}</div>
            <div className="mt-1 font-medium text-[var(--color-foreground)]">
              {(((profile?.pending_email as string) || (user?.pending_email as string)) || "").trim()}
            </div>
            <p className="mt-2 text-xs leading-relaxed text-[var(--color-muted)]">{t("profile.emailPendingExplain")}</p>
          </div>
        ) : null}

        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("profile.emailEditNewLabel")}</label>
          <div className="flex gap-2 items-center">
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="flex-1 min-w-0 p-2 rounded border border-[var(--color-border)] bg-[var(--color-input-bg)] text-[var(--color-foreground)]"
              placeholder={(((profile?.email as string) || (user?.email as string)) || "").trim()}
              maxLength={100}
            />
            <button
              type="button"
              onClick={handleSaveEmail}
              disabled={saving || !email.trim()}
              className="p-2 rounded border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-button-hover)] disabled:opacity-60 shrink-0 text-[var(--color-foreground)]"
              title={t("profile.emailChangeSendLink")}
              aria-label={t("profile.emailChangeSendLink")}
            >
              <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </button>
          </div>
          {isOwner ? (
            <p className="mt-1 text-xs text-[var(--color-muted)]">{t("profile.emailChangeHint")}</p>
          ) : null}
        </div>

        <div>
          <label className="block mb-1 text-[var(--color-label)]">{t("profile.nameLabel")}</label>
          {nameError && (
            <p className="text-sm text-red-600 dark:text-red-400 mb-1">{nameError}</p>
          )}
          <div className="flex gap-2 items-center">
            <input
              type="text"
              value={name}
              onChange={(e) => { setName(e.target.value); setNameError(null); }}
              className="flex-1 min-w-0 p-2 rounded border border-[var(--color-border)] bg-[var(--color-input-bg)] text-[var(--color-foreground)]"
              placeholder={t("roles.placeholderName")}
              maxLength={100}
            />
            <button
              type="button"
              onClick={handleSaveName}
              disabled={saving}
              className="p-2 rounded border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-button-hover)] disabled:opacity-60 shrink-0 text-[var(--color-foreground)]"
              title={t("common.save")}
              aria-label={t("common.save")}
            >
              <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </button>
            <button
              type="button"
              onClick={handleRevertName}
              className="p-2 rounded border border-[var(--color-border)] bg-[var(--color-card)] hover:bg-[var(--color-button-hover)] shrink-0 text-[var(--color-foreground)]"
              title={t("profile.revert")}
              aria-label={t("profile.revert")}
            >
              <svg className="w-5 h-5 text-[var(--color-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-6">
          <div>
            <label className="block mb-2 text-[var(--color-label)]">{t("settings.languageLabel")}</label>
            <div className="flex flex-wrap gap-2">
              {LOCALE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleLocaleChange(opt.value)}
                  disabled={saving}
                  className={`px-4 py-2 rounded text-sm border ${
                    preferredLocale === opt.value
                      ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)] hover:opacity-90"
                      : "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-button-hover)]"
                  } disabled:opacity-60`}
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
                onClick={() => handleThemeChange("light")}
                disabled={saving}
                className={`px-4 py-2 rounded text-sm border ${
                  preferredTheme === "light"
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)] hover:opacity-90"
                    : "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-button-hover)]"
                } disabled:opacity-60`}
              >
                {t("profile.themeLight")}
              </button>
              <button
                type="button"
                onClick={() => handleThemeChange("dark")}
                disabled={saving}
                className={`px-4 py-2 rounded text-sm border ${
                  preferredTheme === "dark"
                    ? "bg-[var(--color-primary)] text-[var(--color-on-primary)] border-[var(--color-primary)] hover:opacity-90"
                    : "bg-[var(--color-card)] text-[var(--color-foreground)] border-[var(--color-border)] hover:bg-[var(--color-button-hover)]"
                } disabled:opacity-60`}
              >
                {t("profile.themeDark")}
              </button>
            </div>
          </div>
        </div>

        <div className="pt-2 border-t border-[var(--color-border)] text-sm text-[var(--color-muted-foreground)]">
          Ha szeretné törölni az összes tudástárát és regisztrációját, akkor a linkre kattintson:{" "}
          <button type="button" onClick={handleOpenUnsubscribe} className="underline text-[var(--color-foreground)]">
            leiratkozás
          </button>
          .
        </div>
        </div>
      </div>

      {unsubscribeOpen && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center px-4">
          <div className="w-full max-w-xl rounded-xl bg-[var(--color-card)] border border-[var(--color-border)] p-5">
            <h2 className="text-lg font-semibold mb-3 text-[var(--color-foreground)]">Leiratkozás megerősítése</h2>
            <p className="text-sm text-[var(--color-foreground)] mb-2">
              Ha leiratkozik, minden tudástárat törlünk és többet nem fogja elérni azokat.
            </p>
            <p className="text-sm text-[var(--color-foreground)] mb-3">
              Ha valóban szeretne leiratkozni, kérjük gépelje be az email címét és nyomja meg a leiratkozás gombot.
            </p>
            <p className="text-sm text-[var(--color-muted-foreground)] mb-2">
              7 napon belül töröljük az összes tudástárat.
            </p>
            <p className="text-sm font-medium text-red-600 mb-4">
              Figyelem! Ezzel az email címmel nem hozhat létre több demo regisztrációt.
            </p>
            <input
              type="email"
              value={unsubscribeEmail}
              onChange={(e) => setUnsubscribeEmail(e.target.value)}
              placeholder="email@pelda.hu"
              className="w-full p-2 rounded border border-[var(--color-border)] bg-[var(--color-input-bg)] text-[var(--color-foreground)]"
            />
            {unsubscribeInfo ? <p className="mt-3 text-sm text-[var(--color-foreground)]">{unsubscribeInfo}</p> : null}
            <p className="mt-2 text-xs text-[var(--color-muted-foreground)]">
              Ettől ponttól jelenleg létrehozhat egy másik tudástárat a felhasználó, de éles rendszerben nem.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setUnsubscribeOpen(false)}
                className="px-4 py-2 rounded border border-[var(--color-border)]"
              >
                Vissza
              </button>
              <button
                type="button"
                onClick={handleConfirmUnsubscribe}
                disabled={demoUnsubscribe.isPending}
                className="px-4 py-2 rounded bg-red-600 text-white disabled:opacity-60"
              >
                {demoUnsubscribe.isPending ? "Leiratkozás..." : "Leiratkozás"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
