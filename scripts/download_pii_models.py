#!/usr/bin/env python3
"""
PII NER modellek letöltése: spaCy (en, es) és Stanza (hu).
Futtatás: python scripts/download_pii_models.py

Angol + spanyol: spaCy (en_core_web_sm, es_core_news_sm).
Magyar: Stanza (hu) – a ~/Library/Caches/stanza vagy STANZA_CACHE_DIR alá tölt;
        ha nincs magyar modell, a magyar szöveg csak regex réteggel fut (NER nélkül).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    print("spaCy modellek (angol, spanyol)...")
    for model in ("en_core_web_sm", "es_core_news_sm"):
        subprocess.check_call(
            [sys.executable, "-m", "spacy", "download", model],
            cwd=root,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    print("Stanza magyar modell (a felhasználó cache könyvtárába kerül)...")
    import stanza
    stanza.download("hu", verbose=True)
    print("Kész.")


if __name__ == "__main__":
    main()
