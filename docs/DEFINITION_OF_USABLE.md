# Definition of “Usable”

A PII / tudástár / file ingest és review rendszert **használhatónak** tekintjük, ha az alábbi feltételek teljesülnek.

---

## 1. No duplicated implementation truth

**Criterion:** Nincs duplikált implementációs igazság – egyetlen forrás a detektálásra, helyettesítésre és policy-re.

- **PII detection:** Egy központi pipeline (pl. `pii_gdpr`) a detektálás forrása; a `pii` csomag csak **adapter** (legacy API: `filter_pii`, `apply_pii_replacements`).
- **Placeholders / policy:** Standard placeholderek és policy döntések egy helyen (pl. `pii/sanitization.py`, `pii_gdpr/policy`); nincs párhuzamos, eltérő logika ugyanarra az entitásra két külön modulban.
- **Ellenőrzés:** Keresés a codebase-ben: nincs két különböző „email detektor” vagy „IBAN regex” implementáció, amelyek nem ugyanazzal a pipeline-nal vannak összekötve.

---

## 2. Every supported entity has a real detector

**Criterion:** Minden támogatott entitástípusnak van **valódi detektora** (regex, NER, vagy dedikált recognizer), nem csak placeholder vagy üres stub.

- **Supported list:** Explicit lista (pl. `SUPPORTED_ENTITIES.md` vagy `policy.py` / `entities_for_sensitivity`) – ezen belül minden típusra létezik detektor a pipeline-ban.
- **Real detector:** A pipeline (pl. `IngestionPipeline` / `MultilingualAnalyzer` vagy adapter) valóban meghívja a megfelelő recognizert és visszaadja a detektálást; nem csak „név” vagy „email” hardcoded, hanem a teljes supported set lefedve.
- **Backlog:** Ha egy típus még nincs detektorral lefedve, nem szerepel a supported listán, vagy explicit backlog/xfail.

---

## 3. Every supported entity has real tests

**Criterion:** Minden támogatott entitásnak van **valódi tesztje** – legalább egy pozitív (és ahol értelmes, negatív vagy edge) teszt, ami a detektálást vagy a policy/replace viselkedést ellenőrzi.

- **Unit vagy integration:** Pozitív példa (pl. „ezt a szöveget kiszűri”), és ahol lehet: negatív („ezt nem”), edge (pl. VIN vs random 17 char).
- **Must-pass / release acceptance:** A supported entitásokhoz tartozó tesztek a minimum release acceptance suite részei vagy egyértelműen must_pass.
- **Lásd:** `COVERAGE_MATRIX.md`, `MINIMUM_RELEASE_ACCEPTANCE.md`.

---

## 4. Unsupported entities are explicitly marked as backlog or xfail

**Criterion:** A nem (még) támogatott entitások **explicit módon** backlogon vagy xfail tesztben szerepelnek – nem „néma hiány”, hanem dokumentált vállalás vagy „még nem”.

- **Lista:** Egy helyen (pl. `NOT_YET_SUPPORTED.md`) felsorolva: mely típusok nem garantáltak, mi a terv (backlog).
- **Tesztek:** Ha van rá teszt (pl. „IP detektálódik”), az vagy xfail („még nem garantált”), vagy a típus bekerül a supported listába és a teszt must_pass.
- **Nincs „középút”:** Egy típus vagy supported (detektor + teszt), vagy explicit not-supported/backlog/xfail.

---

## 5. Upload → detect → review → sanitize → index flow is proven end-to-end

**Criterion:** A teljes folyamat **végpontoktól-végpontig** bizonyított: feltöltés (file vagy plain text) → detektálás → review (409 + döntés) → szanitizálás → tárolás/indexelés.

- **Upload:** File (PDF/DOCX/TXT) vagy nyers szöveg a megfelelő API-n (pl. `/kb/{uuid}/train`, `/train/file`).
- **Detect:** PII detektálódik; ha a KB with_confirmation módban van és nincs confirm → 409.
- **Review:** 409 válasz tartalmazza: entity types, counts, snippets; a kliens dönt: confirm (mask/reject) vagy cancel.
- **Sanitize:** Confirm esetén standard placeholderekkel (vagy generalization) helyettesítés; raw_content és review_decision tárolva ahol kell.
- **Index:** A szanitizált tartalom a training log-ban (és ahol van, a vektor indexben) megjelenik; nyers PII külön kezelve (raw_content, personal_data tábla).
- **Bizonyítás:** Integrációs tesztek (pl. `test_pii_review_flow`, `test_file_ingest`, `test_pii_pipeline` replacement) lefedik ezt a folyamatot; release acceptance suite tartalmaz ilyen teszteket.

---

## 6. English, Hungarian, and Spanish are all covered at least at a solid baseline level

**Criterion:** Angol, magyar és spanyol **mindegyike** legalább **solid baseline** szinten lefedett – detektálás és policy ugyanazon entitásokra mindhárom nyelvnél értelmezett.

- **Baseline:** Legalább: email, telefon, név, dátum (és a supported listából további típusok) mindhárom nyelvön detektálódnak ahol a formátum nyelvfüggetlen vagy nyelvspecifikus minta van (pl. HU telefonszám, ES rendszám, EN email).
- **Nyelvdetektálás:** A pipeline nyelvet detektál vagy kapja; a megfelelő recognizer/NER/regex path fut (hu/en/es).
- **Tesztek:** Legalább egy pozitív teszt HU, EN és ES szövegre a kritikus entitásokra (pl. email, phone, name, vehicle registration); lásd coverage matrix „Positive HU / EN / ES” oszlopok.
- **Dokumentáció:** A supported listán vagy a coverage matrixban világos, hogy EN/HU/ES baseline mely típusokra van lefedve.

---

## Összefoglaló – mikor „usable”?

| # | Feltétel |
|---|----------|
| 1 | Nincs duplikált implementációs igazság (egy pipeline, egy adapter, egy placeholder/policy forrás). |
| 2 | Minden supported entitásnak van valódi detektora. |
| 3 | Minden supported entitásnak van valódi tesztje. |
| 4 | Unsupported entitások explicit backlog vagy xfail (dokumentum + tesztek). |
| 5 | Upload → detect → review → sanitize → index flow végpontoktól-végpontig bizonyított (E2E tesztek). |
| 6 | Angol, magyar és spanyol mind solid baseline szinten lefedve. |

Ha mind a hat teljesül, a rendszer **használható**. A `COVERAGE_MATRIX.md`, `MINIMUM_RELEASE_ACCEPTANCE.md` és `NOT_YET_SUPPORTED.md` dokumentumok segítenek ellenőrizni a 2–4–6. pontot; a release acceptance suite és a review flow tesztek a 5. pontot.
