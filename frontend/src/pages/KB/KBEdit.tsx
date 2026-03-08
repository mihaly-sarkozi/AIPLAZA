import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useKbList, useUpdateKbMutation } from "../../hooks/useApi";
import { getApiErrorMessage } from "../../utils/getApiErrorMessage";

export default function KBEdit() {
  const { uuid } = useParams();
  const navigate = useNavigate();
  const { data: kbList = [], isLoading: kbListLoading } = useKbList();
  const updateKbMutation = useUpdateKbMutation();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  const kb = uuid ? kbList.find((x) => x.uuid === uuid) : null;

  useEffect(() => {
    if (!uuid) return;
    if (!kbListLoading && !kb) {
      navigate("/kb");
      return;
    }
    if (kb) {
      setName(kb.name);
      setDescription(kb.description ?? "");
    }
  }, [kb, kbListLoading, uuid, navigate]);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!uuid) return;
    setError("");
    updateKbMutation.mutate(
      { uuid, name, description },
      {
        onSuccess: () => navigate("/kb"),
        onError: (err: unknown) => {
          setError(getApiErrorMessage(err) ?? "Hiba történt.");
        },
      }
    );
  };

  return (
    <div className="p-10 text-black max-w-xl mx-auto">
      <h1 className="text-3xl mb-6 font-bold">Tudástár szerkesztése</h1>

      {error && (
        <div className="bg-gray-100 border border-gray-300 text-gray-800 p-3 mb-4 rounded">
          {error}
        </div>
      )}

      <form className="flex flex-col gap-5" onSubmit={handleSave}>
        <div>
          <label className="block mb-1 text-gray-700">Név</label>
          <input
            type="text"
            maxLength={20}
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full p-3 rounded bg-white border border-gray-300"
          />
        </div>

        <div>
          <label className="block mb-1 text-gray-700">Leírás</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full p-3 rounded bg-white border border-gray-300 h-32"
          />
        </div>

        <button
          type="submit"
          className="bg-black hover:bg-gray-800 text-white py-3 rounded disabled:opacity-50"
          disabled={updateKbMutation.isPending}
        >
          {updateKbMutation.isPending ? "Mentés…" : "Mentés"}
        </button>
      </form>
    </div>
  );
}
