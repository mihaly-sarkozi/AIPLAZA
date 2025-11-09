import { useState, useEffect, useRef } from "react";
import api from "../api/axiosClient";
import { useAuthStore } from "../store/authStore";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const { logout, user } = useAuthStore();
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null); // 🔹 input mező ref

  // 🔹 Automatikus scroll az utolsó üzenetre
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!question.trim() || loading) return;
    const currentQuestion = question.trim();

    // 🔹 Kérdés megjelenítése
    setMessages((prev) => [...prev, { role: "user", text: currentQuestion }]);
    setQuestion("");
    setLoading(true);

    try {
      const res = await api.post("/chat", { question: currentQuestion });
      const answer = res.data.answer;

      // 🔹 AI válasz megjelenítése
      setMessages((prev) => [...prev, { role: "assistant", text: answer }]);
    } catch (err) {
      console.error("Chat error:", err);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "⚠️ Hiba történt a válasz lekérése közben." },
      ]);
    } finally {
      setLoading(false);
      // 🔹 Fókusz visszaállítása a beviteli mezőre
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-900 text-white">
      {/* 🔹 Rögzített fejléc */}
      <nav className="fixed top-0 left-0 w-full p-4 bg-blue-600 flex justify-between items-center shadow-md z-10">
        <span className="font-semibold">💬 BrainBankCenter.com – {user?.email}</span>
        <button
          onClick={() => logout()}
          className="text-sm underline hover:text-slate-200"
        >
          Kilépés
        </button>
      </nav>

      {/* 🔹 Chat üzenetek */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 pt-20 pb-28">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${
              msg.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`px-4 py-2 rounded-2xl max-w-lg ${
                msg.role === "user"
                  ? "bg-blue-600 text-white rounded-br-none"
                  : "bg-slate-700 text-slate-100 rounded-bl-none"
              } shadow-md whitespace-pre-wrap`}
            >
              {msg.text}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-700 text-slate-300 px-4 py-2 rounded-2xl rounded-bl-none animate-pulse">
              ...
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* 🔹 Rögzített beviteli mező */}
      <div className="fixed bottom-0 left-0 w-full bg-slate-800 border-t border-slate-700 p-4 flex items-center gap-2">
        <textarea
          ref={inputRef} // 👈 fontos: ref hozzárendelve
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          className="flex-1 bg-slate-700 text-white p-3 rounded-lg resize-none h-16 focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Írd be a kérdésed és nyomj Entert..."
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading}
          className={`px-6 py-3 rounded-lg font-semibold transition-all ${
            loading
              ? "bg-gray-500 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-500 text-white"
          }`}
        >
          {loading ? "..." : "Küldés"}
        </button>
      </div>
    </div>
  );
}
