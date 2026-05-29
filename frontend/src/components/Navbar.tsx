import { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { GearIcon } from "@radix-ui/react-icons";
import { useTranslation } from "../i18n";
import { useAuthStore, isDemoInitialPasswordMode } from "../store/authStore";
import { hasUserPermission } from "../platform/permissions";
import { useBillingOverview } from "../features/billing/hooks/useBilling";
import { getModuleMenuDefinitions } from "../platform/moduleRegistry";

type NavbarProps = {
  onOpenProfile?: () => void;
  onOpenChangePassword?: () => void;
  topOffsetClassName?: string;
};

export default function Navbar({
  onOpenProfile,
  onOpenChangePassword,
  topOffsetClassName = "top-0",
}: NavbarProps) {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const { data: billingOverview } = useBillingOverview({ enabled: user?.role === "owner" });
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const hamburgerButtonRef = useRef<HTMLDivElement | null>(null);
  const hamburgerMenuRef = useRef<HTMLDivElement | null>(null);
  const profileMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null;
      if (profileMenuOpen && profileMenuRef.current && target && !profileMenuRef.current.contains(target)) {
        setProfileMenuOpen(false);
      }
      const clickedHamburgerButton = Boolean(hamburgerButtonRef.current && target && hamburgerButtonRef.current.contains(target));
      const clickedHamburgerMenu = Boolean(hamburgerMenuRef.current && target && hamburgerMenuRef.current.contains(target));
      if (menuOpen && !clickedHamburgerButton && !clickedHamburgerMenu) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [menuOpen, profileMenuOpen]);

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

  const hasPaidInvoice = (billingOverview?.invoices ?? []).some((invoice) => {
    const status = String(invoice.status ?? "").trim().toLowerCase();
    return status === "paid" || status === "simulated_paid";
  });

  const visibleMenuItems = getModuleMenuDefinitions()
    .filter((item) => (item.requiresAuth ? Boolean(user) : true))
    .filter((item) => (item.requiredPermission ? hasUserPermission(user, item.requiredPermission) : true))
    .filter((item) => (item.key === "billing.menu" ? user?.role === "owner" || hasPaidInvoice : true))
    .sort((a, b) => (a.order ?? 999) - (b.order ?? 999))
    .map((item) => ({
      key: item.key,
      label: t(item.labelKey),
      path: item.path,
      order: item.order ?? 999,
    }));

  const profileMenuItems = visibleMenuItems.filter((item) => item.key === "users.roles.menu" || item.key === "settings.system");

  const leftMenuSections = [
    visibleMenuItems.filter((item) => item.order < 30),
    visibleMenuItems.filter((item) => item.order >= 30 && item.order < 50),
    visibleMenuItems.filter((item) => item.order >= 50),
  ].filter((section) => section.length > 0);

  const showHamburger = !user || visibleMenuItems.length > 0;

  useEffect(() => {
    if (!showHamburger) setMenuOpen(false);
  }, [showHamburger]);

  return (
    <nav className={`w-full bg-[var(--color-background)] text-[var(--color-foreground)] border-b border-[var(--color-border)] fixed ${topOffsetClassName} left-0 z-50`}>
      <div className="p-2 flex justify-between items-center">
        {/* Bal oldal: hamburger + BrainBankCenter */}
        <div ref={hamburgerButtonRef} className="flex items-center gap-2 min-w-0">
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
                className="p-2 rounded shrink-0 hover:bg-gray-200 dark:hover:bg-gray-700"
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
                  {profileMenuItems.length > 0 ? <div className="my-1 border-t border-[var(--color-border)]" /> : null}
                  {profileMenuItems.map((item) => (
                    <button
                      key={`profile-${item.key}`}
                      onClick={() => go(item.path)}
                      className="w-full text-left px-4 py-2 text-sm hover:bg-[var(--color-border)]/20"
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Lenyíló menü – keskeny, balra igazított sáv */}
      {showHamburger && menuOpen && (
        <div ref={hamburgerMenuRef} className="absolute left-2 top-full mt-2 w-56 rounded-lg border border-[var(--color-border)] bg-[var(--color-background)] shadow-lg py-2 z-[60]">
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
