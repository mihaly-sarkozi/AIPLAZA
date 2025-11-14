import { useEffect, type JSX } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import MainLayout from "./layouts/MainLayout";

import LoginPage from "./pages/LoginPage";
import ChatPage from "./pages/ChatPage";

import RolesPage from "./pages/Admin/RolesPage";
import TrainPage from "./pages/Admin/TrainPage";
import SettingsPage from "./pages/Admin/SettingsPage";

import { useAuthStore } from "./store/authStore";

// 🔹 Csak bejelentkezett user mehet tovább
function AuthGuard({ children }: { children: JSX.Element }) {
  const { user, loadingUser } = useAuthStore();

  if (loadingUser) {
    return <div className="text-center p-10 text-white">Betöltés...</div>;
  }

  return user ? children : <Navigate to="/login" replace />;
}

// 🔹 Csak admin role mehet tovább
function AdminGuard({ children }: { children: JSX.Element }) {
  const { user, loadingUser } = useAuthStore();

  if (loadingUser) {
    return <div className="text-center p-10 text-white">Betöltés...</div>;
  }

  return user?.role === "admin"
    ? children
    : <Navigate to="/chat" replace />;
}

export default function App() {
  const { loadUser } = useAuthStore();

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <BrowserRouter>
      <Routes>

        {/* Login layout nélkül */}
        <Route path="/login" element={<LoginPage />} />

        {/* Minden más layout-tal */}
        <Route element={<MainLayout />}>

          <Route
            path="/chat"
            element={
              <AuthGuard>
                <ChatPage />
              </AuthGuard>
            }
          />

          {/* Admin oldalak */}
          <Route
            path="/admin/roles"
            element={
              <AdminGuard>
                <RolesPage />
              </AdminGuard>
            }
          />

          <Route
            path="/admin/train"
            element={
              <AdminGuard>
                <TrainPage />
              </AdminGuard>
            }
          />

          <Route
            path="/admin/settings"
            element={
              <AdminGuard>
                <SettingsPage />
              </AdminGuard>
            }
          />

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/chat" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
