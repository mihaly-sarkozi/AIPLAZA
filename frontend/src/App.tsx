import { useEffect, lazy, Suspense, type JSX } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";
import { useAuthStore } from "./store/authStore";
import { useLocaleStore } from "./i18n";
import type { Locale } from "./i18n";
import type { Theme } from "./i18n";

// Lazy: csak akkor töltődik, amikor az adott útvonalra navigálsz
const LoginPage = lazy(() => import("./pages/LoginPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const SetPasswordPage = lazy(() => import("./pages/SetPasswordPage"));
const ChatPage = lazy(() => import("./pages/ChatPage"));
const RolesPage = lazy(() => import("./pages/Admin/RolesPage"));
const TrainPage = lazy(() => import("./pages/Admin/TrainPage"));
const SettingsPage = lazy(() => import("./pages/Admin/SettingsPage"));
const KBList = lazy(() => import("./pages/KB/KBList"));
const KBEdit = lazy(() => import("./pages/KB/KBEdit"));
const KBTrain = lazy(() => import("./pages/KB/KBTrain"));

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

function AuthGuard({ children }: { children: JSX.Element }) {
    const user = useAuthStore((s) => s.user);
    const loadingUser = useAuthStore((s) => s.loadingUser);
    const location = useLocation();
    if (loadingUser) return <GuardFallback />;
    if (!user) {
        const redirect = encodeURIComponent(location.pathname || "/chat");
        return <Navigate to={`/login?redirect=${redirect}`} replace />;
    }
    return children;
}

function AdminGuard({ children }: { children: JSX.Element }) {
    const user = useAuthStore((s) => s.user);
    const loadingUser = useAuthStore((s) => s.loadingUser);
    if (loadingUser) return <GuardFallback />;
    return (user?.role === "admin" || user?.role === "owner") ? children : <Navigate to="/chat" replace />;
}

export default function App() {
    const loadUser = useAuthStore((s) => s.loadUser);
    const user = useAuthStore((s) => s.user);
    const setLocaleAndTheme = useLocaleStore((s) => s.setLocaleAndTheme);

    useEffect(() => {
        const path = window.location.pathname || "";
        if (path === "/login" || path.startsWith("/forgot") || path.startsWith("/set-password")) {
            useAuthStore.getState().setToken(null);
            useAuthStore.setState({ user: null, loadingUser: false });
            return;
        }
        loadUser();
    }, [loadUser]);

    useEffect(() => {
        if (user?.locale && user?.theme) {
            setLocaleAndTheme(user.locale as Locale, user.theme as Theme);
        }
    }, [user?.id, user?.locale, user?.theme, setLocaleAndTheme]);

    return (
        <BrowserRouter>
            <Suspense fallback={<PageFallback />}>
                <Routes>
                    {/* LOGIN / REGISZTRÁCIÓ (auth nélkül) */}
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/forgot" element={<ForgotPasswordPage />} />
                    <Route path="/set-password" element={<SetPasswordPage />} />

                {/* MAIN LAYOUT ALATT MINDEN */}
                <Route element={<MainLayout/>}>

                    <Route
                        path="/chat"
                        element={
                            <AuthGuard>
                                <ChatPage/>
                            </AuthGuard>
                        }
                    />

                    <Route
                        path="/profile"
                        element={<Navigate to="/chat" state={{ openProfile: true }} replace />}
                    />
                    <Route
                        path="/change-password"
                        element={<Navigate to="/chat" state={{ openChangePassword: true }} replace />}
                    />

                    {/* ADMIN */}
                    <Route
                        path="/admin/roles"
                        element={
                            <AdminGuard>
                                <RolesPage/>
                            </AdminGuard>
                        }
                    />

                    <Route
                        path="/admin/train"
                        element={
                            <AdminGuard>
                                <TrainPage/>
                            </AdminGuard>
                        }
                    />

                    <Route
                        path="/admin/settings"
                        element={
                            <AdminGuard>
                                <SettingsPage/>
                            </AdminGuard>
                        }
                    />

                    {/* 🔥 KB CRUD OLDALAK */}
                    <Route
                        path="/kb"
                        element={
                            <AdminGuard>
                                <KBList/>
                            </AdminGuard>
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
                            <AdminGuard>
                                <KBEdit/>
                            </AdminGuard>
                        }
                    />

                    <Route path="*" element={<Navigate to="/chat" replace />} />
                </Route>
                </Routes>
            </Suspense>
        </BrowserRouter>
    );
}
