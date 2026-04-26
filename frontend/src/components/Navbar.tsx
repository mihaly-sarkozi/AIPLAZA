import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { GearIcon } from "@radix-ui/react-icons";
import { useTranslation } from "../i18n";
import { useAuthStore, isDemoInitialPasswordMode } from "../store/authStore";
import { hasUserPermission } from "../platform/permissions";

type NavbarProps = {
  onOpenProfile?: () => void;
  onOpenChangePassword?: () => void;
  onOpenSystemSettings?: () => void;
};

export default function Navbar({ onOpenProfile, onOpenChangePassword, onOpenSystemSettings }: NavbarProps) {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const profileMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!profileMenuOpen) return;
      const target = event.target as Node | null;
      if (profileMenuRef.current && target && !profileMenuRef.current.contains(target)) {
        setProfileMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [profileMenuOpen]);

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    navigate("/login", { replace: true });
  };

  const go = (path: string) => {
    setMenuOpen(false);
    setProfileMenuOpen(false);
    navigate(path);
  };

  const leftMenuSections = [
    [
      { key: "chat", label: t("nav.chat"), path: "/chat", visible: Boolean(user) },
      { key: "knowledge", label: t("nav.knowledgeBase"), path: "/kb", visible: hasUserPermission(user, "knowledge.read") },
    ],
    [
      { key: "traffic", label: t("nav.traffic"), path: "/admin/forgalom", visible: hasUserPermission(user, "settings.read") },
      { key: "packages", label: t("nav.packages"), path: "/admin/csomagok", visible: hasUserPermission(user, "settings.read") },
      { key: "billing", label: t("nav.invoices"), path: "/admin/szamlak", visible: hasUserPermission(user, "settings.read") },
    ],
    [
      { key: "roles", label: t("roles.title"), path: "/admin/roles", visible: hasUserPermission(user, "users.write") },
    ],
  ]
    .map((section) => section.filter((item) => item.visible))
    .filter((section) => section.length > 0);

  const showHamburger = !user || user.role === "owner";

  useEffect(() => {
    if (!showHamburger) setMenuOpen(false);
  }, [showHamburger]);

  return (
    <nav className="w-full bg-[var(--color-background)] text-[var(--color-foreground)] border-b border-[var(--color-border)] fixed top-0 left-0 z-50">
      <div className="p-2 flex justify-between items-center">
        {/* Bal oldal: hamburger + BrainBankCenter */}
        <div className="flex items-center gap-2 min-w-0">
          {showHamburger ? (
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              className="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-700 shrink-0"
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
          ) : null}
          <button
            type="button"
            onClick={() => {
              setMenuOpen(false);
              setProfileMenuOpen(false);
              if (user) {
                if (location.pathname !== "/chat") navigate("/chat");
              } else {
                navigate("/");
              }
            }}
            className="font-semibold text-[var(--color-foreground)] truncate hover:underline"
          >
            BrainBankCenter
          </button>
        </div>

        {/* Jobb oldal: név, role + profil beállítás ikon (fogaskerék) */}
        <div ref={profileMenuRef} className="flex items-center gap-2 sm:gap-3 min-w-0 relative">
          {user && (
            <>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  setProfileMenuOpen((v) => !v);
                }}
                className="flex flex-col items-end text-right min-w-0"
                aria-label={t("profile.title")}
              >
                <span className="text-sm text-[var(--color-foreground)] truncate max-w-[120px] sm:max-w-[200px] hover:underline">
                  {user.name?.trim() || user.email}
                </span>
                <span className="text-xs text-[var(--color-muted)]">
                  {user.role === "owner" ? t("roles.roleOwner") : user.role === "admin" ? t("roles.roleAdmin") : t("roles.roleUser")}
                </span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  setProfileMenuOpen((v) => !v);
                }}
                className="p-2 rounded hover:bg-gray-200 dark:hover:bg-gray-700 shrink-0"
                aria-label={t("nav.settings")}
              >
                <GearIcon className="w-5 h-5 text-[var(--color-foreground)]" />
              </button>
              {profileMenuOpen && (
                <div className="absolute right-0 top-full mt-2 w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] shadow-lg py-1 z-[60]">
                  <button
                    onClick={() => {
                      if (onOpenProfile) {
                        setProfileMenuOpen(false);
                        onOpenProfile();
                        return;
                      }
                      go("/profile");
                    }}
                    className="w-full text-left px-4 py-2 text-sm hover:bg-[var(--color-border)]/20"
                  >
                    {t("nav.account")}
                  </button>
                  <button
                    onClick={() => {
                      if (onOpenChangePassword) {
                        setProfileMenuOpen(false);
                        onOpenChangePassword();
                        return;
                      }
                      go("/change-password");
                    }}
                    className="w-full text-left px-4 py-2 text-sm hover:bg-[var(--color-border)]/20"
                  >
                    {t(user && isDemoInitialPasswordMode(user) ? "nav.setInitialPassword" : "nav.changePassword")}
                  </button>
                  {user?.role === "owner" ? (
                    <button
                      onClick={() => {
                        if (onOpenSystemSettings) {
                          setProfileMenuOpen(false);
                          onOpenSystemSettings();
                          return;
                        }
                        go("/admin/settings?section=system");
                      }}
                      className="w-full text-left px-4 py-2 text-sm hover:bg-[var(--color-border)]/20"
                    >
                      {t("nav.systemSettings")}
                    </button>
                  ) : null}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Lenyíló menü – keskeny, balra igazított sáv */}
      {showHamburger && menuOpen && (
        <div className="absolute left-2 top-full mt-2 w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] shadow-lg py-2 z-[60]">
          {leftMenuSections.map((section, sectionIdx) => (
            <div key={`menu-section-${sectionIdx}`} className="flex flex-col gap-1 px-2">
              {section.map((item) => (
                <button
                  key={item.key}
                  onClick={() => go(item.path)}
                  className="w-full rounded-md px-2 py-2 text-left text-sm text-[var(--color-muted)] hover:bg-[var(--color-border)]/20 hover:text-[var(--color-foreground)]"
                >
                  {item.label}
                </button>
              ))}
              {sectionIdx < leftMenuSections.length - 1 ? (
                <div className="my-2 border-t border-gray-200 dark:border-gray-600" />
              ) : null}
            </div>
          ))}
          {user && (
            <button
              onClick={handleLogout}
              className="mx-2 mt-2 w-[calc(100%-1rem)] border-t border-gray-200 px-2 pt-3 text-left text-sm text-red-600 hover:text-red-700 dark:border-gray-600 dark:text-red-400 dark:hover:text-red-300"
            >
              {t("common.logout")}
            </button>
          )}
        </div>
      )}
    </nav>
  );
}
