# shared/text

A `shared/text` csomag általános szövegfeldolgozó utility réteg. Chunkolást, nyelvdetektálást, többnyelvű lexikon hozzáférést és karaktertartomány deduplikációt ad olyan app és core komponenseknek, amelyeknek nincs szükségük saját domain modellhez kötött NLP rétegre.

## Fő felelősség

Ez a modul kisméretű, determinisztikus text helper funkciókat tartalmaz. A knowledge ingest és runtime store chunkoláshoz használja, a PII pipeline-ok nyelvdetektáláshoz és span deduplikációhoz, a chat/knowledge query és claim feldolgozás pedig közös hu/en/es lexikon elemekhez.

## Fájlok

- `__init__.py`: publikus exportfelület a text helper függvényekhez.
- `chunking.py`: tréninghez és ingesthez használható szövegdarabolás bekezdés-, mondat- és fix méretű fallback alapján.
- `language_detection.py`: dokumentum- és chunk-szintű nyelvdetektálás `langdetect` alapú, en fallbackkel.
- `language_lexicon.py`: hu/en/es/generic lexikon kérdésszavakhoz, stopwordökhöz, idő-, hely-, állapot-, reláció- és szabálymarkerekhez.
- `span_utils.py`: átfedő karaktertartomány találatok deduplikációja "hosszabb találat nyer" szabállyal.

## Kapcsolódás a nagy egészhez

A knowledge app importálja chunkoláshoz, query resolverhez, claim extractionhöz, space-time extractionhöz és PII pipeline-okhoz. A chat service a lexikont kérdés- és entity normalizálási heurisztikákhoz használja. Unit tesztek fedik a lexikon fallbackeket, hónapfeloldást, nyelvdetektálást és PII span deduplikációt.

## Boundary Értékelés

A shared hely indokolt, mert a modul nem tárol állapotot, nem függ adatbázistól, tenanttól vagy konkrét app domain modellektől. Figyelni kell viszont arra, hogy üzleti claim szabályok, app-specifikus prompt/intent logika vagy domain response modellek ne ide kerüljenek; ezek maradjanak a knowledge/chat modulok saját service rétegében.

## Sárközi Mihály - 2026.05.21
