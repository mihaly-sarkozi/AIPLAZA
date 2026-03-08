import { useState, useEffect } from "react";
import { useTranslation } from "../../../i18n";
import type { Locale } from "../../../i18n";
import type { Theme } from "../../../i18n";
import { useAuthStore } from "../../../store/authStore";
import { usePatchMeMutation } from "../hooks";
import { toast } from "sonner";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { validateRequired } from "../../../utils/formValidation";

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
  const [preferredLocale, setPreferredLocale] = useState<Locale>("hu");
  const [preferredTheme, setPreferredTheme] = useState<Theme>("light");
  const patchMe = usePatchMeMutation();
  const saving = patchMe.isPending;

  useEffect(() => {
    if (isOpen && user) {
      setName((user.name as string)?.trim() ?? "");
      setPreferredLocale((user.locale as Locale) || "hu");
      setPreferredTheme((user.theme as Theme) || "light");
    }
  }, [isOpen, user]);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    const nameError = validateRequired(name);
    if (nameError) {
      toast.error(t(nameError));
      return;
    }
    patchMe.mutate(
      { name: name.trim() || undefined, preferred_locale: preferredLocale, preferred_theme: preferredTheme },
      {
        onSuccess: (data: { name?: string; preferred_locale?: string; preferred_theme?: string; locale?: string; theme?: string }) => {
          const d = data;
          setUser({ ...user, name: data.name ?? undefined, preferred_locale: data.preferred_locale, preferred_theme: data.preferred_theme, locale: d.locale, theme: d.theme });
          if (d.locale) setLocale(d.locale as Locale);
          if (d.theme) setTheme(d.theme as Theme);
          toast.success(t("profile.saved"));
          onClose();
        },
        onError: (err: unknown) => toast.error(getApiErrorMessage(err) ?? t("common.errorGeneric")),
      }
    );
  };

  const handleCancel = () => {
    if (!saving) onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-6 rounded-lg w-full max-w-md shadow-lg max-h-[90vh] overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4 text-[var(--color-foreground)]">{t("profile.title")}</h2>
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
            <label className="block mb-2 text-[var(--color-label)]">{t("settings.languageLabel")}</label>
            <div className="flex flex-wrap gap-2">
              {LOCALE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setPreferredLocale(opt.value)}
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
          <div className="flex gap-2 pt-4 justify-end">
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
