import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "../i18n";
import { useAuthStore } from "../store/authStore";
import { getSafeLoginRedirect } from "../utils/loginRedirect";
import { useLocaleStore } from "../i18n";
import { useDefaultSettings, useLoginMutation } from "../hooks/useApi";
import type { Locale } from "../i18n";

const LOGIN_REMEMBER_EMAIL_KEY = "AIPLAZA_login_remember_email";
const LOGIN_COOLDOWN_SECONDS = 30;

export default function Login() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnTo = getSafeLoginRedirect(searchParams.get("redirect"));
  const { setToken, logout, loadUser } = useAuthStore();
  const setLocaleAndTheme = useLocaleStore((s) => s.setLocaleAndTheme);
  const token = useAuthStore((s) => s.token);
  const { data: defaultSettings } = useDefaultSettings({ enabled: !token });

  useEffect(() => {
    if (!defaultSettings) return;
    const loc = (defaultSettings.locale || "hu") as Locale;
    const currentTheme = useLocaleStore.getState().theme;
    setLocaleAndTheme(loc, currentTheme);
  }, [defaultSettings, setLocaleAndTheme]);

  const handleLoginSuccess = async (access_token: string) => {
    setToken(access_token); // memory only (auth store); never persist to localStorage/sessionStorage
    await loadUser();
    navigate(returnTo);
  };

  const [email, setEmail] = useState(() => {
    try {
      return localStorage.getItem(LOGIN_REMEMBER_EMAIL_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [twoFactorCode, setTwoFactorCode] = useState("");
  const [autoLogin, setAutoLogin] = useState(() => {
    try {
      return !!localStorage.getItem(LOGIN_REMEMBER_EMAIL_KEY);
    } catch {
      return false;
    }
  });
  const [error, setError] = useState("");
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [cooldownSecondsRemaining, setCooldownSecondsRemaining] = useState(0);
  const loginMutation = useLoginMutation();
  const submitting = loginMutation.isPending;

  useEffect(() => {
    if (cooldownSecondsRemaining <= 0) return;
    const id = setInterval(() => {
      setCooldownSecondsRemaining((s) => (s <= 1 ? 0 : s - 1));
    }, 1000);
    return () => clearInterval(id);
  }, [cooldownSecondsRemaining]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || cooldownSecondsRemaining > 0) return;
    setError("");

    const payload = pendingToken
      ? { pending_token: pendingToken, two_factor_code: twoFactorCode, auto_login: autoLogin }
      : { email, password, auto_login: autoLogin };

    const doLogin = async () => {
      const data = await loginMutation.mutateAsync(payload);
      if (data.pending_token) {
        setPendingToken(data.pending_token);
        setTwoFactorCode("");
        setError("");
        return;
      }
      const access_token = data.access_token;
      if (!access_token) return;
      try {
        if (autoLogin && email) {
          localStorage.setItem(LOGIN_REMEMBER_EMAIL_KEY, email);
        } else {
          localStorage.removeItem(LOGIN_REMEMBER_EMAIL_KEY);
        }
      } catch (_) {}
      await handleLoginSuccess(access_token);
    };

    try {
      await doLogin();
    } catch (err: unknown) {
      const axErr = err as { response?: { status?: number } };
      if (axErr.response?.status === 409) {
        logout();
        try {
          await doLogin();
        } catch (retryErr: unknown) {
          const retry = retryErr as { response?: { status?: number } };
          console.error("Login retry error:", retryErr);
          if (retry.response?.status === 401) {
            setError(pendingToken ? t("login.errorBad2FA") : t("login.errorBadCredentials"));
          } else if (retry.response?.status === 429) {
            setError(t("login.errorTooMany"));
            setCooldownSecondsRemaining(LOGIN_COOLDOWN_SECONDS);
          } else {
            setError(t("login.errorUnknown"));
          }
        }
        return;
      }
      if (axErr.response?.status === 429) {
        setError(t("login.errorTooMany"));
        setCooldownSecondsRemaining(LOGIN_COOLDOWN_SECONDS);
      } else if (axErr.response?.status === 401) {
        setError(pendingToken ? t("login.errorBad2FA") : t("login.errorBadCredentials"));
      } else {
        setError(t("login.errorUnknown"));
      }
      console.error("Login error:", err);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-8 rounded-lg shadow-sm w-full max-w-md">
        <h1 className="text-3xl font-bold text-center mb-6 text-[var(--color-foreground)]">{t("login.title")}</h1>

        {error && (
          <div className="bg-[var(--color-table-head)] border border-[var(--color-border)] text-[var(--color-foreground)] p-3 rounded-md text-sm mb-4 text-center">
            {error}
          </div>
        )}

        {cooldownSecondsRemaining > 0 && (
          <div className="bg-[var(--color-table-head)] border border-[var(--color-border)] text-[var(--color-foreground)] p-3 rounded-md text-sm mb-4 text-center font-medium" role="status" aria-live="polite">
            {t("login.tryAgainInSeconds").replace("{{seconds}}", String(cooldownSecondsRemaining))}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4" aria-disabled={cooldownSecondsRemaining > 0}>
          {!pendingToken && (
            <>
              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("login.emailLabel")}</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full p-3 rounded-md bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border)] disabled:opacity-60 disabled:cursor-not-allowed"
                  placeholder={t("login.emailPlaceholder")}
                  autoComplete="username"
                  maxLength={100}
                  required
                  disabled={cooldownSecondsRemaining > 0}
                />
              </div>

              <div>
                <label className="block mb-1 text-[var(--color-label)]">{t("login.passwordLabel")}</label>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full p-3 pr-10 rounded-md bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border)] disabled:opacity-60 disabled:cursor-not-allowed"
                    placeholder={t("login.passwordPlaceholder")}
                    autoComplete="current-password"
                    required
                    disabled={cooldownSecondsRemaining > 0}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded text-[var(--color-muted)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-border)]"
                    aria-label={showPassword ? "Jelszó elrejtése" : "Jelszó megjelenítése"}
                  >
                    {showPassword ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                    )}
                  </button>
                </div>
              </div>
            </>
          )}

          {pendingToken && (
            <div>
              <label className="block mb-1 text-[var(--color-label)]">
                {t("login.twoFactorLabel")}
              </label>
              <input
                type="text"
                value={twoFactorCode}
                onChange={(e) => setTwoFactorCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                className="w-full p-3 rounded-md bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border)] disabled:opacity-60 disabled:cursor-not-allowed"
                placeholder={t("login.twoFactorPlaceholder")}
                maxLength={6}
                autoComplete="one-time-code"
                required
                disabled={cooldownSecondsRemaining > 0}
              />
              <p className="text-sm text-[var(--color-muted)] mt-1">
                {t("login.twoFactorHint")}
              </p>
            </div>
          )}

          {!pendingToken && (
            <div className="flex items-center justify-between mb-2">
              <label className="flex items-center gap-2 text-sm text-[var(--color-label)] select-none">
                <input
                  type="checkbox"
                  checked={autoLogin}
                  disabled={cooldownSecondsRemaining > 0}
                  onChange={(e) => {
                    const checked = e.target.checked;
                    setAutoLogin(checked);
                    if (!checked) {
                      try {
                        localStorage.removeItem(LOGIN_REMEMBER_EMAIL_KEY);
                      } catch (_) {}
                    }
                  }}
                  className="h-4 w-4 shrink-0 accent-[var(--color-primary)] cursor-pointer rounded border border-[var(--color-border)] bg-[var(--color-input-bg)]"
                  style={{
                    display: "inline-block",
                    flex: "0 0 auto",
                    width: "1rem",
                    height: "1rem",
                    margin: "0 6px 0 2px",
                    verticalAlign: "middle",
                  }}
                />
                <span className="leading-tight">{t("login.autoLogin")}</span>
              </label>

              <a
                href="/forgot"
                className="text-sm text-[var(--color-muted)] hover:text-[var(--color-foreground)] underline whitespace-nowrap"
              >
                {t("login.forgotPassword")}
              </a>
            </div>
          )}

          {pendingToken && (
            <button
              type="button"
              onClick={() => {
                setPendingToken(null);
                setTwoFactorCode("");
                setError("");
              }}
              className="text-sm text-[var(--color-muted)] hover:text-[var(--color-foreground)] underline"
            >
              {t("login.back")}
            </button>
          )}

          <button
            type="submit"
            disabled={submitting || cooldownSecondsRemaining > 0}
            className="w-full bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] disabled:opacity-60 disabled:cursor-not-allowed font-semibold py-3 rounded-md transition"
          >
            {cooldownSecondsRemaining > 0
              ? t("login.tryAgainInSeconds").replace("{{seconds}}", String(cooldownSecondsRemaining))
              : submitting
                ? t("login.submitting")
                : t("login.submit")}
          </button>
        </form>
      </div>
    </div>
  );
}
