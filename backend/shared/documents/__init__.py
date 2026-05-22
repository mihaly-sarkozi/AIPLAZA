# backend/shared/documents/__init__.py
# Feladat: A shared dokumentumfeldolgozó csomag exportfelülete. Strukturált ExtractedDocument/ExtractedParagraph modelleket és feltöltött TXT/PDF/DOCX fájlokból szöveget vagy dokumentumstruktúrát kinyerő helper függvényeket ad tovább core és app rétegek számára. Általános shared utility belépési pont, nem knowledge-specifikus service.
# Sárközi Mihály - 2026.05.21

from shared.documents.models import ExtractedDocument, ExtractedParagraph
from shared.documents.text_extraction import extract_document_from_upload, extract_text_from_upload

__all__ = [
    "ExtractedDocument",
    "ExtractedParagraph",
    "extract_document_from_upload",
    "extract_text_from_upload",
]
