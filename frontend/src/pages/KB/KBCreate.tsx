import { useState } from "react";
import api from "../../api/axiosClient";
import { useNavigate } from "react-router-dom";

export default function KBCreate() {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  const navigate = useNavigate();

  const handleSave = async (e: any) => {
    e.preventDefault();
    setError("");

    try {
      await api.post("/kb", { name, description });
      navigate("/kb");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Hiba történt.");
    }
  };

  return (
    <div className="p-10 text-white max-w-xl mx-auto">
      <h1 className="text-3xl mb-6 font-bold">Új tudástár</h1>

      {error && (
        <div className="bg-red-700/30 border border-red-400 p-3 mb-4 rounded">
          {error}
        </div>
      )}

      <form className="flex flex-col gap-5" onSubmit={handleSave}>
        <div>
          <label className="block mb-1">Név</label>
          <input
            type="text"
            maxLength={20}
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full p-3 rounded bg-slate-800 border border-slate-600"
          />
        </div>

        <div>
          <label className="block mb-1">Leírás</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full p-3 rounded bg-slate-800 border border-slate-600 h-32"
          />
        </div>

        <button className="bg-blue-600 hover:bg-blue-500 py-3 rounded">
          Mentés
        </button>
      </form>
    </div>
  );
}
