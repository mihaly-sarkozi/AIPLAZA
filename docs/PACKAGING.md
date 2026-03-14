# Package / import konzisztencia

## Egyértelmű stratégia

- **Csomag gyökér** = a repository gyökér (ahol a `pyproject.toml` van).  
  A Python import path gyökere itt van; nincs külön `knowledge/` a repo gyökerén.

- **Top-level csomagok:** csak **`apps`** és **`config`**.
  - Alkalmazás kód: `apps.*` (pl. `apps.knowledge`, `apps.auth`, `apps.core`).
  - Konfiguráció: `config.*` (pl. `config.settings`, `config.base`).

- **Knowledge modul:** mindig **`apps.knowledge`**, soha nem `knowledge` önmagában.  
  A tesztek és a kód egyaránt `from apps.knowledge....` importot használnak.

## Import szabályok

- Használd: `from apps.knowledge...`, `from apps.core...`, `from config.settings import ...`
- Ne használd: `from knowledge...` (nincs ilyen top-level csomag)

## Futtatás

1. **Ajánlott:** a repo gyökeréből `pip install -e .` – így az `apps` és `config` telepítve van, mindenhol működik az import.
2. **Alternatíva:** a repo gyökeréből `export PYTHONPATH=.` (vagy hasonló), majd ugyanonnan futtatod a parancsokat.
3. **Pytest:** mindig a **repo gyökeréből** indítsd (`pytest` vagy `pytest tests/...`).  
   A `pytest.ini` / `pyproject.toml` szerint `pythonpath = .` – a „.” a futtatás aktuális munkakönyvtára, ezért a pytest-et a repo gyökeréből kell futtatni.

## Scriptek

A `scripts/` alatti fájlok a repo gyökerét teszik a `sys.path` elé (`sys.path.insert(0, str(project_root))`), hogy `apps` és `config` importálható legyen. Futtatás: `python scripts/xyz.py` a repo gyökeréből, vagy ugyanonnan `python -m scripts.xyz` ha a scripts modulként van kezelve.

## Tesztek és lazy app

- **Unit tesztek** (`pytest tests/unit/`): nem importálják a `main` modult. A conftest csak akkor tölti be az appot, ha valamilyen integration fixture (pl. `client`) kell. Így a unit tesztek nem húzzák be a teljes runtime stacket (DB, Redis, middleware, stb.).
- **Integration tesztek**: a `client` és társai a conftest `app` fixture-jét használják; az app fixture session scope-ban lazy importtal hívja a `main` modult. Azok a tesztek, amelyek közvetlenül használják az `app`-ot (pl. `app.dependency_overrides`), a `get_app()` függvényt hívják a tests.conftest-ből.
- **Futtatás:** mindig a **repo gyökeréből**: `pytest`, `pytest tests/unit`, `pytest tests/integration`. A `pyproject.toml` és a `pytest.ini` szerint `pythonpath = .`, ezért a pytest-et a repo gyökeréből kell indítani (vagy `pip install -e .` után bárhonnan).

## Összefoglalva

| Kérdés | Válasz |
|--------|--------|
| Hol van a package root? | Repo gyökér (pyproject.toml mappa). |
| Milyen importok legyenek? | `apps.*`, `config.*`. |
| Van-e `knowledge` gyökér? | Nincs; a knowledge logika az `apps.knowledge` alatt van. |
| Hogyan futtassuk a teszteket? | Repo gyökeréből: `pytest` (vagy `pip install -e .` majd `pytest`). |
| Miért nem törik be a unit tesztek? | A conftest nem importálja a main-t top-level; az app csak akkor töltődik, ha kell (integration fixture). |
