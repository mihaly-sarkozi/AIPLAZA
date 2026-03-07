import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "../i18n";
import { useAuthStore } from "../store/authStore";

interface NavbarProps {
  onOpenProfile?: () => void;
  onOpenChangePassword?: () => void;
}

export default function Navbar({ onOpenProfile, onOpenChangePassword }: NavbarProps) {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

  const isAdminOrOwner = user?.role === "admin" || user?.role === "owner";

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate("/login", { replace: true });
  };

  const go = (path: string) => {
    setMenuOpen(false);
    navigate(path);
  };

  const menuLinks = (
    <>
      {user && (
        <button onClick={() => go("/chat")} className="text-sm text-[var(--color-muted)] hover:text-[var(--color-foreground)] py-2">
          {t("nav.chat")}
        </button>
      )}
      {isAdminOrOwner && (
        <>
          <button onClick={() => go("/kb")} className="text-sm text-[var(--color-muted)] hover:text-[var(--color-foreground)] py-2">
            {t("nav.knowledgeBase")}
          </button>
          <button onClick={() => go("/admin/roles")} className="text-sm text-[var(--color-muted)] hover:text-[var(--color-foreground)] py-2">
            {t("nav.permissions")}
          </button>
          {user?.role === "owner" && (
            <button onClick={() => go("/admin/settings")} className="text-sm text-[var(--color-muted)] hover:text-[var(--color-foreground)] py-2">
              {t("nav.settings")}
            </button>
          )}
        </>
      )}
    </>
  );

  return (
    <nav className="w-full bg-[var(--color-background)] text-[var(--color-foreground)] border-b border-[var(--color-border)] fixed top-0 left-0 z-50">
      <div className="p-4 flex justify-between items-center">
        {/* Bal oldal: csak hamburger menü */}
        <button
          type="button"
          onClick={() => setMenuOpen((o) => !o)}
          className="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
          aria-expanded={menuOpen}
          aria-label={menuOpen ? "Menü bezárása" : "Menü"}
        >
          {menuOpen ? (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          )}
        </button>

        {/* Jobb oldal: név kattintható, profil felugró */}
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {user && (
            <>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onOpenProfile?.();
                }}
                className="text-sm text-[var(--color-foreground)] truncate max-w-[120px] sm:max-w-[200px] text-left hover:underline"
                aria-label={t("profile.title")}
              >
                {user.name?.trim() || user.email}
              </button>
              <span className="text-xs text-[var(--color-muted)] shrink-0">
                ({user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser")})
              </span>
            </>
          )}
        </div>
      </div>

      {/* Lenyíló menü – halványszürke háttér, kilépés alul piros */}
      {menuOpen && (
        <div className="border-t border-[var(--color-border)] bg-[var(--color-background)] px-4 py-3 flex flex-col gap-1 [&>button]:text-left [&>button]:w-full">
          {menuLinks}
          {user && (
            <button
              onClick={() => {
                setMenuOpen(false);
                onOpenChangePassword?.();
              }}
              className="text-sm text-[var(--color-muted)] hover:text-[var(--color-foreground)] py-2"
            >
              {t("nav.changePassword")}
            </button>
          )}
          <button
            onClick={handleLogout}
            className="text-sm text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 py-2 mt-2 pt-3 border-t border-gray-200 dark:border-gray-600"
          >
            {t("common.logout")}
          </button>
        </div>
      )}
    </nav>
  );
}
