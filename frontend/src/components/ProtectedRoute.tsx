import { Navigate, Link, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { useTranslation } from "../i18n";
import { getSafeLoginRedirect } from "../utils/loginRedirect";
import type { ReactNode } from "react";

export type AllowedRole = "user" | "admin" | "owner";

interface ProtectedRouteProps {
  children: ReactNode;
  allowedRoles?: Array<AllowedRole>;
  loadingFallback?: ReactNode;
}

export default function ProtectedRoute({ children, allowedRoles, loadingFallback }: ProtectedRouteProps) {
  const { token, user, loadingUser } = useAuthStore();
  const { t } = useTranslation();
  const location = useLocation();

  if (loadingUser && loadingFallback) return <>{loadingFallback}</>;
  if (!token || !user) {
    const safePath = getSafeLoginRedirect(location.pathname || "/chat");
    const redirect = safePath !== "/chat" ? `?redirect=${encodeURIComponent(safePath)}` : "";
    return <Navigate to={`/login${redirect}`} replace />;
  }
  if (allowedRoles != null && allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-4 p-6 text-black">
        <p className="text-lg">{t("common.accessDenied")}</p>
        <Link to="/chat" className="text-blue-600 underline">
          {t("nav.chat")}
        </Link>
      </div>
    );
  }
  return <>{children}</>;
}
