import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { demoSignup, type DemoSignupResponse } from "../api/demoApi";
import { useTranslation } from "../../../i18n";

export const DEMO_SESSION_STORAGE_KEY = "brainbankcenter_demo_session_id";

function generateSessionId(): string {
  const cryptoApi = typeof window !== "undefined" ? window.crypto : undefined;
  if (cryptoApi && typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }

  const randomPart = Math.random().toString(36).slice(2);
  return `demo-${Date.now()}-${randomPart}`;
}

function createFreshDemoSessionId(): string {
  const generated = generateSessionId();
  sessionStorage.setItem(DEMO_SESSION_STORAGE_KEY, generated);
  return generated;
}

export default function DemoPage() {
  const { locale } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [existingDemo, setExistingDemo] = useState<{ email: string } | null>(null);

  const demoSessionId = useMemo(() => createFreshDemoSessionId(), []);
  const canSubmit = Boolean(email.trim() && name.trim());

  const submitDemo = async (resendExistingAccess: boolean): Promise<DemoSignupResponse> => {
    const res = await demoSignup({
      email: email.trim(),
      name: name.trim(),
      locale,
      resend_existing_access: resendExistingAccess,
      kb_name: name.trim(),
      plan_code: "free",
      billing_period: "monthly",
      demo_session_id: demoSessionId,
    });
    const params = new URLSearchParams();
    params.set("email", email.trim());
    if (resendExistingAccess) params.set("resent", "1");
    navigate(`/demo-email-sent?${params.toString()}`, { replace: true });
    return res;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || !canSubmit) return;
    setSubmitError("");
    setExistingDemo(null);
    setSubmitting(true);
    try {
      await submitDemo(false);
    } catch (err: unknown) {
      const response =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { status?: number; data?: { detail?: string | { reason?: string; message?: string } } } })
              .response
          : null;
      const responseData = response?.data ?? null;
      const detail = responseData?.detail;
      const reason = typeof detail === "object" && detail ? detail.reason : undefined;
      const message = typeof detail === "object" && detail ? detail.message : detail;
      const normalizedMessage = (typeof message === "string" ? message : "").toLowerCase();
      const isExistingDemoLike =
        reason === "demo_exists" ||
        response?.status === 409 ||
        normalizedMessage.includes("already") ||
        normalizedMessage.includes("már") ||
        normalizedMessage.includes("használatban");
      if (isExistingDemoLike) {
        try {
          await submitDemo(true);
          setExistingDemo(null);
          setSubmitError("");
        } catch (resendErr: unknown) {
          const resendData =
            resendErr && typeof resendErr === "object" && "response" in resendErr
              ? (resendErr as { response?: { data?: { detail?: string | { message?: string } } } }).response?.data
              : null;
          const resendDetail = resendData?.detail;
          const resendMessage =
            typeof resendDetail === "object" && resendDetail ? resendDetail.message : resendDetail;
          setSubmitError(typeof resendMessage === "string" ? resendMessage : "Hiba történt. Próbáld újra.");
        }
      } else {
        setSubmitError(typeof message === "string" ? message : "Hiba történt. Próbáld újra.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleResendAccess = async () => {
    if (submitting || !canSubmit) return;
    setSubmitError("");
    setSubmitting(true);
    try {
      await submitDemo(true);
      setExistingDemo(null);
    } catch (err: unknown) {
      const responseData =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string | { message?: string } } } }).response?.data
          : null;
      const detail = responseData?.detail;
      const message = typeof detail === "object" && detail ? detail.message : detail;
      setSubmitError(typeof message === "string" ? message : "Hiba történt. Próbáld újra.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4 flex justify-between items-center">
        <Link to="/" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza
        </Link>
        <span className="font-semibold">1 perc a telepítés</span>
      </header>

      <main className="flex-1 px-4 py-8 max-w-lg mx-auto w-full">
        <h1 className="text-3xl font-bold mb-3">Próbáld ki a saját anyagaiddal</h1>
        <p className="text-base text-[var(--color-muted-foreground)] mb-2">
          Tölts fel néhány dokumentumot, és tegyél fel valós kérdéseket.
        </p>
        <p className="text-base text-[var(--color-muted-foreground)] mb-8">
          Megmutatjuk, hogyan működik a tudástár a saját tartalmaiddal.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Hogy szólíthatunk?</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-3"
              required
              placeholder="Kovács Anna"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Email címed</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-3"
              required
              placeholder="email@pelda.hu"
            />
          </div>

          {submitError && <p className="text-sm text-red-600">{submitError}</p>}
          <div className="pt-2">
            <button
              type="submit"
              disabled={submitting || !canSubmit}
              className="w-full px-6 py-3 rounded bg-[var(--color-primary)] text-white font-medium disabled:opacity-50"
            >
              {submitting ? "Telepítés…" : "Kipróbálom ingyen"}
            </button>
          </div>

          <p className="text-sm text-[var(--color-muted-foreground)]">
            Nincs kötelezettség, nincs szükség bankkártyára.
          </p>
          <p className="text-sm text-[var(--color-muted-foreground)]">
            Az adataidat bizalmasan kezeljük.{" "}
            <a
              href={`/api/installer/privacy-policy.pdf?lang=${encodeURIComponent(locale)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              adatkezelési tájékoztató
            </a>
          </p>
        </form>
      </main>

      {existingDemo && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          role="dialog"
          aria-modal="true"
          aria-labelledby="demo-exists-title"
          onClick={() => {
            if (!submitting) setExistingDemo(null);
          }}
        >
          <div
            className="relative w-full max-w-md rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] p-6 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="demo-exists-title" className="text-lg font-semibold text-[var(--color-foreground)] mb-3">
              Figyelem
            </h2>
            <p className="text-sm text-[var(--color-foreground)] mb-2">
              Ezzel az email címmel már hoztál létre demo oldalt.
            </p>
            <p className="text-sm text-[var(--color-muted-foreground)] mb-6">
              A jelszóbeállító linket elküldtük emailben, de ha szeretnél újat, elküldjük ismét emailben.
            </p>
            <p className="text-xs text-[var(--color-muted-foreground)] mb-4">
              Ha a folyamat automatikusan továbbment, ezt az ablakot nem fogod látni.
            </p>
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setExistingDemo(null)}
                disabled={submitting}
                className="inline-flex items-center justify-center rounded border border-[var(--color-border)] px-4 py-2 text-[var(--color-foreground)] disabled:opacity-50 order-2 sm:order-1"
              >
                Vissza
              </button>
              <button
                type="button"
                onClick={handleResendAccess}
                disabled={submitting}
                className="inline-flex items-center justify-center rounded bg-[var(--color-primary)] px-4 py-2 font-medium text-white disabled:opacity-50 order-1 sm:order-2"
              >
                {submitting ? "Küldés…" : "Új elérést szeretnék"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
