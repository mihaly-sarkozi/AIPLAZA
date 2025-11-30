import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";

export default function Navbar() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const isAdmin = user?.role === "admin";
  const isSuperuser = user?.is_superuser === true;

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <nav className="w-full bg-blue-600 text-white p-4 flex justify-between items-center shadow-md fixed top-0 left-0 z-50">

      {/* Bal oldal – Logo + email */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate("/chat")}
          className="font-semibold text-lg hover:opacity-90"
        >
          💬 BrainBankCenter
        </button>

        {user && (
          <span className="text-sm opacity-90">({user.email})</span>
        )}
      </div>

      {/* Jobb oldal – Menüpontok */}
      <div className="flex items-center gap-6">

        {isAdmin && (
        
          <>
            <button
              onClick={() => navigate("/chat")}
              className="hover:underline"
            >
              Chat
            </button>

            <button
              onClick={() => navigate("/kb")}
              className="hover:underline"
            >
              Tudástár
            </button>

            {isSuperuser && (
              <button
                onClick={() => navigate("/admin/roles")}
                className="hover:underline"
              >
                Jogosultság
              </button>
            )}

            <button
              onClick={() => navigate("/admin/settings")}
              className="hover:underline"
            >
              Beállítások
            </button>
          </>
        )}

        <button
          onClick={handleLogout}
          className="text-sm underline hover:text-slate-200"
        >
          Kilépés
        </button>
      </div>
    </nav>
  );
}
