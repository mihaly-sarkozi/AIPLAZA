import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { getApiErrorMessage } from "../../../utils/getApiErrorMessage";
import { platformAdminLogin } from "../api";
import { usePlatformAdminStore } from "../state";

export default function PlatformAdminLoginPage() {
  const navigate = useNavigate();
  const setSession = usePlatformAdminStore((s) => s.setSession);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (loading) return;
    setError("");
    setLoading(true);
    try {
      const data = await platformAdminLogin(email.trim(), password);
      setSession(data.access_token, data.user);
      navigate("/platform-admin", { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err) ?? "Hibás email vagy jelszó.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-background)] px-4 text-[var(--color-foreground)]">
      <div className="mx-auto flex min-h-screen max-w-md items-center">
        <form onSubmit={submit} className="w-full rounded-3xl border border-[var(--color-border)] bg-[var(--color-card)] p-8 shadow-sm">
          <p className="mb-2 text-sm font-semibold uppercase tracking-[0.2em] text-[var(--color-muted)]">Fő admin</p>
          <h1 className="mb-6 text-3xl font-bold">Admin bejelentkezés</h1>
          {error ? (
            <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          ) : null}
          <div className="space-y-4">
            <label className="block">
              <span className="mb-1 block text-sm text-[var(--color-label)]">Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-input-bg)] p-3"
                autoComplete="username"
                required
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-[var(--color-label)]">Jelszó</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-xl border border-[var(--color-border)] bg-[var(--color-input-bg)] p-3"
                autoComplete="current-password"
                required
              />
            </label>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-black px-4 py-3 font-semibold text-white disabled:opacity-60"
            >
              {loading ? "Belépés..." : "Belépés"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

