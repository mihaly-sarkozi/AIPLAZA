import { useState } from "react";
import { useParams } from "react-router-dom";
import { useKbTrainTextMutation, useKbTrainFileMutation } from "../hooks/useKb";

export default function KBTrain() {
  const { uuid } = useParams();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const trainTextMutation = useKbTrainTextMutation();
  const trainFileMutation = useKbTrainFileMutation();

  const trainText = () => {
    if (!uuid) return;
    trainTextMutation.mutate(
      { uuid, title, content },
      { onSuccess: () => alert("Szöveg betanítva!") }
    );
  };

  const trainFile = () => {
    if (!uuid) return;
    if (!file) return alert("Nincs fájl kiválasztva!");
    const formData = new FormData();
    formData.append("file", file);
    trainFileMutation.mutate(
      { uuid, formData },
      { onSuccess: () => alert("Fájl betanítva!") }
    );
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) setFile(f);
  };

  return (
    <div className="p-10 text-black max-w-3xl mx-auto">

      <h1 className="text-3xl font-bold mb-6">Tudástár tanítása</h1>

      <div className="bg-white border border-gray-200 p-6 rounded-lg mb-10">
        <h2 className="text-xl font-bold mb-4">Szöveges tanítás</h2>

        <label className="block mb-1 text-gray-700">Cím</label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mb-4 w-full p-3 rounded bg-white border border-gray-300"
        />

        <label className="block mb-1 text-gray-700">Tartalom</label>
        <textarea
          rows={6}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="mb-4 w-full p-3 rounded bg-white border border-gray-300"
        ></textarea>

        <button
          className="bg-black text-white px-4 py-2 rounded hover:bg-gray-800 disabled:opacity-50"
          onClick={trainText}
          disabled={trainTextMutation.isPending}
        >
          {trainTextMutation.isPending ? "Feldolgozás…" : "Tanítás szöveggel"}
        </button>
      </div>

      <div className="bg-white border border-gray-200 p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Fájl feltöltés</h2>

        <div
          className={`border-2 border-dashed rounded-lg p-10 text-center transition ${
            dragOver ? "border-gray-500 bg-gray-50" : "border-gray-300"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          {file ? (
            <div>Kiválasztott fájl: <strong>{file.name}</strong></div>
          ) : (
            <div>Húzd ide a fájlt vagy kattints lentebb!</div>
          )}
        </div>

        <div className="mt-4">
          <input
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="block"
          />
        </div>

        <button
          className="bg-gray-800 text-white px-4 py-2 rounded mt-5 hover:bg-gray-700 disabled:opacity-50"
          onClick={trainFile}
          disabled={trainFileMutation.isPending}
        >
          {trainFileMutation.isPending ? "Feldolgozás…" : "Tanítás fájllal"}
        </button>
      </div>
    </div>
  );
}
