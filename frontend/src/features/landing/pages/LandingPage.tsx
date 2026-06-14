import { useEffect } from "react";
import { Link } from "react-router-dom";

import { DEMO_SESSION_STORAGE_KEY } from "../../demo/pages/DemoPage";

function StarRow() {
  return (
    <span className="text-amber-500 dark:text-amber-400 tracking-tight" aria-hidden>
      ★★★★★
    </span>
  );
}

export default function LandingPage() {
  useEffect(() => {
    sessionStorage.removeItem(DEMO_SESSION_STORAGE_KEY);
  }, []);

  return (
    <div className="min-h-screen bg-[var(--color-background)] text-[var(--color-foreground)] flex flex-col">
      <header className="border-b border-[var(--color-border)] px-4 py-4 flex justify-between items-center">
        <span className="font-semibold text-lg">AIPLAZA</span>
        <Link
          to="/platform-admin/login"
          className="text-sm text-[var(--color-muted-foreground)] hover:underline"
        >
          Bejelentkezés
        </Link>
      </header>

      <main className="flex-1 flex flex-col items-center px-4 py-12 max-w-3xl mx-auto text-center">
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
          className="inline-flex items-center justify-center px-8 py-4 rounded-lg bg-[var(--color-primary)] text-[var(--color-on-primary)] font-medium hover:opacity-90 transition"
        >
          Demo – Próbáld ki
        </Link>

        <p className="mt-6 text-sm text-[var(--color-muted)]">
          Később saját domain is beállítható a tudástárhoz.
        </p>

        <section className="mt-16 w-full max-w-6xl mx-auto text-left">
          <h2 className="text-2xl font-bold text-center mb-2">Csomagok</h2>
          <p className="text-center text-[var(--color-muted)] text-sm mb-8 max-w-2xl mx-auto">
            Hasonlítsd össze a próbaidőt és az előfizetéseket egy táblázatban.
          </p>

          <div className="overflow-x-auto rounded-xl border border-[var(--color-border)] shadow-sm">
            <table className="w-full min-w-[720px] border-collapse text-sm">
              <thead>
                <tr className="bg-[var(--color-table-head)]">
                  <th
                    scope="col"
                    className="sticky left-0 z-20 bg-[var(--color-table-head)] border-b border-r border-[var(--color-border)] px-3 py-3 text-left font-semibold align-bottom"
                  >
                    Funkció
                  </th>
                  <th
                    scope="col"
                    className="border-b border-[var(--color-border)] px-3 py-3 text-center font-semibold align-bottom w-[18%]"
                  >
                    <span className="block text-base mb-1" aria-hidden>
                      🟢
                    </span>
                    <span className="block">Ingyenes próba</span>
                  </th>
                  <th
                    scope="col"
                    className="border-b border-[var(--color-border)] px-2 py-3 text-center font-semibold align-bottom w-[22%] relative bg-amber-50/80 dark:bg-amber-950/35 ring-2 ring-amber-400/70 ring-inset"
                  >
                    <div className="flex flex-col items-center gap-1 mb-1">
                      <StarRow />
                      <span className="text-[0.65rem] font-semibold uppercase tracking-wide text-amber-800 dark:text-amber-300 leading-tight">
                        Legtöbben ezt választják
                      </span>
                    </div>
                    <span className="block text-base mb-1" aria-hidden>
                      🟡
                    </span>
                    <span className="block">Starter</span>
                    <span className="block text-[var(--color-muted)] font-normal mt-0.5">
                      29 € / hó
                    </span>
                  </th>
                  <th
                    scope="col"
                    className="border-b border-[var(--color-border)] px-3 py-3 text-center font-semibold align-bottom w-[18%]"
                  >
                    <span className="block text-base mb-1" aria-hidden>
                      🔵
                    </span>
                    <span className="block">Pro</span>
                    <span className="block text-[var(--color-muted)] font-normal mt-0.5">
                      59 € / hó
                    </span>
                  </th>
                  <th
                    scope="col"
                    className="border-b border-[var(--color-border)] px-3 py-3 text-center font-semibold align-bottom w-[18%]"
                  >
                    <span className="block text-base mb-1" aria-hidden>
                      🟣
                    </span>
                    <span className="block">Business</span>
                    <span className="block text-[var(--color-muted)] font-normal mt-0.5">
                      129 € / hó
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody className="[&_td]:border-b [&_td]:border-[var(--color-border)]">
                <tr>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Időtartam
                  </th>
                  <td className="px-3 py-2.5 text-center">1 hét</td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20">—</td>
                  <td className="px-3 py-2.5 text-center">—</td>
                  <td className="px-3 py-2.5 text-center">—</td>
                </tr>
                <tr>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Tudástár
                  </th>
                  <td className="px-3 py-2.5 text-center">1</td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20">1</td>
                  <td className="px-3 py-2.5 text-center">3</td>
                  <td className="px-3 py-2.5 text-center">10</td>
                </tr>
                <tr>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Felhasználó
                  </th>
                  <td className="px-3 py-2.5 text-center">1</td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20">—</td>
                  <td className="px-3 py-2.5 text-center">—</td>
                  <td className="px-3 py-2.5 text-center">—</td>
                </tr>
                <tr>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Tárhely
                  </th>
                  <td className="px-3 py-2.5 text-center">—</td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20">1 GB</td>
                  <td className="px-3 py-2.5 text-center">5 GB</td>
                  <td className="px-3 py-2.5 text-center">10 GB</td>
                </tr>
                <tr>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Betanítás
                  </th>
                  <td className="px-3 py-2.5 text-center">500 000 karakter</td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20">—</td>
                  <td className="px-3 py-2.5 text-center">—</td>
                  <td className="px-3 py-2.5 text-center">—</td>
                </tr>
                <tr>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Kérdések
                  </th>
                  <td className="px-3 py-2.5 text-center">100</td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20">
                    500 / hó
                  </td>
                  <td className="px-3 py-2.5 text-center">2000 / hó</td>
                  <td className="px-3 py-2.5 text-center">5000 / hó</td>
                </tr>
                <tr>
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Ár
                  </th>
                  <td className="px-3 py-2.5 text-center font-medium">Ingyenes</td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20 font-medium">
                    29 € / hó
                  </td>
                  <td className="px-3 py-2.5 text-center font-medium">59 € / hó</td>
                  <td className="px-3 py-2.5 text-center font-medium">129 € / hó</td>
                </tr>
                <tr className="align-top">
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Célcsoport / ideális
                  </th>
                  <td className="px-3 py-2.5 text-center text-[var(--color-muted)]">
                    Kipróbálni saját anyaggal, kockázat nélkül.
                  </td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20 text-[var(--color-muted)]">
                    Kisebb csapatok, indulás
                  </td>
                  <td className="px-3 py-2.5 text-center text-[var(--color-muted)]">
                    Növekvő KKV-k
                  </td>
                  <td className="px-3 py-2.5 text-center text-[var(--color-muted)]">
                    Több csapat, nagyobb használat
                  </td>
                </tr>
                <tr className="align-top">
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-[var(--color-background)] border-r border-[var(--color-border)] px-3 py-2.5 text-left font-medium text-[var(--color-label)]"
                  >
                    Kedvezmények
                  </th>
                  <td className="px-3 py-2.5 text-center text-[var(--color-muted)]">—</td>
                  <td className="px-3 py-2.5 text-center bg-amber-50/50 dark:bg-amber-950/20 text-[var(--color-muted)] text-xs leading-relaxed">
                    Negyedéves: 26 € / hó (−7%)
                    <br />
                    Éves: 24 € / hó (−15%)
                  </td>
                  <td className="px-3 py-2.5 text-center text-[var(--color-muted)] text-xs leading-relaxed">
                    Negyedéves: 54 € / hó (−7%)
                    <br />
                    Éves: 50 € / hó (−15%)
                  </td>
                  <td className="px-3 py-2.5 text-center text-[var(--color-muted)] text-xs leading-relaxed">
                    Negyedéves: 119 € / hó (−7%)
                    <br />
                    Éves: 109 € / hó (−15%)
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-12 grid gap-10 md:grid-cols-2">
            <div>
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <span aria-hidden>⚙️</span> Betanítás (egyszeri díj)
              </h3>
              <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-[var(--color-table-head)]">
                      <th className="text-left px-3 py-2 font-semibold border-b border-[var(--color-border)]">
                        Típus
                      </th>
                      <th className="text-right px-3 py-2 font-semibold border-b border-[var(--color-border)]">
                        Ár
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-[var(--color-border)]">
                      <td className="px-3 py-2">Első betanítás (500k karakterig)</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">49 €</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2">További 500k karakter</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">+29 €</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <span aria-hidden>➕</span> Bővítések (addonok)
              </h3>
              <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="bg-[var(--color-table-head)]">
                      <th className="text-left px-3 py-2 font-semibold border-b border-[var(--color-border)]">
                        Bővítés
                      </th>
                      <th className="text-right px-3 py-2 font-semibold border-b border-[var(--color-border)]">
                        Ár
                      </th>
                    </tr>
                  </thead>
                  <tbody className="[&_tr]:border-b [&_tr]:border-[var(--color-border)] [&_tr:last-child]:border-b-0">
                    <tr>
                      <td className="px-3 py-2">Extra tudástár</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">+5 € / hó</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2">Extra tárhely</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">+5 € / GB / hó</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2">500 extra kérdés</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">+5 €</td>
                    </tr>
                    <tr>
                      <td className="px-3 py-2">100 extra kérdés</td>
                      <td className="px-3 py-2 text-right whitespace-nowrap">+1,2 €</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="mt-12">
            <h3 className="text-lg font-semibold mb-4 text-center flex items-center justify-center gap-2">
              <span aria-hidden>🔁</span> Működés röviden
            </h3>
            <ol className="max-w-xl mx-auto space-y-2 text-[var(--color-muted)] list-decimal list-inside text-sm">
              <li>Ingyenes próba indul</li>
              <li>Anyagok feltöltése</li>
              <li>Előfizetés választása</li>
              <li>Használat növekedésével bővítés</li>
            </ol>
          </div>

          <div className="mt-10 rounded-xl border border-[var(--color-border)] bg-[var(--color-muted)]/10 p-5">
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
              <span aria-hidden>📌</span> Fontos szabályok
            </h3>
            <ul className="space-y-2 text-sm text-[var(--color-muted)] list-disc list-inside">
              <li>Tárhely és tudástár bővítés: időarányos számlázás</li>
              <li>Kérdéscsomagok: azonnal aktiválódnak</li>
              <li>Kérdések: gördülnek tovább</li>
              <li>Előfizetés: automatikusan megújul</li>
            </ul>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--color-border)] px-4 py-4 text-center text-sm text-[var(--color-muted-foreground)]">
        © AIPLAZA
      </footer>
    </div>
  );
}
