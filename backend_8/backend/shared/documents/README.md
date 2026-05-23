# shared/documents

A `shared/documents` csomag általános dokumentum szöveg- és struktúra-kinyerő utility réteg. Core és app modulok egyaránt használhatják, mert nem importál domain service-t, repositoryt vagy app-specifikus típust.

## Fő felelősség

A modul TXT, PDF és DOCX feltöltésekből egységes `ExtractedDocument` contractot állít elő. A sima `extract_text_from_upload()` csak teljes szöveget ad vissza, az `extract_document_from_upload()` pedig bekezdés/lista/heading/táblázatsor/metadatablokk szintű struktúrát és extraction metadatát is.

## Fájlok

- `__init__.py`: publikus exportfelület a modellekhez és extraction helper függvényekhez.
- `models.py`: `ExtractedDocument` és `ExtractedParagraph` dataclass contractok.
- `text_extraction.py`: fájltípus szerinti TXT/PDF/DOCX orchestration és DOCX blokkfelismerés.
- `pdf_layout_parser.py`: PDF layout parsing, sorcsoportosítás, heading/lista/tábla/metadatablokk heurisztikák.

## Kapcsolódás a nagy egészhez

Jelenleg főleg a knowledge app ingest és training útvonalai használják, de a csomag szándékosan shared: bármely app modul használhatja dokumentumfeltöltések szövegének kinyerésére. A visszaadott modellek nem knowledge-specifikusak, így core és apps közös contractként kezelhetők.

## Boundary Értékelés

A modul shared helye indokolt, mert általános file-format extraction utility. Figyelendő határ, hogy a PDF parser tartalmaz néhány magyar/jogi dokumentumokra hangolt heurisztikát; ezek még dokumentum-layout jellegűek, de ha knowledge-domain szabályokká nőnek, külön app oldali extractor policy rétegbe kell őket áttenni.

## Függőségek

A PDF kinyerés `pdfplumber` csomagot használ, a DOCX kinyerés `python-docx`-ra épít. Ezek importja késleltetett az adott fájltípus feldolgozásáig.

## Shared Szabály

Ide csak általános dokumentumfeldolgozó, formátumkezelő és strukturálási logika kerüljön. Knowledge claim extraction, PII felismerés, tenant vagy app-specifikus validáció ne ebben a csomagban legyen.

## Sárközi Mihály - 2026.05.21
