import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { consumeDemoLogin, resolveDemoLogin } from "../api/demoApi";
import { fetchCsrfToken } from "../../../api/axiosClient";
import { isDemoInitialPasswordMode, useAuthStore } from "../../../store/authStore";
import { getTenantBaseDomain, isTenantSubdomain } from "../../../utils/domain";

function installBaseUrl(): string {
  const scheme = window.location.protocol || "http:";
  const host = getTenantBaseDomain();
  const port = window.location.port ? `:${window.location.port}` : "";
  return `${scheme}//${host}${port}`;
}

export default function DemoLoginPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setToken, loadUser } = useAuthStore();
  const [message, setMessage] = useState("A demo link ellenőrzése folyamatban…");
  const [error, setError] = useState("");
  const token = useMemo(() => searchParams.get("token") || "", [searchParams]);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      if (!token) {
        setError("Hiányzik a demo token.");
        setMessage("");
        return;
      }

      try {
        if (!isTenantSubdomain()) {
          const data = await resolveDemoLogin(token);
          if (!cancelled) window.location.replace(data.redirect_to);
          return;
        }

        setMessage("Beléptetés folyamatban…");
        await fetchCsrfToken();
        const data = await consumeDemoLogin(token);
        if (cancelled) return;
        setToken(data.access_token);
        await loadUser();
        const currentUser = useAuthStore.getState().user;
        navigate(isDemoInitialPasswordMode(currentUser) ? "/change-password" : "/chat", { replace: true });
      } catch (err: unknown) {
        if (cancelled) return;
        const status =
          err && typeof err === "object" && "response" in err
            ? (err as { response?: { status?: number } }).response?.status
            : undefined;

        if (status === 410) {
          window.location.replace(`${installBaseUrl()}/demo-expired`);
          return;
        }

        setMessage("");
        setError("A demo link nem használható. Kérj új linket a demo oldalról.");
      }
    };

    void run();
    return () => {
      cancelled = true;
    };
  }, [loadUser, navigate, setToken, token]);

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4">
        <Link to="/demo" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza a demo oldalra
        </Link>
      </header>
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-md w-full text-center">
          {message && <p className="text-lg font-medium">{message}</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>
      </main>
    </div>
  );
}
