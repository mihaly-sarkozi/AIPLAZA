import { useState, useEffect, lazy, Suspense } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ProfileModal from "../features/profile/components/ProfileModal";
import ChangePasswordModal from "../features/profile/components/ChangePasswordModal";
import SettingsModal from "../features/settings/components/SettingsModal";

const Footer = lazy(() => import("../components/Footer"));
import { Outlet } from "react-router-dom";
import { isDemoInitialPasswordMode, useAuthStore } from "../store/authStore";
import { hasUserPermission } from "../platform/permissions";
import { useKbList } from "../features/knowledge-base/hooks/useKb";

export default function MainLayout() {
  const [showFooter, setShowFooter] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showChangePasswordModal, setShowChangePasswordModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const loadingUser = useAuthStore((s) => s.loadingUser);
  const isFullHeight = location.pathname === "/chat" || location.pathname === "/onboarding/train";
  const shouldCheckOnboardingTraining =
    user?.tenant_demo_mode === true &&
    user.tenant_kb_has_training !== true &&
    hasUserPermission(user, "knowledge.write");
  const {
    data: availableKbList = [],
    isLoading: loadingAvailableKbList,
    isError: availableKbListError,
  } = useKbList({ enabled: shouldCheckOnboardingTraining });

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => setShowFooter(true));
    });
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    const state = location.state as { openChangePassword?: boolean };
    if (state?.openChangePassword) {
      navigate("/change-password", { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  useEffect(() => {
    if (loadingUser || !user) return;
    const path = location.pathname;
    if (isDemoInitialPasswordMode(user)) {
      if (path !== "/change-password") {
        navigate("/change-password", { replace: true });
      }
      return;
    }
    if (!shouldCheckOnboardingTraining) return;
    if (loadingAvailableKbList || availableKbListError) return;
    if (availableKbList.some((kb) => kb.has_training === true)) return;
    if (path.startsWith("/onboarding")) return;
    if (path === "/profile" || path.startsWith("/profile/")) return;
    if (path === "/change-password") return;
    if (path.startsWith("/admin")) return;
    if (path.startsWith("/kb")) return;
    navigate("/onboarding/train", { replace: true });
  }, [
    user,
    loadingUser,
    shouldCheckOnboardingTraining,
    loadingAvailableKbList,
    availableKbListError,
    availableKbList,
    location.pathname,
    navigate,
  ]);

  return (
    <div
      className={`flex flex-col bg-[var(--color-background)] text-[var(--color-foreground)] ${
        isFullHeight ? "h-screen overflow-hidden" : "min-h-screen"
      }`}
    >
      <Navbar
        onOpenProfile={() => setShowProfileModal(true)}
        onOpenChangePassword={() => setShowChangePasswordModal(true)}
        onOpenSystemSettings={() => setShowSettingsModal(true)}
      />

      <main
        className={`pt-20 flex-1 min-h-0 flex flex-col ${isFullHeight ? "overflow-hidden" : ""}`}
        aria-label="Fő tartalom"
      >
        <Outlet />
      </main>

      {showFooter && (
        <Suspense fallback={null}>
          <Footer />
        </Suspense>
      )}
      <ProfileModal isOpen={showProfileModal} onClose={() => setShowProfileModal(false)} />
      <ChangePasswordModal isOpen={showChangePasswordModal} onClose={() => setShowChangePasswordModal(false)} />
      <SettingsModal isOpen={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
    </div>
  );
}
