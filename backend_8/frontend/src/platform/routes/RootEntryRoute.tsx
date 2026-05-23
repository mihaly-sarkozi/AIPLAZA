import { Navigate } from "react-router-dom";

import LandingPage from "../../features/landing/pages/LandingPage";
import { useAuthStore } from "../../store/authStore";
import { isTenantSubdomain } from "../../utils/domain";

const GuardFallback = () => (
  <div className="min-h-[70vh] flex items-center justify-center text-black text-lg" role="status" aria-live="polite">
    Betöltés…
  </div>
);

export default function RootEntryRoute() {
  const { user, loadingUser } = useAuthStore();

  if (isTenantSubdomain()) {
    if (loadingUser) return <GuardFallback />;
    if (user) return <Navigate to="/chat" replace />;
    return <Navigate to="/login?redirect=%2Fchat" replace />;
  }

  return <LandingPage />;
}
