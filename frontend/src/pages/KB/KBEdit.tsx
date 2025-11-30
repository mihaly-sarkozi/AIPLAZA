import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../../api/axiosClient";

export default function KBEdit() {
  const { uuid } = useParams();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/kb").then((res) => {
      const kb = res.data.find((x: any) => x.uuid === uuid);
      if (!kb) return navigate("/kb");

      setName(kb.name);
      setDescription(kb.description);
    });
  }, [uuid]);

  const handleSave = async (e: any) => {
    e.preventDefault();
    setError("");

    try {
      await api.put(`/kb/${uuid}`, { name, description });
      navigate("/kb");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Hiba történt.");
    }
  };

  return (
    <div className="p-10 text-white max-w-xl mx-auto">
      <h1 className="text-3xl mb-6 font-bold">Tudástár szerkesztése</h1>

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
