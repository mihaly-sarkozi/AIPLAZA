import { Link } from "react-router-dom";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4 flex justify-between items-center">
        <span className="font-semibold text-lg">AIPLAZA</span>
        <Link
          to="/login"
          className="text-sm text-[var(--color-muted-foreground)] hover:underline"
        >
          Bejelentkezés
        </Link>
      </header>

      <main className="flex-1 flex flex-col items-center justify-center px-4 py-12 max-w-3xl mx-auto text-center">
        <h1 className="text-3xl md:text-4xl font-bold mb-6">
          Építs saját tudástárat
        </h1>
        <p className="text-lg text-[var(--color-muted-foreground)] mb-8 leading-relaxed">
          Az AI ilyen tudástárakból dolgozik. Legyen saját tudásanyagod, és add
          pénzért az AI-nak vagy más cégeknek. <strong>Ne elvegye az AI a munkádat</strong>—
          hanem neked dolgozzon.
        </p>

        <div className="text-left bg-[var(--color-muted)]/30 rounded-lg p-6 mb-8 w-full">
          <h2 className="font-semibold mb-2">Mi kell ehhez?</h2>
          <p className="text-[var(--color-muted-foreground)]">
            Saját tudáshalmaz: ellenőrzött, jól felépített, strukturált. Védett és
            szabályzott. Ezzel a programmal bérbe is adhatod.
          </p>
        </div>

        <p className="text-[var(--color-muted-foreground)] mb-6">
          Próbáld ki most: <strong>1 hét próbaidő</strong>. Tanítsd meg a rendszert,
          és próbáld ki, hogyan segíti a munkádat. Ha céged van, megtaníthatod a
          cég működését—nem mindig téged fognak kérdezni. Ha üzemeltetsz, tanítsd
          meg, mit mondjanak; tedd ki a weboldaladra. Legyen több tudástárad
          különböző célokra.
        </p>

        <Link
          to="/demo"
          className="inline-flex items-center justify-center px-8 py-4 rounded-lg bg-[var(--color-primary)] text-white font-medium hover:opacity-90 transition"
        >
          Demo – Próbáld ki
        </Link>

        <p className="mt-6 text-sm text-[var(--color-muted-foreground)]">
          Később saját domain is beállítható a tudástárhoz.
        </p>
      </main>

      <footer className="border-t border-[var(--color-border)] px-4 py-4 text-center text-sm text-[var(--color-muted-foreground)]">
        © AIPLAZA
      </footer>
    </div>
  );
}
