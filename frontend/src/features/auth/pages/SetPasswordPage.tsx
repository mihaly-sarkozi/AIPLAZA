import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import api from "../../../api/axiosClient";
import { useSetPasswordMutation } from "../hooks/useAuth";

type TokenStatus = "loading" | "valid" | "invalid" | "expired" | "missing";

export default function SetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [tokenStatus, setTokenStatus] = useState<TokenStatus>("loading");
  const [tokenMessage, setTokenMessage] = useState("");
  const setPasswordMutation = useSetPasswordMutation();

  useEffect(() => {
    if (!token) {
      setTokenStatus("missing");
      setTokenMessage("Hiányzó vagy érvénytelen link. Kérj újat az adminisztrátortól.");
      return;
    }
    let cancelled = false;
    setTokenStatus("loading");
    api
      .get("/users/set-password/validate", { params: { token } })
      .then((res) => {
        if (!cancelled && res.data?.valid) setTokenStatus("valid");
      })
      .catch((err: unknown) => {
        if (!cancelled) return;
        const axErr = err as { response?: { status?: number; data?: { detail?: unknown } } };
        const d = axErr.response?.data?.detail;
        const msg = typeof d === "object" && d && "message" in d ? String((d as { message?: string }).message) : String(d || "A link nem érvényes.");
        setTokenMessage(msg);
        setTokenStatus(axErr.response?.status === 410 ? "expired" : "invalid");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const getDetailMessage = (err: unknown) => {
    const axErr = err as { response?: { data?: { detail?: unknown } } };
    const d = axErr.response?.data?.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) return String((d as { message?: string }).message);
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError("A két jelszó nem egyezik.");
      return;
    }
    if (password.length < 6) {
      setError("A jelszónak legalább 6 karakter hosszúnak kell lennie.");
      return;
    }
    if (!/[a-z]/.test(password)) {
      setError("A jelszónak tartalmaznia kell legalább egy kisbetűt.");
      return;
    }
    if (!/[A-Z]/.test(password)) {
      setError("A jelszónak tartalmaznia kell legalább egy nagybetűt.");
      return;
    }
    if (!/\d/.test(password)) {
      setError("A jelszónak tartalmaznia kell legalább egy számot.");
      return;
    }
    if (!token) return;
    setPasswordMutation.mutate(
      { token, password },
      {
        onSuccess: () => setSuccess(true),
        onError: (err) => setError(getDetailMessage(err) || "Ismeretlen hiba. Próbáld újra."),
      }
    );
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] text-[var(--color-foreground)] p-4">
        <div className="max-w-md w-full bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-8 shadow-sm">
          <h1 className="text-2xl font-bold mb-4 text-[var(--color-foreground)]">Jelszó beállítva</h1>
          <p className="mb-6 text-[var(--color-foreground)]">Most már be tudsz lépni a megadott email címmel és jelszóval.</p>
          <button
            type="button"
            onClick={() => navigate("/login")}
            className="w-full bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] py-3 rounded"
          >
            Tovább a bejelentkezéshez
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-background)] text-[var(--color-foreground)] p-4">
      <div className="max-w-md w-full bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg p-8 shadow-sm">
        <h1 className="text-2xl font-bold mb-2 text-[var(--color-foreground)]">Regisztráció befejezése</h1>
        <p className="text-sm text-[var(--color-muted)] mb-6">
          Állítsd be a jelszavad. A jelszónak legalább 6 karakter hosszúnak kell lennie, és tartalmazzon kisbetűt, nagybetűt és számot.
        </p>

        {tokenStatus === "loading" && token && (
          <div className="bg-[var(--color-table-head)] border border-[var(--color-border)] text-[var(--color-foreground)] p-4 rounded mb-4 text-sm">
            Link ellenőrzése…
          </div>
        )}

        {(tokenStatus === "invalid" || tokenStatus === "expired" || tokenStatus === "missing") && (
          <div className="bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-700 text-amber-900 dark:text-amber-200 p-4 rounded mb-4">
            <p className="font-medium mb-1">
              {tokenStatus === "expired" ? "A link lejárt" : "Ez a link már nem érvényes"}
            </p>
            <p className="text-sm">{tokenMessage}</p>
          </div>
        )}

        {error && (
          <div className="bg-[var(--color-table-head)] border border-[var(--color-border)] text-[var(--color-foreground)] p-3 rounded mb-4 text-sm">
            {error}
          </div>
        )}

        {token && tokenStatus === "valid" && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block mb-1 text-[var(--color-label)]">Új jelszó</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full p-3 pr-10 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
                  placeholder="••••••••"
                  minLength={6}
                  autoComplete="new-password"
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
            <div>
              <label className="block mb-1 text-[var(--color-label)]">Jelszó újra</label>
              <div className="relative">
                <input
                  type={showConfirm ? "text" : "password"}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="w-full p-3 pr-10 rounded bg-[var(--color-input-bg)] border border-[var(--color-border)] text-[var(--color-foreground)]"
                  placeholder="••••••••"
                  minLength={6}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded text-[var(--color-muted)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-border)]"
                  aria-label={showConfirm ? "Jelszó elrejtése" : "Jelszó megjelenítése"}
                >
                  {showConfirm ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                  )}
                </button>
              </div>
            </div>
            <button
              type="submit"
              disabled={setPasswordMutation.isPending}
              className="w-full bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)] py-3 rounded disabled:opacity-50"
            >
              {setPasswordMutation.isPending ? "Feldolgozás..." : "Jelszó mentése"}
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-[var(--color-muted)]">
          <a href="/login" className="underline hover:text-[var(--color-foreground)]">Vissza a bejelentkezéshez</a>
        </p>
      </div>
    </div>
  );
}
