from __future__ import annotations

# backend/apps/kb/kb_ingest/orm/TrainingItem.py
# Feladat: Egy tanítandó anyag (szöveg / később fájl, URL) perzisztencia rekordja.
# Sárközi Mihály - 2026.06.07

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from shared.utils.clock import utc_now_naive
from core.kernel.db.model_bases import TenantSchemaBase


class TrainingItem(TenantSchemaBase):
    """Egy konkrét tanítási elem — nyers anyag hivatkozás, állapot, hiba, duplikátum kapcsolat.

    A tényleges tartalom object storage-ban van (``raw_ref`` kulcs); ez a sor csak
    metaadatot és feldolgozási állapotot tárol. A worker / understanding pipeline
    az ``id`` és ``raw_ref`` alapján tölti be a nyers szöveget.
    """

    __tablename__ = "kb_ingest_items"

    # Egyedi item azonosító (pl. training_item_…).
    id = Column(String(64), primary_key=True)
    # Szülő batch azonosító — ``kb_ingest_batches.id``.
    training_batch_id = Column(String(64), nullable=False, index=True)
    # Cél tudástár UUID-ja (denormalizált a gyors szűréshez).
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # Bemenet típusa: ``text`` | ``file`` | ``url`` (jelenleg főleg ``text``).
    input_type = Column(String(16), nullable=False, index=True)
    # Felhasználó által adott cím; üres string = nincs cím (megjelenítés a kliensen).
    title = Column(String(200), nullable=False, default="")
    # Elem állapot: ``pending`` | ``accepted`` | ``rejected`` | ``failed``.
    status = Column(String(32), nullable=False, default="pending", index=True)
    # Object storage kulcs a nyers anyaghoz (pl. tenants/…/training/…/input.txt).
    raw_ref = Column(String(1024), nullable=True)
    # Normalizált tanítási szöveg SHA-256 hash-e — tartalmi duplikátum kereséshez.
    content_hash = Column(String(128), nullable=True, index=True)
    # Gépi hibakód (``TrainingErrorCode`` érték); UI fordítás a kódból.
    error_code = Column(String(64), nullable=True)
    # Opcionális technikai hiba részlet (log / debug); nem lokalizált üzenet a felhasználónak.
    error_message = Column(Text, nullable=True)
    # Újrapróbálható-e a feldolgozás hiba esetén.
    retryable = Column(Boolean, nullable=False, default=False)
    # Eddigi újrapróbálások száma.
    retry_count = Column(Integer, nullable=False, default=0)
    # Ha duplikátum: az eredeti item ``id``-ja, amellyel egyezik a tartalom.
    duplicate_of_item_id = Column(String(64), nullable=True)
    # Eredeti fájlnév fájl-alapú tanításnál; szövegnél általában ``None``.
    original_filename = Column(String(255), nullable=True)
    # MIME típus (pl. ``text/plain``); object storage meta egyező mezője.
    mime_type = Column(String(255), nullable=True)
    # Nyers anyag mérete bájtban.
    size_bytes = Column(BigInteger, nullable=True)
    # Forrás URL (URL-alapú tanításnál); szöveges csatornánál ``None``.
    origin_url = Column(String(2048), nullable=True, index=True)
    # Végleges / átirányított URL letöltés után (URL csatorna).
    final_url = Column(String(2048), nullable=True)
    # HTTP státuszkód URL letöltésnél; egyéb csatornánál ``None``.
    status_code = Column(Integer, nullable=True)
    # Rekord létrehozása (UTC, naive).
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    # Elem feldolgozásának befejezése.
    completed_at = Column(DateTime, nullable=True)
    # Utolsó módosítás ideje.
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    # Kiegészítő meta (pl. ``char_count``, ``text_encoding``) — strukturált, nem lokalizált.
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)


__all__ = ["TrainingItem"]
