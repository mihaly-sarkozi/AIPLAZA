import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";

import { fetchPlatformAdminMfaStatus } from "../api";
import { usePlatformAdminStore } from "../state";
import PlatformAdminMfaRequired from "./PlatformAdminMfaRequired";

export default function PlatformAdminLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { user, loadingUser, loadUser, logout } = usePlatformAdminStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mfaEnabled, setMfaEnabled] = useState<boolean | null>(null);
  const platformAdminMfaRequired = import.meta.env.VITE_PLATFORM_ADMIN_MFA_REQUIRED === "true";

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  useEffect(() => {
    if (!loadingUser && !user) navigate("/platform-admin/login", { replace: true });
  }, [loadingUser, navigate, user]);

  useEffect(() => {
    if (!platformAdminMfaRequired) {
      setMfaEnabled(true);
      return;
    }
    if (loadingUser || !user) {
      setMfaEnabled(null);
      return;
    }
    if (user.mfa_enabled) {
      setMfaEnabled(true);
      return;
    }
    let cancelled = false;
    fetchPlatformAdminMfaStatus()
      .then((status) => {
        if (!cancelled) setMfaEnabled(Boolean(status.enabled));
      })
      .catch(() => {
        if (!cancelled) setMfaEnabled(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadingUser, platformAdminMfaRequired, user]);

  const menuItems = [
    { path: "/platform-admin", label: "Áttekintés", end: true },
    { path: "/platform-admin/statistics", label: "Statisztika" },
    { path: "/platform-admin/audit", label: "Audit napló" },
    { path: "/platform-admin/monitoring/security", label: "Monitoring" },
    { path: "/platform-admin/datum-szimulacio", label: "Dátum szimuláció" },
    { path: "/platform-admin/mfa", label: "MFA beállítás" },
  ];

  if (loadingUser) {
    return <div className="flex min-h-screen items-center justify-center">Betöltés...</div>;
  }
  if (!user) return null;
  if (mfaEnabled === null) {
    return <div className="flex min-h-screen items-center justify-center">Biztonsági állapot ellenőrzése...</div>;
  }
  if (!mfaEnabled) {
    return <PlatformAdminMfaRequired onCompleted={() => setMfaEnabled(true)} />;
  }

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)]">
      <header className="sticky top-0 z-40 border-b border-[var(--color-border)] bg-[var(--color-background)]">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="relative flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              className="rounded-lg border border-[var(--color-border)] p-2 hover:bg-[var(--color-border)]/30"
              aria-expanded={menuOpen}
              aria-label={menuOpen ? "Menü bezárása" : "Menü megnyitása"}
            >
              {menuOpen ? (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
            <Link to="/platform-admin" onClick={() => setMenuOpen(false)} className="font-bold">
              BrainBankCenter
            </Link>
            {menuOpen ? (
              <div className="absolute left-0 top-full mt-3 w-64 rounded-2xl border border-[var(--color-border)] bg-[var(--color-card)] p-2 shadow-xl">
                {menuItems.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.end}
                    onClick={() => setMenuOpen(false)}
                    className={({ isActive }) =>
                      `block rounded-xl px-4 py-3 text-sm ${
                        isActive ? "bg-[var(--color-border)]/40 font-semibold" : "text-[var(--color-muted)] hover:bg-[var(--color-border)]/30"
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            ) : null}
          </div>
          <div className="flex items-center gap-2 text-sm">
            <button
              onClick={() => {
                void logout();
                navigate("/platform-admin/login", { replace: true });
              }}
              className="rounded-lg px-3 py-2 text-red-600 hover:bg-red-50"
            >
              Kilépés
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        {children}
      </main>
    </div>
  );
}

