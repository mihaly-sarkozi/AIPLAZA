import { useState } from "react";
import api from "../api/axiosClient";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);

  const submit = async () => {
    await api.post("/auth/forgot", { email });
    setDone(true);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-6 bg-white rounded-2xl shadow-md w-80 text-center">
        {done ? (
          <p>Ha az email címed regisztrálva van, küldtünk egy visszaállító linket.</p>
        ) : (
          <>
            <h2 className="text-xl font-bold mb-4">Jelszó emlékeztető</h2>
            <input
              type="email"
              placeholder="Email címed"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full mb-3 p-2 border rounded"
            />
            <button onClick={submit} className="w-full bg-blue-600 text-white py-2 rounded">
              Küldés
            </button>
          </>
        )}
      </div>
    </div>
  );
}
