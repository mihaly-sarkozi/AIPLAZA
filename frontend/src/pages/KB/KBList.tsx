import { useEffect, useState } from "react";
import api from "../../api/axiosClient";
import { Link, useNavigate } from "react-router-dom";

export default function KBList() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    load();
  }, []);

  const load = async () => {
    try {
      const res = await api.get("/kb");
      setItems(res.data);
    } finally {
      setLoading(false);
    }
  };

  const deleteKB = async (kb: any) => {
    const confirm = window.prompt(
      `Törlés megerősítése.\nÍrd be a tudástár nevét: "${kb.name}"`
    );

    if (confirm !== kb.name) {
      alert("A beírt név nem egyezik.");
      return;
    }

    await api.delete(`/kb/${kb.uuid}`, {
      data: { confirm_name: confirm }
    });

    load();
  };

  if (loading) return <div className="p-10">Betöltés...</div>;

  return (
    <div className="p-10 text-white">
      <div className="flex justify-between mb-6">
        <h1 className="text-3xl font-bold">Tudástárak</h1>

        <Link
          to="/kb/create"
          className="bg-blue-600 px-4 py-2 rounded-md hover:bg-blue-500"
        >
          Új tudástár
        </Link>
      </div>

      <table className="w-full bg-slate-800 rounded-xl overflow-hidden">
        <thead className="bg-slate-700">
          <tr>
            <th className="p-3 text-left">Név</th>
            <th className="p-3 text-left">Leírás</th>
            <th className="p-3">Műveletek</th>
          </tr>
        </thead>
        <tbody>
          {items.map((kb: any) => (
            <tr key={kb.uuid} className="border-b border-slate-700">
              <td className="p-3">{kb.name}</td>
              <td className="p-3 text-slate-300">{kb.description}</td>
              <td className="p-3 flex gap-3 justify-end w-full">

                {/* Szerkesztés */}
                <button
                    className="bg-blue-600 px-3 py-1 rounded hover:bg-blue-500"
                    onClick={() => navigate(`/kb/edit/${kb.uuid}`)}
                >
                  Szerkesztés
                </button>

                {/* Törlés */}
                <button
                    className="bg-red-600 px-3 py-1 rounded hover:bg-red-500"
                    onClick={() => deleteKB(kb)}
                >
                  Törlés
                </button>

                {/* Tanítás - sor végén, piros színnel */}
                <button
                    className="bg-green-600 px-3 py-1 ml-10 rounded hover:bg-green-500"
                    onClick={() => navigate(`/kb/train/${kb.uuid}`)}
                >
                  Tanítás
                </button>

              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}