import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axiosClient";
import { useAuthStore } from "../store/authStore";

export default function Login() {
  const navigate = useNavigate();
  const { setToken, setUser } = useAuthStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    try {
      const res = await api.post("/auth/login", {
        email,
        password,
        remember,
      });

      const { access_token, user } = res.data;

      setToken(access_token);
      setUser(user);

      navigate("/chat");
    } catch (err: any) {
      console.error("Login error:", err);
      if (err.response?.status === 401)
        setError("Hibás email vagy jelszó.");
      else setError("Ismeretlen hiba történt. Próbáld újra.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white">
      <div className="bg-slate-800 p-8 rounded-2xl shadow-md w-full max-w-md">
        <h1 className="text-3xl font-bold text-center mb-6">Bejelentkezés</h1>

        {/* 🔴 Hibaüzenet blokk */}
        {error && (
          <div className="bg-red-600/20 border border-red-500 text-red-300 p-3 rounded-md text-sm mb-4 text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="block mb-1 text-slate-300">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full p-3 rounded-md bg-slate-700 border border-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="email@domain.hu"
              autoComplete="username"
              required
            />
          </div>

          <div>
            <label className="block mb-1 text-slate-300">Jelszó</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full p-3 rounded-md bg-slate-700 border border-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>

          <div className="flex items-center justify-between mb-2">
            <label className="flex items-center gap-2 text-sm text-slate-300 select-none">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="h-4 w-4 shrink-0 accent-blue-600 cursor-pointer rounded-sm border border-slate-500 bg-slate-700 hover:scale-110 transition-transform duration-150"
                style={{
                  display: "inline-block",
                  flex: "0 0 auto",
                  width: "1rem",
                  height: "1rem",
                  margin: "0 6px 0 2px",
                  verticalAlign: "middle",
                }}
              />
              <span className="leading-tight">Emlékezz rám</span>
            </label>

            <a
              href="/forgot"
              className="text-sm text-blue-400 hover:text-blue-300 underline whitespace-nowrap"
            >
              Elfelejtett jelszó?
            </a>
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 rounded-md transition"
          >
            Belépés
          </button>
        </form>
      </div>
    </div>
  );
}
