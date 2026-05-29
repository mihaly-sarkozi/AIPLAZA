import { useState } from "react";
import { useNavigate } from "react-router-dom";

import Alert from "../../../components/ui/Alert";
import Button from "../../../components/ui/Button";
import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { platformAdminLogin } from "../api";
import { usePlatformAdminStore } from "../state";

export default function PlatformAdminLoginPage() {
  const navigate = useNavigate();
  const setSession = usePlatformAdminStore((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [mfaDialogOpen, setMfaDialogOpen] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const finishLogin = (data: Awaited<ReturnType<typeof platformAdminLogin>>) => {
    setSession(data.access_token, data.user);
    navigate("/platform-admin", { replace: true });
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      const data = await platformAdminLogin(email.trim(), password);
      finishLogin(data);
    } catch (err) {
      const message = getApiErrorMessage(err) ?? "Hibás email vagy jelszó.";
      if (message.toLowerCase().includes("mfa") || message.toLowerCase().includes("authenticator")) {
        setMfaDialogOpen(true);
        setMfaCode("");
        setError("");
      } else {
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  };

  const submitMfa = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading || !mfaCode.trim()) return;
    setError("");
    setLoading(true);
    try {
      const data = await platformAdminLogin(email.trim(), password, mfaCode);
      finishLogin(data);
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Érvénytelen MFA kód.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] px-4 text-[var(--color-foreground)]">
      <div className="modal-card w-full max-w-md p-8">
        <h1 className="text-3xl font-bold text-center mb-2 text-[var(--color-foreground)]">Admin bejelentkezés</h1>
        <p className="mb-6 text-center text-sm font-semibold uppercase tracking-[0.2em] text-[var(--color-muted)]">Fő admin</p>

        {error ? (
          <Alert tone="error" className="mb-4 text-center">
            {error}
          </Alert>
        ) : null}

        <form onSubmit={submit} className="flex flex-col gap-4">
          <div>
            <label className="block mb-1 text-[var(--color-label)]">Email</label>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full p-3 rounded-md bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border)]"
                autoComplete="username"
                required
              />
          </div>

          <div>
            <label className="block mb-1 text-[var(--color-label)]">Jelszó</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="w-full p-3 pr-10 rounded-md bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border)]"
                  autoComplete="current-password"
                  required
                />
                <Button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  variant="ghost"
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5"
                  aria-label={showPassword ? "Jelszó elrejtése" : "Jelszó megjelenítése"}
                >
                  {showPassword ? (
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                  ) : (
                    <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                  )}
                </Button>
              </div>
          </div>

          <Button type="submit" disabled={loading} fullWidth size="lg">
            {loading ? "Belépés..." : "Belépés"}
          </Button>
        </form>
      </div>
      {mfaDialogOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <form onSubmit={submitMfa} className="modal-card w-full max-w-sm p-6">
            <h2 className="text-xl font-semibold">MFA ellenőrzés</h2>
            <p className="mt-2 text-sm text-[var(--color-muted)]">
              A jelszó rendben van. Add meg az authenticator vagy recovery kódot a belépéshez.
            </p>
            {error ? (
              <Alert tone="error" className="mt-4">
                {error}
              </Alert>
            ) : null}
            <label className="mt-4 block">
              <span className="mb-1 block text-sm text-[var(--color-label)]">MFA kód vagy recovery kód</span>
              <input
                type="text"
                value={mfaCode}
                onChange={(event) => setMfaCode(event.target.value)}
                className="w-full p-3 rounded-md bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--color-border)]"
                autoComplete="one-time-code"
                inputMode="numeric"
                autoFocus
                placeholder="123456"
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setMfaDialogOpen(false);
                  setMfaCode("");
                  setError("");
                }}
                disabled={loading}
              >
                Mégse
              </Button>
              <Button
                type="submit"
                disabled={loading || !mfaCode.trim()}
              >
                {loading ? "Ellenőrzés..." : "Belépés"}
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}

