import { useEffect, useState } from "react";
import api from "../../api/axiosClient";
import { useAuthStore } from "../../store/authStore";

interface User {
  id: number;
  email: string;
  role: "user" | "admin";
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export default function RolesPage() {
  const { user: currentUser } = useAuthStore();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    role: "user" as "user" | "admin",
    is_superuser: false,
    is_active: true,
  });

  useEffect(() => {
    if (currentUser?.is_superuser) {
      loadUsers();
    }
  }, [currentUser]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const res = await api.get("/users");
      setUsers(res.data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Hiba történt a felhasználók betöltésekor");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      await api.post("/users", {
        email: formData.email,
        password: formData.password,
        role: formData.role,
        is_superuser: formData.is_superuser,
      });
      setShowCreateModal(false);
      resetForm();
      loadUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Hiba történt a létrehozáskor");
    }
  };

  const handleUpdate = async () => {
    if (!editingUser) return;

    try {
      await api.put(`/users/${editingUser.id}`, {
        email: formData.email,
        role: formData.role,
        is_active: formData.is_active,
      });
      setEditingUser(null);
      resetForm();
      loadUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Hiba történt a frissítéskor");
    }
  };

  const handleDelete = async (userId: number) => {
    if (!confirm("Biztosan törölni szeretnéd ezt a felhasználót?")) return;

    try {
      await api.delete(`/users/${userId}`);
      loadUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Hiba történt a törléskor");
    }
  };

  const resetForm = () => {
    setFormData({
      email: "",
      password: "",
      role: "user",
      is_superuser: false,
      is_active: true,
    });
  };

  const openEditModal = (user: User) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      password: "",
      role: user.role,
      is_superuser: user.is_superuser,
      is_active: user.is_active,
    });
  };

  if (!currentUser?.is_superuser) {
    return (
      <div className="p-6">
        <div className="bg-red-500 text-white p-4 rounded">
          Nincs jogosultságod az oldal megtekintéséhez. Csak superuser férhet hozzá.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Jogosultságkezelés</h1>
        <button
          onClick={() => {
            resetForm();
            setShowCreateModal(true);
          }}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
        >
          + Új felhasználó
        </button>
      </div>

      {error && (
        <div className="bg-red-500 text-white p-4 rounded mb-4">{error}</div>
      )}

      {loading ? (
        <div>Betöltés...</div>
      ) : (
        <div className="bg-slate-800 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-700">
              <tr>
                <th className="p-3 text-left">Email</th>
                <th className="p-3 text-left">Szerepkör</th>
                <th className="p-3 text-left">Státusz</th>
                <th className="p-3 text-left">Superuser</th>
                <th className="p-3 text-left">Létrehozva</th>
                <th className="p-3 text-left">Műveletek</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id} className="border-t border-slate-700">
                  <td className="p-3">{user.email}</td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-1 rounded text-xs ${
                        user.role === "admin"
                          ? "bg-purple-600 text-white"
                          : "bg-slate-600 text-white"
                      }`}
                    >
                      {user.role}
                    </span>
                  </td>
                  <td className="p-3">
                    <span
                      className={`px-2 py-1 rounded text-xs ${
                        user.is_active
                          ? "bg-green-600 text-white"
                          : "bg-red-600 text-white"
                      }`}
                    >
                      {user.is_active ? "Aktív" : "Inaktív"}
                    </span>
                  </td>
                  <td className="p-3">
                    {user.is_superuser ? (
                      <span className="text-yellow-400 font-bold">⭐ Superuser</span>
                    ) : (
                      <span className="text-slate-400">-</span>
                    )}
                  </td>
                  <td className="p-3 text-sm text-slate-400">
                    {new Date(user.created_at).toLocaleDateString("hu-HU")}
                  </td>
                  <td className="p-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => openEditModal(user)}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm"
                      >
                        Szerkesztés
                      </button>
                      {!user.is_superuser && (
                        <button
                          onClick={() => handleDelete(user.id)}
                          className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm"
                        >
                          Törlés
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-slate-800 p-6 rounded-lg w-96">
            <h2 className="text-2xl font-bold mb-4">Új felhasználó</h2>
            <div className="space-y-4">
              <div>
                <label className="block mb-1">Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  className="w-full bg-slate-700 text-white p-2 rounded"
                />
              </div>
              <div>
                <label className="block mb-1">Jelszó</label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) =>
                    setFormData({ ...formData, password: e.target.value })
                  }
                  className="w-full bg-slate-700 text-white p-2 rounded"
                />
              </div>
              <div>
                <label className="block mb-1">Szerepkör</label>
                <select
                  value={formData.role}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      role: e.target.value as "user" | "admin",
                      is_superuser: e.target.value === "admin" ? formData.is_superuser : false,
                    })
                  }
                  className="w-full bg-slate-700 text-white p-2 rounded"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              {formData.role === "admin" && (
                <div>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.is_superuser}
                      onChange={(e) =>
                        setFormData({ ...formData, is_superuser: e.target.checked })
                      }
                    />
                    <span>Superuser</span>
                  </label>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={handleCreate}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded"
              >
                Létrehozás
              </button>
              <button
                onClick={() => {
                  setShowCreateModal(false);
                  resetForm();
                }}
                className="flex-1 bg-slate-600 hover:bg-slate-700 text-white px-4 py-2 rounded"
              >
                Mégse
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {editingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-slate-800 p-6 rounded-lg w-96">
            <h2 className="text-2xl font-bold mb-4">Felhasználó szerkesztése</h2>
            <div className="space-y-4">
              <div>
                <label className="block mb-1">Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  className="w-full bg-slate-700 text-white p-2 rounded"
                />
              </div>
              <div>
                <label className="block mb-1">Szerepkör</label>
                <select
                  value={formData.role}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      role: e.target.value as "user" | "admin",
                    })
                  }
                  disabled={editingUser.is_superuser}
                  className="w-full bg-slate-700 text-white p-2 rounded disabled:opacity-50"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) =>
                      setFormData({ ...formData, is_active: e.target.checked })
                    }
                    disabled={editingUser.is_superuser}
                    className="disabled:opacity-50"
                  />
                  <span>Aktív</span>
                </label>
              </div>
              {editingUser.is_superuser && (
                <div className="text-yellow-400 text-sm">
                  ⚠️ Superuser nem módosítható
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={handleUpdate}
                disabled={editingUser.is_superuser}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded disabled:opacity-50"
              >
                Mentés
              </button>
              <button
                onClick={() => {
                  setEditingUser(null);
                  resetForm();
                }}
                className="flex-1 bg-slate-600 hover:bg-slate-700 text-white px-4 py-2 rounded"
              >
                Mégse
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
