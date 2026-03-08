import { useEffect, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";
import ProtectedRoute from "./features/auth/components/ProtectedRoute";
import { useAuthStore } from "./store/authStore";
import { fetchCsrfToken } from "./api/axiosClient";
import { useLocaleStore } from "./i18n";
import { isTenantSubdomain } from "./utils/domain";
import type { Locale } from "./i18n";
import type { Theme } from "./i18n";

const LandingPage = lazy(() => import("./features/landing/pages/LandingPage"));
const DemoPage = lazy(() => import("./features/demo/pages/DemoPage"));
const LoginPage = lazy(() => import("./features/auth/pages/LoginPage"));
const ForgotPasswordPage = lazy(() => import("./features/auth/pages/ForgotPasswordPage"));
const SetPasswordPage = lazy(() => import("./features/auth/pages/SetPasswordPage"));
const ChatPage = lazy(() => import("./features/chat/pages/ChatPage"));
const ProfilePage = lazy(() => import("./features/profile/pages/ProfilePage"));
const ChangePasswordPage = lazy(() => import("./features/profile/pages/ChangePasswordPage"));
const RolesPage = lazy(() => import("./features/users/pages/RolesPage"));
const TrainPage = lazy(() => import("./features/users/pages/TrainPage"));
const SettingsPage = lazy(() => import("./features/settings/pages/SettingsPage"));
const KBList = lazy(() => import("./features/knowledge-base/pages/KBList"));
const KBEdit = lazy(() => import("./features/knowledge-base/pages/KBEdit"));
const KBTrain = lazy(() => import("./features/knowledge-base/pages/KBTrain"));

// Nagy blokk az első paint-nál, hogy a fő tartalom legyen az LCP jelölt (ne a footer)
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

/** "/" útvonal: fődomain → landing; tenant aldomain → bejelentkezés alapján /chat vagy /login */
function RootRoute() {
    const { user, loadingUser } = useAuthStore();
    if (isTenantSubdomain()) {
        if (loadingUser) return <GuardFallback />;
        if (user) return <Navigate to="/chat" replace />;
        return <Navigate to="/login?redirect=%2Fchat" replace />;
    }
    return <LandingPage />;
}

export default function App() {
    const loadUser = useAuthStore((s) => s.loadUser);
    const user = useAuthStore((s) => s.user);
    const setLocaleAndTheme = useLocaleStore((s) => s.setLocaleAndTheme);

    useEffect(() => {
        const path = window.location.pathname || "";
        (async () => {
            await fetchCsrfToken();
            if (path === "/demo") return;
            if (path === "/" && !isTenantSubdomain()) return;
            if (path === "/login" || path.startsWith("/forgot") || path.startsWith("/set-password")) {
                useAuthStore.getState().setToken(null);
                useAuthStore.setState({ user: null, loadingUser: false });
                return;
            }
            loadUser();
        })();
    }, [loadUser]);

    useEffect(() => {
        if (user?.locale && user?.theme) {
            setLocaleAndTheme(user.locale as Locale, user.theme as Theme);
        }
    }, [user?.id, user?.locale, user?.theme, setLocaleAndTheme]);

    useEffect(() => {
        if (!user) return;
        import("./features/knowledge-base/pages/KBList");
        import("./features/knowledge-base/pages/KBEdit");
        import("./features/knowledge-base/pages/KBTrain");
    }, [user]);

    return (
        <BrowserRouter>
            <Suspense fallback={<PageFallback />}>
                <Routes>
                    {/* NYILVÁNOS: landing (fődomain), demo; tenant aldomain "/" → /chat vagy /login */}
                    <Route path="/" element={<RootRoute />} />
                    <Route path="/demo" element={<DemoPage />} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/forgot" element={<ForgotPasswordPage />} />
                    <Route path="/set-password" element={<SetPasswordPage />} />

                {/* MAIN LAYOUT ALATT MINDEN */}
                <Route element={<MainLayout/>}>

                    <Route
                        path="/chat"
                        element={
                            <ProtectedRoute loadingFallback={<GuardFallback />}>
                                <ChatPage/>
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/profile"
                        element={
                            <ProtectedRoute loadingFallback={<GuardFallback />}>
                                <ProfilePage />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/change-password"
                        element={
                            <ProtectedRoute loadingFallback={<GuardFallback />}>
                                <ChangePasswordPage />
                            </ProtectedRoute>
                        }
                    />

                    {/* ADMIN */}
                    <Route
                        path="/admin/roles"
                        element={
                            <ProtectedRoute allowedRoles={["admin", "owner"]} loadingFallback={<GuardFallback />}>
                                <RolesPage/>
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/admin/train"
                        element={
                            <ProtectedRoute allowedRoles={["admin", "owner"]} loadingFallback={<GuardFallback />}>
                                <TrainPage/>
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/admin/settings"
                        element={
                            <ProtectedRoute allowedRoles={["admin", "owner"]} loadingFallback={<GuardFallback />}>
                                <SettingsPage/>
                            </ProtectedRoute>
                        }
                    />

                    {/* 🔥 KB CRUD OLDALAK */}
                    <Route
                        path="/kb"
                        element={
                            <ProtectedRoute allowedRoles={["admin", "owner"]} loadingFallback={<GuardFallback />}>
                                <KBList/>
                            </ProtectedRoute>
                        }
                    />

                    <Route
                        path="/kb/create"
                        element={<Navigate to="/kb" state={{ openKbCreate: true }} replace />}
                    />
                    <Route path="/kb/train/:uuid" element={<KBTrain/>}/>
                    <Route
                        path="/kb/edit/:uuid"
                        element={
                            <ProtectedRoute allowedRoles={["admin", "owner"]} loadingFallback={<GuardFallback />}>
                                <KBEdit/>
                            </ProtectedRoute>
                        }
                    />

                    <Route path="*" element={<Navigate to="/chat" replace />} />
                </Route>
                </Routes>
            </Suspense>
        </BrowserRouter>
    );
}
