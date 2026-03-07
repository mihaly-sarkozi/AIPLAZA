import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import ProfileModal from "../components/ProfileModal";
import ChangePasswordModal from "../components/ChangePasswordModal";
import { Outlet } from "react-router-dom";

export default function MainLayout() {
  const [showFooter, setShowFooter] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showChangePasswordModal, setShowChangePasswordModal] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => setShowFooter(true));
    });
    return () => cancelAnimationFrame(id);
  }, []);

  useEffect(() => {
    const state = location.state as { openProfile?: boolean; openChangePassword?: boolean };
    if (state?.openProfile) {
      setShowProfileModal(true);
      navigate(location.pathname, { replace: true, state: {} });
    }
    if (state?.openChangePassword) {
      setShowChangePasswordModal(true);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  return (
    <div className="min-h-screen flex flex-col bg-[var(--color-background)] text-[var(--color-foreground)]">
      <Navbar
        onOpenProfile={() => setShowProfileModal(true)}
        onOpenChangePassword={() => setShowChangePasswordModal(true)}
      />

      <main className="pt-20 flex-1 min-h-0 flex flex-col" aria-label="Fő tartalom">
        <Outlet />
      </main>

      {showFooter && <Footer />}

      <ProfileModal isOpen={showProfileModal} onClose={() => setShowProfileModal(false)} />
      <ChangePasswordModal isOpen={showChangePasswordModal} onClose={() => setShowChangePasswordModal(false)} />
    </div>
  );
}
