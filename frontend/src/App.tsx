import {useEffect, type JSX} from "react";
import {BrowserRouter, Routes, Route, Navigate} from "react-router-dom";

import MainLayout from "./layouts/MainLayout";

import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";

import RolesPage from "./pages/Admin/RolesPage";
import TrainPage from "./pages/Admin/TrainPage";
import SettingsPage from "./pages/Admin/SettingsPage";

import KBList from "./pages/KB/KBList";
import KBCreate from "./pages/KB/KBCreate";
import KBEdit from "./pages/KB/KBEdit";
import KBTrain from "./pages/KB/KBTrain";

import {useAuthStore} from "./store/authStore";

function AuthGuard({children}: { children: JSX.Element }) {
    const {user, loadingUser} = useAuthStore();
    if (loadingUser) return <div className="text-white">Betöltés...</div>;
    return user ? children : <Navigate to="/login" replace/>;
}

function AdminGuard({children}: { children: JSX.Element }) {
    const {user, loadingUser} = useAuthStore();
    if (loadingUser) return <div className="text-white">Betöltés...</div>;
    return user?.role === "admin" ? children : <Navigate to="/chat" replace/>;
}

function SuperuserGuard({children}: { children: JSX.Element }) {
    const {user, loadingUser} = useAuthStore();
    if (loadingUser) return <div className="text-white">Betöltés...</div>;
    return user?.is_superuser === true ? children : <Navigate to="/chat" replace/>;
}

export default function App() {
    const {loadUser} = useAuthStore();

    useEffect(() => {
        loadUser();
    }, [loadUser]);

    return (
        <BrowserRouter>
            <Routes>

                {/* LOGIN VÉDÉS NÉLKÜL */}
                <Route path="/login" element={<LoginPage/>}/>

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

                    {/* ADMIN */}
                    <Route
                        path="/admin/roles"
                        element={
                            <SuperuserGuard>
                                <RolesPage/>
                            </SuperuserGuard>
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
                        element={
                            <AdminGuard>
                                <KBCreate/>
                            </AdminGuard>
                        }
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

                    <Route path="*" element={<Navigate to="/chat" replace/>}/>

                </Route>
            </Routes>
        </BrowserRouter>
    );
}
