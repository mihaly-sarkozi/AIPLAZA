import { lazy, useEffect, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";

import { fetchCsrfToken } from "../api/axiosClient";
import ErrorBoundary from "../components/ErrorBoundary";
import { useLocaleStore } from "../i18n";
import type { Locale, Theme } from "../i18n";
import MainLayout from "../layouts/MainLayout";
import { useAuthStore } from "../store/authStore";
import { isTenantSubdomain } from "../utils/domain";
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

  useEffect(() => {
    const path = window.location.pathname || "";
    void (async () => {
      if (path === "/demo" || path === "/demo-login" || path === "/demo-expired") return;
      if (path === "/" && !isTenantSubdomain()) return;
      await fetchCsrfToken();
      if (path === "/login" || path.startsWith("/forgot") || path.startsWith("/set-password")) {
        useAuthStore.getState().setToken(null);
        useAuthStore.setState({ user: null, loadingUser: false });
        return;
      }
      await loadUser();
    })();
  }, [loadUser]);

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
