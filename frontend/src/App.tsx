import { useEffect, lazy, Suspense, type JSX } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import { useAuthStore } from "./store/authStore";
import { fetchCsrfToken } from "./api/axiosClient";
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

export default function App() {
    const loadUser = useAuthStore((s) => s.loadUser);
    const user = useAuthStore((s) => s.user);
    const setLocaleAndTheme = useLocaleStore((s) => s.setLocaleAndTheme);

    useEffect(() => {
        const path = window.location.pathname || "";
        (async () => {
            await fetchCsrfToken();
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

    // Prefetch likely next routes (KB pages) after login so navigation is instant
    useEffect(() => {
        if (!user) return;
        import("./pages/KB/KBList");
        import("./pages/KB/KBEdit");
        import("./pages/KB/KBTrain");
    }, [user]);

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
                            <ProtectedRoute loadingFallback={<GuardFallback />}>
                                <ChatPage/>
                            </ProtectedRoute>
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
