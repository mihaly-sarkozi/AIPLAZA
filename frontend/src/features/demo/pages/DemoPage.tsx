import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { checkSlug, demoSignup, normalizeSlug } from "../api/demoApi";

/** Demo oldal "A címed: slug.{domain}" – ugyanaz, mint a backend tenant_base_domain. Beállítás: frontend/.env.local → VITE_TENANT_DOMAIN=app.test */
const TENANT_DOMAIN_FALLBACK = import.meta.env.VITE_TENANT_DOMAIN ?? "app.test";

function getSlugCheckErrorMessage(err: unknown): string {
  if (err && typeof err === "object" && "response" in err) {
    const res = (err as { response?: { status?: number; data?: { detail?: string | { message?: string } } } }).response;
    const detail = res?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && typeof detail.message === "string") return detail.message;
    const status = res?.status;
    if (status === 400) return "A kérés érvénytelen. Tenant hiányzik – használd a céges aldomaint, vagy a backend engedélyezi a /api/public útvonalat.";
    if (status === 503) return "Az ellenőrzés ideiglenesen nem elérhető (szerver/DB). Próbáld később.";
    if (status != null) return `Ellenőrzés sikertelen (${status}). ${detail ? JSON.stringify(detail) : ""}`.trim();
  }
  const msg = err && typeof err === "object" && "message" in err && typeof (err as { message: unknown }).message === "string"
    ? (err as { message: string }).message
    : null;
  return msg || "Nem sikerült elérni a szervert. Ellenőrizd a kapcsolatot és a címet (pl. /api proxy).";
}

export default function DemoPage() {
  const [email, setEmail] = useState("");
  const [kbName, setKbName] = useState("");
  const [slugAvailable, setSlugAvailable] = useState<boolean | null>(null);
  const [slugChecking, setSlugChecking] = useState(false);
  const [slugCheckError, setSlugCheckError] = useState<string | null>(null);
  /** Backend check-slug válaszából jön; ha nincs még, fallback: VITE_TENANT_DOMAIN. */
  const [tenantBaseDomain, setTenantBaseDomain] = useState<string>(TENANT_DOMAIN_FALLBACK);

  const [name, setName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<{ slug: string; host_hint: string } | null>(null);

  const derivedSlug = normalizeSlug(kbName);
  const canSubmit = slugAvailable === true && email.trim() && kbName.trim() && name.trim() && phone.trim();

  // Tudástárnév: ha nincs benne a rendszerben (elérhető), akkor választható – automatikus ellenőrzés
  useEffect(() => {
    if (!derivedSlug || derivedSlug.length < 2) {
      setSlugAvailable(null);
      setSlugCheckError(null);
      return;
    }
    let cancelled = false;
    setSlugChecking(true);
    setSlugAvailable(null);
    setSlugCheckError(null);
    const t = setTimeout(() => {
      checkSlug(derivedSlug)
        .then((res) => {
          if (!cancelled) {
            setSlugAvailable(res.available);
            setSlugCheckError(null);
            if (res.tenant_base_domain) setTenantBaseDomain(res.tenant_base_domain);
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setSlugAvailable(null);
            const msg = getSlugCheckErrorMessage(err);
            setSlugCheckError(msg);
          }
        })
        .finally(() => { if (!cancelled) setSlugChecking(false); });
    }, 500);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [derivedSlug]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting || !canSubmit) return;
    setSubmitError("");
    setSubmitting(true);
    try {
      const res = await demoSignup({
        email: email.trim(),
        kb_name: kbName.trim(),
        name: name.trim(),
        company_name: companyName.trim() || undefined,
        address: address.trim() || undefined,
        phone: phone.trim() || undefined,
      });
      setSuccess({ slug: res.slug, host_hint: res.host_hint });
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      setSubmitError(typeof detail === "string" ? detail : "Hiba történt. Próbáld újra.");
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
        <header className="border-b border-[var(--color-border)] px-4 py-4">
          <Link to="/" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
            ← Vissza a főoldalra
          </Link>
        </header>
        <main className="flex-1 flex flex-col items-center justify-center px-4 py-12 max-w-lg mx-auto text-center">
          <h1 className="text-2xl font-bold mb-4">Megkezdjük a telepítést</h1>
          <p className="text-[var(--color-muted-foreground)] mb-6">
            2–3 percen belül kapsz egy emailt. A linken beállíthatod a jelszavad, majd
            bejelentkezhetsz.
          </p>
          <p className="text-sm text-[var(--color-muted-foreground)]">
            A rendszered címe: <strong>{success.host_hint}</strong>
          </p>
          <p className="mt-6 text-sm text-[var(--color-muted-foreground)]">
            Később saját domain is beállítható.
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4 flex justify-between items-center">
        <Link to="/" className="text-sm text-[var(--color-muted-foreground)] hover:underline">
          ← Vissza
        </Link>
        <span className="font-semibold">Demo – Telepítés</span>
      </header>

      <main className="flex-1 px-4 py-8 max-w-lg mx-auto w-full">
        <h1 className="text-2xl font-bold mb-2">Próbáld ki</h1>
        <p className="text-sm text-[var(--color-muted-foreground)] mb-6">
          1 ingyenes tudástár a próbaidőszak alatt. Többet is beállíthatsz később.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Step 1 */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Email *</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                required
                placeholder="email@pelda.hu"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Tudástár neve *</label>
              <input
                type="text"
                value={kbName}
                onChange={(e) => setKbName(e.target.value)}
                className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                required
                placeholder="pl. Cégünk szabályzatai"
              />
              <p className="text-xs text-[var(--color-muted-foreground)] mt-1">
                Csak olyan nevet választhatsz, ami még nincs a rendszerben (automatikusan ellenőrizzük).
              </p>
            </div>
            {derivedSlug && derivedSlug.length >= 2 && (
              <div className="text-sm">
                <span className="text-[var(--color-muted-foreground)]">A címed: </span>
                <strong>{derivedSlug}.{tenantBaseDomain}</strong>
                {slugChecking && <span className="ml-2 text-[var(--color-muted-foreground)]">(ellenőrzés…)</span>}
              </div>
            )}
            {slugCheckError && (
              <p className="text-sm text-amber-600">
                {slugCheckError}
              </p>
            )}
            {!slugCheckError && slugAvailable === false && (
              <p className="text-sm text-red-600">
                A név foglalt, válassz egy másikat.
              </p>
            )}
            {slugAvailable === true && (
              <p className="text-sm text-green-600">Ez a név nincs a rendszerben, választhatod.</p>
            )}
          </div>

          {slugAvailable === true && (
            <>
              <hr className="border-[var(--color-border)]" />
              <p className="font-medium">Megkezdjük a telepítést – pár adat kell:</p>
              <div>
                <label className="block text-sm font-medium mb-1">Neved *</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                  placeholder="Kovács János"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Cégnév</label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Cím</label>
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Telefonszám *</label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full rounded border border-[var(--color-border)] bg-[var(--color-background)] px-3 py-2"
                  required
                />
              </div>
              <p className="text-sm text-[var(--color-muted-foreground)]">
                Emailt kapsz egy linkkel; a linken meg kell erősítened és be kell állítanod a jelszavad.
              </p>
            </>
          )}

          {submitError && (
            <p className="text-sm text-red-600">{submitError}</p>
          )}

          {slugAvailable === true && (
            <div className="pt-2">
              <button
                type="submit"
                disabled={submitting || !canSubmit}
                className="px-6 py-2 rounded bg-[var(--color-primary)] text-white font-medium disabled:opacity-50"
              >
                {submitting ? "Küldés…" : "Regisztráció indítása"}
              </button>
            </div>
          )}
        </form>
      </main>
    </div>
  );
}
