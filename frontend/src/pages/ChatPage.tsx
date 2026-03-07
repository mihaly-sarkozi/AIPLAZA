import { useState, useEffect, useRef } from "react";
import api from "../api/axiosClient";
import { useAuthStore } from "../store/authStore";
import { sanitizeMessage } from "../utils/sanitize";

export default function ChatPage() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([]);
  const [loading, setLoading] = useState(false);
  useAuthStore(); // keep store subscription if needed for auth checks
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null); // 🔹 input mező ref

  // 🔹 Automatikus scroll az utolsó üzenetre
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!question.trim() || loading) return;
    const currentQuestion = question.trim();

    // 🔹 Kérdés megjelenítése (szanitálva: beillesztett HTML/script nem kerül tárolásra)
    setMessages((prev) => [...prev, { role: "user", text: sanitizeMessage(currentQuestion) }]);
    setQuestion("");
    setLoading(true);

    try {
      const res = await api.post("/chat", { question: currentQuestion });
      const answer = res.data.answer;

      // 🔹 AI válasz megjelenítése (DOMPurify: nincs HTML/script végrehajtás)
      setMessages((prev) => [...prev, { role: "assistant", text: sanitizeMessage(answer) }]);
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
    <div className="flex-1 flex flex-col min-h-0 bg-[var(--color-background)] text-[var(--color-foreground)]">
      <div className="flex-1 overflow-y-auto p-6 space-y-4 pt-4 pb-4">
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
                  ? "bg-black text-white rounded-br-none"
                  : "bg-gray-100 text-black border border-gray-200 rounded-bl-none"
              } shadow-sm whitespace-pre-wrap`}
            >
              {sanitizeMessage(msg.text)}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-600 px-4 py-2 rounded-2xl rounded-bl-none animate-pulse border border-gray-200">
              ...
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      <div className="shrink-0 w-full bg-[var(--color-background)] border-t border-[var(--color-border)] p-4 flex items-center gap-2">
        <textarea
          ref={inputRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          className="flex-1 bg-[var(--color-background)] text-[var(--color-foreground)] border border-[var(--color-border)] p-3 rounded-lg resize-none h-16 focus:outline-none focus:ring-2 focus:ring-[var(--color-border)]"
          placeholder="Írd be a kérdésed és nyomj Entert..."
          disabled={loading}
        />
        <button
          onClick={send}
          disabled={loading}
          className={`px-6 py-3 rounded-lg font-semibold transition-all ${
            loading
              ? "bg-[var(--color-border)] text-[var(--color-muted)] cursor-not-allowed"
              : "bg-[var(--color-primary)] hover:opacity-90 text-[var(--color-on-primary)]"
          }`}
        >
          {loading ? "..." : "Küldés"}
        </button>
      </div>
    </div>
  );
}
