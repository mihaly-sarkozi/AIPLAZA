import { lazy, useEffect, Suspense, useMemo, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import api, { fetchCsrfToken } from "../api/axiosClient";
import ErrorBoundary from "../components/ErrorBoundary";
import { useLocaleStore, useTranslation } from "../i18n";
import type { Locale, Theme } from "../i18n";
import MainLayout from "../layouts/MainLayout";
import { useAuthStore } from "../store/authStore";
import { getTenantBaseDomain, isTenantSubdomain } from "../utils/domain";
import ProtectedRoute from "../features/auth/components/ProtectedRoute";
import { getAuthenticatedFallbackPath, getModuleRoutes, preloadFrontendModules } from "./moduleRegistry";
import type { ModuleRouteDefinition } from "./moduleTypes";

const PageFallback = () => (
  <div className="min-h-[70vh] flex items-center justify-center text-black text-lg" role="status" aria-live="polite">
    Betöltés…
  </div>
);

const GuardFallback = () => (
  <div className="min-h-[70vh] flex items-center justify-center text-black text-lg" role="status" aria-live="polite">
    Betöltés…
  </div>
);

function UnknownTenantHostPage() {
  const { t } = useTranslation();
  const mainDomainUrl = useMemo(() => {
    if (typeof window === "undefined") return `https://${getTenantBaseDomain()}`;
    const port = window.location.port ? `:${window.location.port}` : "";
    return `${window.location.protocol}//${getTenantBaseDomain()}${port}`;
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="max-w-xl text-center">
        <p className="text-6xl font-bold mb-4">404</p>
        <h1 className="text-2xl md:text-3xl font-semibold mb-3">{t("tenantNotFound.title")}</h1>
        <p className="text-[var(--color-muted-foreground)] mb-8">{t("tenantNotFound.description")}</p>
        <a
          href={mainDomainUrl}
          className="inline-flex items-center justify-center px-5 py-3 rounded-lg bg-[var(--color-primary)] text-[var(--color-on-primary)] font-medium hover:opacity-90 transition"
        >
          {t("tenantNotFound.backToMain")}
        </a>
      </div>
    </div>
  );
}

function ServiceDeletedStandalonePage() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="max-w-2xl text-center">
        <h1 className="text-2xl md:text-3xl font-semibold mb-4">{t("serviceDeleted.title")}</h1>
        <p className="text-[var(--color-muted-foreground)]">{t("serviceDeleted.description")}</p>
      </div>
    </div>
  );
}

function ScrollToTopOnRouteChange() {
  const location = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [location.pathname]);

  return null;
}

function renderRoute(route: ModuleRouteDefinition) {
  let element = null;

  if (route.loader) {
    const Component = lazy(route.loader);
    element = <Component />;
  }
  if (!element && route.redirectTo) {
    element = <Navigate to={route.redirectTo} state={route.redirectState} replace />;
  }
  if (!element) return null;

  if (route.requiresAuth || route.requiredPermission) {
    element = (
      <ProtectedRoute
        loadingFallback={<GuardFallback />}
        requiredPermission={route.requiredPermission}
      >
        {element}
      </ProtectedRoute>
    );
  }

  return <Route key={route.key} path={route.path} element={element} />;
}

export default function AppShell() {
  const loadUser = useAuthStore((state) => state.loadUser);
  const user = useAuthStore((state) => state.user);
  const setLocaleAndTheme = useLocaleStore((state) => state.setLocaleAndTheme);
  const [tenantHostStatus, setTenantHostStatus] = useState<"checking" | "valid" | "invalid">(
    isTenantSubdomain() ? "checking" : "valid",
  );

  useEffect(() => {
    if (!isTenantSubdomain()) {
      setTenantHostStatus("valid");
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        await api.get("/auth/default-settings");
        if (!cancelled) setTenantHostStatus("valid");
      } catch (error) {
        const status = (error as { response?: { status?: number } })?.response?.status;
        if (!cancelled) setTenantHostStatus(status === 404 ? "invalid" : "valid");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (tenantHostStatus !== "valid") return;
    const path = window.location.pathname || "";
    void (async () => {
      if (path === "/demo" || path === "/demo-login" || path === "/demo-expired") return;
      if (path.startsWith("/platform-admin")) return;
      if (path === "/" && !isTenantSubdomain()) return;
      if (path === "/service-deleted") {
        useAuthStore.getState().setToken(null);
        useAuthStore.setState({ user: null, loadingUser: false });
        return;
      }
      await fetchCsrfToken();
      if (path === "/login" || path.startsWith("/forgot") || path.startsWith("/set-password") || path.startsWith("/confirm-email")) {
        // Ne töröljük a sessiont: a 2FA/login flow közben és után is kell a token.
        // A nyilvános auth oldalak nem hívják a loadUser-t; a ProtectedRoute kezeli a redirectet.
        useAuthStore.setState({ loadingUser: false });
        return;
      }
      await loadUser();
    })();
  }, [loadUser, tenantHostStatus]);

  useEffect(() => {
    if (user?.locale && user?.theme) {
      setLocaleAndTheme(user.locale as Locale, user.theme as Theme);
    }
  }, [setLocaleAndTheme, user?.id, user?.locale, user?.theme]);

  useEffect(() => {
    preloadFrontendModules(user);
  }, [user]);

  const publicRoutes = getModuleRoutes("public");
  const mainRoutes = getModuleRoutes("main");
  const fallbackPath = getAuthenticatedFallbackPath();

  if (tenantHostStatus === "checking") return <GuardFallback />;
  if (tenantHostStatus === "invalid" && (typeof window !== "undefined" ? window.location.pathname === "/service-deleted" : false)) {
    return <ServiceDeletedStandalonePage />;
  }
  if (tenantHostStatus === "invalid") return <UnknownTenantHostPage />;

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ScrollToTopOnRouteChange />
        <Suspense fallback={<PageFallback />}>
          <Routes>
            {publicRoutes.map(renderRoute)}
            <Route element={<MainLayout />}>
              {mainRoutes.map(renderRoute)}
              <Route path="*" element={<Navigate to={fallbackPath} replace />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
