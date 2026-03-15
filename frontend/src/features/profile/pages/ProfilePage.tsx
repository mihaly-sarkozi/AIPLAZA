import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { useTranslation } from "../../../i18n";
import { SavedModal } from "../../../components/SavedModal";
import type { Locale } from "../../../i18n";
import type { Theme } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { usePatchMeMutation } from "../hooks";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { validateRequired } from "../../../utils/formValidation";

const LOCALE_OPTIONS: { value: Locale; label: string }[] = [
  { value: "hu", label: "Magyar" },
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
];

export default function ProfilePage() {
  const { t, locale, setLocale, theme, setTheme } = useTranslation();
  const { user, setUser } = useAuthStore();
  const [name, setName] = useState("");
  const originalNameRef = useRef("");
  const [preferredLocale, setPreferredLocale] = useState<Locale>(locale);
  const [preferredTheme, setPreferredTheme] = useState<Theme>(theme);
  const [nameError, setNameError] = useState<string | null>(null);
  const [savedModalOpen, setSavedModalOpen] = useState(false);
  const patchMe = usePatchMeMutation();
  const saving = patchMe.isPending;

  useEffect(() => {
    if (user) {
      const n = user.name?.trim() ?? "";
      setName(n);
      originalNameRef.current = n;
      setPreferredLocale((user.locale as Locale) || locale);
      setPreferredTheme((user.theme as Theme) || theme);
    }
  }, [user, locale, theme]);

  const save = (payload: { name?: string | null; preferred_locale?: Locale; preferred_theme?: Theme }) => {
    if (!user) return;
    const body = {
      name: payload.name !== undefined ? (payload.name ?? undefined) : (name.trim() || undefined),
      preferred_locale: payload.preferred_locale ?? preferredLocale,
      preferred_theme: payload.preferred_theme ?? preferredTheme,
    };
    patchMe.mutate(body, {
      onSuccess: (data: { name?: string; locale?: string; theme?: string }) => {
        setUser({ ...user, ...data });
        if (data.locale) setLocale(data.locale as Locale);
        if (data.theme) setTheme(data.theme as Theme);
        if (payload.name !== undefined && data.name !== undefined) {
          const newName = (data.name as string)?.trim() ?? "";
          setName(newName);
          originalNameRef.current = newName;
          setNameError(null);
        }
        setSavedModalOpen(true);
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

  const handleLocaleChange = (value: Locale) => {
    setPreferredLocale(value);
    save({ preferred_locale: value });
  };

  const handleThemeChange = (value: Theme) => {
    setPreferredTheme(value);
    save({ preferred_theme: value });
  };

  return (
    <div className="p-6 w-full min-h-full bg-[var(--color-background)]">
      <h1 className="text-3xl font-bold mb-6 text-[var(--color-foreground)]">{t("profile.title")}</h1>

      <div className="w-full space-y-6 rounded-lg p-6 border border-[var(--color-border)]" style={{ backgroundColor: 'var(--color-card)' }}>
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

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
      </div>
    </div>
  );
}
