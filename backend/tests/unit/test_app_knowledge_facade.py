from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import ProgrammingError

from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.parser_run import ParserRun
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.source import Source
from apps.knowledge.domain.retrieval_profile import DEFAULT_RETRIEVAL_PROFILE
from apps.knowledge.service.knowledge_facade import KnowledgeFacade
from apps.knowledge.service.runtime_store import (
    InMemoryIndexBuildStore,
    InMemoryIndexProfileStore,
    InMemoryMetricsStore,
    InMemoryQueryRunStore,
    InMemorySourceStore,
    SimpleChunkBuilder,
    SimpleContextBuilder,
    SimpleRetrievalEngine,
)
from shared.object_storage.models import StoredObjectData, StoredObjectRef

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_select_semantic_blocks_boosts_overview_block_for_what_does_system_do_query() -> None:
    blocks = [
        {
            "id": "single-claim",
            "source_id": "src-1",
            "claim_ids": ["c-1"],
            "primary_subject": "SK MAX rendszer számos alapbeállítást",
            "summary": "SK MAX rendszer számos alapbeállítást",
            "text": "Az SK MAX rendszerben számos alapbeállítást kell megadnod.",
            "sentence_ids": ["s-20"],
            "metadata": {"sentence_count": 1},
            "order_start": 20,
        },
        {
            "id": "overview",
            "source_id": "src-1",
            "claim_ids": ["c-5", "c-6"],
            "primary_subject": "SK MAX rendszer",
            "summary": "SK MAX rendszer áttekintés",
            "text": (
                "Az SK MAX rendszer kezeli a szerződéseket, támogatja az ügyféladatok kezelését, "
                "automatikusan felismer eseteket, és segíti a jutalékozási folyamatokat."
            ),
            "sentence_ids": [f"s-{idx}" for idx in range(5, 14)],
            "metadata": {"sentence_count": 9},
            "order_start": 5,
        },
    ]

    selected = KnowledgeFacade._select_semantic_blocks_for_query(
        semantic_blocks=blocks,
        matched_claims=[{"claim_id": "c-1"}],
        matched_chunks=[{"source_ids": ["src-1"]}],
        query_profile={"expected_answer_type": "object", "detected_entities": ["sk", "max", "rendszer"]},
        query="mit csinál az sk max rendszer?",
        max_blocks=2,
    )

    assert selected[0]["id"] == "overview"
    assert selected[0]["match_reason"]["exact_query_phrase"] is True
    assert selected[0]["match_reason"]["broad_function_query"] is True


class _FailingRetrievalEngine:
    def __init__(self) -> None:
        self.calls = 0

    async def retrieve(self, **_kwargs):
        self.calls += 1
        raise RuntimeError("vector backend unavailable")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _CorpusStore:
    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.items = {
            "kb-1": Corpus(
                id=1,
                tenant="demo",
                uuid="kb-1",
                name="Pilot KB",
                description="Demo corpus",
                qdrant_collection_name="kb_kb-1",
                created_at=now,
                updated_at=now,
            )
        }
        self.permissions = {"kb-1": [(11, "train")]}

    def list_all(self, *, include_deleted: bool = False) -> list[Corpus]:
        return list(self.items.values())

    def get_by_uuid(self, uuid: str) -> Corpus | None:
        return self.items.get(uuid)

    def get_by_name(self, name: str) -> Corpus | None:
        return next((item for item in self.items.values() if item.name == name), None)

    def create(self, corpus: Corpus, *, actor_user_id: int) -> Corpus:
        now = datetime.now(timezone.utc)
        created = replace(corpus, id=len(self.items) + 1, created_at=now, updated_at=now)
        self.items[created.uuid] = created
        return created

    def update(self, corpus: Corpus, *, actor_user_id: int) -> Corpus:
        updated = replace(corpus, updated_at=datetime.now(timezone.utc))
        self.items[updated.uuid] = updated
        return updated

    def delete(self, uuid: str, *, training_char_count: int = 0) -> None:
        self.items.pop(uuid, None)

    def list_permissions(self, corpus_uuid: str) -> list[tuple[int, str]]:
        return list(self.permissions.get(corpus_uuid, []))

    def list_permissions_batch(self, corpus_uuids: list[str]) -> dict[str, list[tuple[int, str]]]:
        return {item: list(self.permissions.get(item, [])) for item in corpus_uuids}

    def set_permissions(self, corpus_uuid: str, permissions: list[tuple[int, str]], *, actor_user_id: int) -> None:
        self.permissions[corpus_uuid] = list(permissions)

    def get_kb_ids_with_permission(self, user_id: int, permission: str) -> list[int]:
        allowed: list[int] = []
        for corpus_uuid, perms in self.permissions.items():
            corpus = self.items.get(corpus_uuid)
            if corpus is None or corpus.id is None:
                continue
            for current_user_id, current_permission in perms:
                if current_user_id != user_id:
                    continue
                if permission == "train" and current_permission == "train":
                    allowed.append(corpus.id)
                elif permission != "train" and current_permission in {"use", "train"}:
                    allowed.append(corpus.id)
        return allowed


class _UserRepo:
    def list_all(self):
        return []


class _NoopStore:
    def create(self, item):
        return item

    def create_many(self, items):
        return items

    def update(self, item):
        return item

    def save(self, item):
        return item

    def get(self, *_args, **_kwargs):
        return None

    def list_for_corpus(self, *_args, **_kwargs):
        return []

    def list_recent(self, *_args, **_kwargs):
        return []

    def list_for_document(self, *_args, **_kwargs):
        return []

    def delete_for_document(self, *_args, **_kwargs):
        return 0

    def delete_for_source(self, *_args, **_kwargs):
        return 0


class _InMemoryIngestRunStore:
    def __init__(self) -> None:
        self.items: dict[str, IngestRun] = {}

    def create(self, item: IngestRun) -> IngestRun:
        self.items[item.id] = item
        return item

    def update(self, item: IngestRun) -> IngestRun:
        self.items[item.id] = item
        return item

    def get(self, item_id: str) -> IngestRun | None:
        return self.items.get(item_id)

    def list_for_corpus(self, corpus_uuid: str, limit: int = 20) -> list[IngestRun]:
        items = [item for item in self.items.values() if item.corpus_uuid == corpus_uuid]
        return sorted(items, key=lambda item: item.created_at, reverse=True)[:limit]


class _InMemoryIngestItemStore:
    def __init__(self) -> None:
        self.items: dict[str, IngestItem] = {}

    def create(self, item: IngestItem) -> IngestItem:
        self.items[item.id] = item
        return item

    def create_many(self, items: list[IngestItem]) -> list[IngestItem]:
        for item in items:
            self.items[item.id] = item
        return items

    def update(self, item: IngestItem) -> IngestItem:
        self.items[item.id] = item
        return item

    def get(self, item_id: str) -> IngestItem | None:
        return self.items.get(item_id)

    def list_for_run(self, run_id: str) -> list[IngestItem]:
        items = [item for item in self.items.values() if item.ingest_run_id == run_id]
        return sorted(items, key=lambda item: item.queue_order)


class _InMemoryIngestEventStore:
    def __init__(self) -> None:
        self.items: list[IngestEvent] = []

    def create(self, item: IngestEvent) -> IngestEvent:
        self.items.append(item)
        return item

    def list_for_run(self, run_id: str, limit: int = 200) -> list[IngestEvent]:
        return [item for item in self.items if item.ingest_run_id == run_id][:limit]


class _NoopObjectStorage:
    def put_bytes(self, *, key: str, content: bytes, bucket: str | None = None, content_type: str | None = None, metadata=None):
        return StoredObjectRef(
            provider="noop",
            bucket=bucket or "test-bucket",
            key=key,
            size_bytes=len(content),
            content_type=content_type,
            metadata=metadata or {},
        )

    def put_fileobj(self, *, key: str, fileobj, bucket: str | None = None, content_type: str | None = None, metadata=None):
        pos = fileobj.tell()
        fileobj.seek(0)
        content = fileobj.read()
        fileobj.seek(pos)
        return self.put_bytes(
            key=key,
            content=content,
            bucket=bucket,
            content_type=content_type,
            metadata=metadata,
        )

    def put_text(
        self,
        *,
        key: str,
        text: str,
        bucket: str | None = None,
        encoding: str = "utf-8",
        content_type: str = "text/plain; charset=utf-8",
        metadata=None,
    ):
        return self.put_bytes(
            key=key,
            content=text.encode(encoding),
            bucket=bucket,
            content_type=content_type,
            metadata=metadata,
        )

    def get_bytes(self, *, key: str, bucket: str | None = None) -> StoredObjectData:
        return StoredObjectData(
            ref=StoredObjectRef(
                provider="noop",
                bucket=bucket or "test-bucket",
                key=key,
                size_bytes=0,
                content_type="application/octet-stream",
                metadata={},
            ),
            body=b"",
        )

    def stat_object(self, *, key: str, bucket: str | None = None) -> StoredObjectRef:
        return StoredObjectRef(provider="noop", bucket=bucket or "test-bucket", key=key, content_type=None, size_bytes=0, metadata={})

    def delete_object(self, *, key: str, bucket: str | None = None) -> None:
        return None

    def build_key(self, *parts: str) -> str:
        return "/".join(part.strip("/") for part in parts if part)


class _VectorIndex:
    def __init__(self) -> None:
        self.collections: dict[str, list[dict[str, object]]] = {}
        self.ensure_calls: list[tuple[str, int | None]] = []

    async def ensure_collection_schema_async(self, collection_name: str, vector_size: int | None = None) -> None:
        self.ensure_calls.append((collection_name, vector_size))
        self.collections.setdefault(collection_name, [])

    async def upsert_sentence_points(self, collection: str, rows: list[dict[str, object]]) -> None:
        self.collections.setdefault(collection, [])
        for idx, row in enumerate(rows):
            payload = dict(row.get("payload") or {})
            payload["text"] = row.get("text")
            payload.setdefault("point_type", "sentence")
            self.collections[collection].append(
                {
                    "id": f"{collection}-{idx}",
                    "payload": payload,
                    "fusion_score": 0.9,
                    "score": 0.9,
                }
            )

    async def upsert_retrieval_chunk_points(self, collection: str, rows: list[dict[str, object]]) -> None:
        self.collections.setdefault(collection, [])
        for row in rows:
            payload = dict(row.get("payload") or {})
            payload["text"] = row.get("text")
            payload.setdefault("point_type", "retrieval_chunk")
            self.collections[collection].append(
                {
                    "id": str(row.get("id")),
                    "payload": payload,
                    "fusion_score": 0.95,
                    "score": 0.95,
                }
            )

    async def upsert_semantic_block_points(self, collection: str, rows: list[dict[str, object]]) -> None:
        self.collections.setdefault(collection, [])
        for row in rows:
            payload = dict(row.get("payload") or {})
            payload["text"] = row.get("text")
            payload.setdefault("point_type", "semantic_block")
            self.collections[collection].append(
                {
                    "id": str(row.get("id")),
                    "payload": payload,
                    "fusion_score": 0.92,
                    "score": 0.92,
                }
            )

    async def search_points(
        self,
        collection: str,
        query: str | None = None,
        limit: int = 10,
        point_types: list[str] | None = None,
        payload_filter: dict[str, object] | None = None,
        query_vector: list[float] | None = None,
        lexical_query: str | None = None,
        fusion_semantic_weight: float | None = None,
        fusion_lexical_weight: float | None = None,
        lexical_focus_terms: list[str] | None = None,
        exact_phrases: list[str] | None = None,
        rare_terms: list[str] | None = None,
    ) -> list[dict[str, object]]:
        rows = list(self.collections.get(collection, []))
        if point_types:
            rows = [row for row in rows if (row.get("payload") or {}).get("point_type") in set(point_types)]
        for key, value in (payload_filter or {}).items():
            if isinstance(value, list):
                rows = [row for row in rows if set(value).intersection(set((row.get("payload") or {}).get(key) or []))]
            else:
                rows = [row for row in rows if (row.get("payload") or {}).get(key) == value]
        return rows[:limit]


def _build_facade(vector_index: _VectorIndex | None = None) -> KnowledgeFacade:
    vector = vector_index or _VectorIndex()
    noop_store = _NoopStore()
    return KnowledgeFacade(
        corpus_store=_CorpusStore(),
        user_repo=_UserRepo(),
        source_store=InMemorySourceStore(),
        ingest_run_store=noop_store,
        ingest_item_store=noop_store,
        ingest_input_store=noop_store,
        ingest_event_store=noop_store,
        parser_run_store=noop_store,
        document_store=noop_store,
        paragraph_store=noop_store,
        sentence_store=noop_store,
        index_profile_store=InMemoryIndexProfileStore(),
        index_build_store=InMemoryIndexBuildStore(),
        query_run_store=InMemoryQueryRunStore(),
        chunk_builder=SimpleChunkBuilder(),
        retrieval_engine=SimpleRetrievalEngine(lambda: vector),
        context_builder=SimpleContextBuilder(),
        vector_index_factory=lambda: vector,
        metrics_store=InMemoryMetricsStore(),
        object_storage=_NoopObjectStorage(),
    )


def test_split_sentences_keeps_numbered_list_item_together() -> None:
    text = "1. Első pont részletes leírása. 2. Második pont külön mondat."

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "1. Első pont részletes leírása.",
        "2. Második pont külön mondat.",
    ]


@pytest.mark.anyio
async def test_retrieval_resilience_falls_back_when_vector_backend_fails() -> None:
    facade = _build_facade()
    failing = _FailingRetrievalEngine()
    facade._retrieval_engine = failing

    hits = await facade._retrieve_hits_with_resilience(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
        builds=[
            IndexBuild(
                tenant="demo",
                corpus_uuid="kb-1",
                index_profile_key="basic_chunk_v1",
                collection_name="kb_1__basic_chunk_v1",
            )
        ],
        retrieval_profile=DEFAULT_RETRIEVAL_PROFILE,
        query_profile={"intent": "state"},
    )

    assert hits == []
    assert failing.calls == 2
    assert facade._metrics_store.snapshot()["counters"]["query_retrieval_error_count"] == 2
    assert facade._metrics_store.snapshot()["counters"]["query_retrieval_fallback_count"] == 1


def test_split_sentences_does_not_break_on_common_abbreviation() -> None:
    text = "Ez egy rövidítés pl. egy tipikus példa. A következő mondat külön áll."

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "Ez egy rövidítés pl. egy tipikus példa.",
        "A következő mondat külön áll.",
    ]


def test_split_sentences_can_break_long_text_without_period() -> None:
    text = (
        "Ez egy hosszú bevezető szakasz amelyben nincs pont mégis elég hosszú ahhoz hogy önálló mondatként "
        "értelmezzük és ne maradjon egyben A következő rész már egy új mondat logikája szerint folytatódik"
    )

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "Ez egy hosszú bevezető szakasz amelyben nincs pont mégis elég hosszú ahhoz hogy önálló mondatként értelmezzük és ne maradjon egyben A következő rész már egy új mondat logikája szerint folytatódik"
    ]


def test_split_sentences_can_break_long_line_on_newline_without_period() -> None:
    text = (
        "Ez itt egy hosszú sor amely pont nélkül zárul de tartalmilag már lezártnak tekinthető mert teljes állítást ad\n"
        "A következő sor már új gondolatot kezd és külön mondatként kell kezelni"
    )

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "Ez itt egy hosszú sor amely pont nélkül zárul de tartalmilag már lezártnak tekinthető mert teljes állítást ad",
        "A következő sor már új gondolatot kezd és külön mondatként kell kezelni",
    ]


def test_normalize_parser_text_joins_hyphenated_linebreak_without_space_before_hyphen() -> None:
    text = "Az időjárás-biztosítás különös feltételeiben a bizto-\nsítás aktiválása szükséges."

    result = KnowledgeFacade._normalize_parser_text(text)

    assert result == "Az időjárás-biztosítás különös feltételeiben a biztosítás aktiválása szükséges."


def test_normalize_parser_text_keeps_spaced_dash_at_linebreak() -> None:
    text = "Ez egy felsorolás -\nkülön magyarázattal."

    result = KnowledgeFacade._normalize_parser_text(text)

    assert result == "Ez egy felsorolás -\nkülön magyarázattal."


def test_describe_empty_extraction_reports_image_only_pdf() -> None:
    result = KnowledgeFacade._describe_empty_extraction(
        {
            "source_format": "pdf",
            "page_count": 2,
            "no_extractable_text": True,
            "pdf_producer": "Quartz PDFContext",
            "pdf_title": "Képernyőfotó",
        }
    )

    assert "nem tartalmaz kiolvasható szövegréteget" in result
    assert "2 oldalas PDF" in result
    assert "Quartz PDFContext" in result
    assert "OCR szükséges" in result


def test_split_sentences_does_not_break_immediately_after_colon_when_not_sentence_start() -> None:
    text = "A rendszer részei: backend, frontend, API."

    result = KnowledgeFacade._split_sentences(text)

    assert result == ["A rendszer részei: backend, frontend, API."]


def test_split_sentence_candidates_include_confidence_and_reason() -> None:
    text = "Az ég kék. A fű zöld."

    result = KnowledgeFacade._split_sentence_candidates(text)

    assert [item.text for item in result] == ["Az ég kék.", "A fű zöld."]
    assert all(item.confidence >= 0.6 for item in result)
    assert all(item.split_reason == "strong_punctuation" for item in result)


def test_split_sentences_does_not_break_common_dotted_abbreviations() -> None:
    text = "This is e.g. a short example. Another sentence follows."

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "This is e.g. a short example.",
        "Another sentence follows.",
    ]


def test_split_sentences_does_not_break_on_hungarian_date_tokens() -> None:
    text = "A szerződés kelte: 2024. 05. 12. napján került aláírásra. A következő mondat külön áll."

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "A szerződés kelte: 2024. 05. 12. napján került aláírásra.",
        "A következő mondat külön áll.",
    ]


def test_split_sentences_does_not_break_on_month_name_date() -> None:
    text = "A teljesítés ideje 2024. május 12. A következő bekezdés új mondatot kezd."

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "A teljesítés ideje 2024. május 12.",
        "A következő bekezdés új mondatot kezd.",
    ]


def test_split_sentences_keeps_heading_as_single_unit() -> None:
    text = "2. Projekt áttekintés és következő lépések"

    result = KnowledgeFacade._split_sentences(text, block_type="heading")

    assert result == ["2. Projekt áttekintés és következő lépések"]


def test_split_sentences_splits_numbered_heading_when_body_contains_multiple_sentences() -> None:
    text = (
        "7.D.2. A szerződő által a biztosítási szerződés létrejöttét megelőzően a biztosító részére "
        "megfizetett díj (vagy díjrészlet) díjelőlegnek minősül, melyet a biztosító kamatmentesen kezel. "
        "Ha a szerződés létrejön, a biztosító a díjelőleget a biztosítási díjba beszámítja. "
        "Ha a szerződés nem jön létre, a biztosító a díjelőleget a szerződőnek visszafizeti."
    )

    result = KnowledgeFacade._split_sentences(text, block_type="heading")

    assert result == [
        "7.D.2. A szerződő által a biztosítási szerződés létrejöttét megelőzően a biztosító részére megfizetett díj (vagy díjrészlet) díjelőlegnek minősül, melyet a biztosító kamatmentesen kezel.",
        "Ha a szerződés létrejön, a biztosító a díjelőleget a biztosítási díjba beszámítja.",
        "Ha a szerződés nem jön létre, a biztosító a díjelőleget a szerződőnek visszafizeti.",
    ]


def test_split_sentences_splits_roman_heading_subsections_and_lettered_items() -> None:
    text = (
        "IV. FELÜGYELETI HATÓSÁG IV.1. A biztosító felügyeleti szerve a Magyar Nemzeti Bank "
        "(a továbbiakban: MNB vagy Felügyelet). A Felügyelet elérhetőségei. "
        "IV.2. A Felügyelet ellenőrzi a) az első kötelezettséget, valamint b) a második kötelezettséget."
    )

    result = KnowledgeFacade._split_sentences(text, block_type="heading")

    assert result == [
        "IV. FELÜGYELETI HATÓSÁG",
        "IV.1. A biztosító felügyeleti szerve a Magyar Nemzeti Bank (a továbbiakban: MNB vagy Felügyelet).",
        "A Felügyelet elérhetőségei.",
        "IV.2. A Felügyelet ellenőrzi",
        "a) az első kötelezettséget, valamint",
        "b) a második kötelezettséget.",
    ]


def test_split_sentences_splits_dense_heading_with_inline_subsections_and_lettered_items() -> None:
    text = (
        "IV. FELÜGYELETI HATÓSÁG IV.1. A biztosító felügyeleti szerve a Magyar Nemzeti Bank "
        "(a továbbiakban: MNB vagy Felügyelet) A Felügyelet elérhetőségei Székhelye: 1054 Budapest, Szabadság tér 8-9. "
        "IV.2. Társaságunk az MNB által felügyelt tevékenység folytatására jogosult szervezet, amelyet a Felügyelet ellenőriz "
        "a) az első kötelezettség tekintetében, valamint b) a második kötelezettség tekintetében."
    )

    result = KnowledgeFacade._split_sentences(text, block_type="heading")

    assert result == [
        "IV. FELÜGYELETI HATÓSÁG",
        "IV.1. A biztosító felügyeleti szerve a Magyar Nemzeti Bank (a továbbiakban: MNB vagy Felügyelet) A Felügyelet elérhetőségei Székhelye: 1054 Budapest, Szabadság tér 8-9.",
        "IV.2. Társaságunk az MNB által felügyelt tevékenység folytatására jogosult szervezet, amelyet a Felügyelet ellenőriz",
        "a) az első kötelezettség tekintetében, valamint",
        "b) a második kötelezettség tekintetében.",
    ]


def test_split_sentences_recognizes_simple_roman_heading_marker() -> None:
    text = "IV. FELÜGYELETI HATÓSÁG IV.1. Első alpont. IV.2. Második alpont."

    result = KnowledgeFacade._split_sentences(text, block_type="heading")

    assert result == [
        "IV. FELÜGYELETI HATÓSÁG",
        "IV.1. Első alpont.",
        "IV.2. Második alpont.",
    ]


def test_split_sentences_splits_non_numbered_heading_on_strong_punctuation() -> None:
    text = (
        "Baleset miatti elpusztulás Biztosítási esemény az a baleset, amelynek következtében a biztosított állat "
        "a balesetet követő 30 napon belül elpusztul. Állatorvosi kezelési költség A jelen biztosítás "
        "szempontjából állatorvosi kezelési költség alatt értendő a biztosított állat baleset vagy betegség "
        "miatti gyógykezelésével összefüggő állatorvosi munkadíj."
    )

    result = KnowledgeFacade._split_sentences(text, block_type="heading")

    assert result == [
        "Baleset miatti elpusztulás Biztosítási esemény az a baleset, amelynek következtében a biztosított állat a balesetet követő 30 napon belül elpusztul.",
        "Állatorvosi kezelési költség A jelen biztosítás szempontjából állatorvosi kezelési költség alatt értendő a biztosított állat baleset vagy betegség miatti gyógykezelésével összefüggő állatorvosi munkadíj.",
    ]


def test_split_sentences_keeps_list_item_as_single_unit() -> None:
    text = "1. Első ellenőrző pont.\nRövid magyarázat ugyanabban a listaelemben."

    result = KnowledgeFacade._split_sentences(text, block_type="list_item")

    assert result == ["1. Első ellenőrző pont.", "Rövid magyarázat ugyanabban a listaelemben."]


def test_split_sentences_splits_list_item_on_strong_punctuation() -> None:
    text = (
        "Baleset miatti elpusztulás Biztosítási esemény az a baleset, amelynek következtében a biztosított állat "
        "a balesetet követő 30 napon belül elpusztul. Állatorvosi kezelési költség A jelen biztosítás "
        "szempontjából állatorvosi kezelési költség alatt értendő a biztosított állat baleset vagy betegség "
        "miatti gyógykezelésével összefüggő állatorvosi munkadíj."
    )

    result = KnowledgeFacade._split_sentences(text, block_type="list_item")

    assert result == [
        "Baleset miatti elpusztulás Biztosítási esemény az a baleset, amelynek következtében a biztosított állat a balesetet követő 30 napon belül elpusztul.",
        "Állatorvosi kezelési költség A jelen biztosítás szempontjából állatorvosi kezelési költség alatt értendő a biztosított állat baleset vagy betegség miatti gyógykezelésével összefüggő állatorvosi munkadíj.",
    ]


def test_build_sentence_units_for_table_row_splits_cells_with_headers() -> None:
    facade = _build_facade()

    result = facade._build_sentence_units_for_paragraph(
        "Bonus-malus | A10",
        block_type="table_row",
        paragraph_metadata={
            "table_cells": ["Bonus-malus", "A10"],
            "table_role": "row",
            "table_column_headers": ["Mező", "Érték"],
        },
    )

    assert [item["text"] for item in result] == ["Mező: Bonus-malus", "Érték: A10"]
    assert result[0]["metadata"]["table_column_header"] == "Mező"
    assert result[1]["metadata"]["table_column_index"] == 2


def test_build_sentence_units_for_metadata_returns_single_unit() -> None:
    facade = _build_facade()

    result = facade._build_sentence_units_for_paragraph(
        "1. Bevezetés ........ 3",
        block_type="metadata",
        paragraph_metadata={"metadata_kind": "table_of_contents"},
    )

    assert result == [{"text": "1. Bevezetés ........ 3", "metadata": {}}]


def test_split_sentences_does_not_break_hierarchical_marker() -> None:
    text = "12.2. A Megbízó felhatalmazza az Alkuszt a hírlevél szolgáltatás rögzítésére."

    result = KnowledgeFacade._split_sentences(text)

    assert result == ["12.2. A Megbízó felhatalmazza az Alkuszt a hírlevél szolgáltatás rögzítésére."]


def test_split_sentences_numeric_period_needs_uppercase_after_it() -> None:
    text = "A gazdasági reklámtevékenységről szóló 2008. évi XLVIII. törvény alkalmazandó."

    result = KnowledgeFacade._split_sentences(text)

    assert result == ["A gazdasági reklámtevékenységről szóló 2008. évi XLVIII. törvény alkalmazandó."]


def test_split_sentences_numeric_period_can_close_sentence_after_enough_words() -> None:
    text = "A szabályozás 1971. A következő mondat már új gondolatot kezd."

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "A szabályozás 1971.",
        "A következő mondat már új gondolatot kezd.",
    ]


def test_split_sentences_short_fragment_before_numeric_marker_stays_joined() -> None:
    text = "Lásd. 3. pont részletes ismertetése következik."

    result = KnowledgeFacade._split_sentences(text)

    assert result == ["Lásd. 3. pont részletes ismertetése következik."]


def test_split_sentences_breaks_before_parenthesized_list_marker() -> None:
    text = "Az ajánlat érvényes a) ha a díj rendezett b) ha a szerződő nyilatkozott."

    result = KnowledgeFacade._split_sentences(text)

    assert result == [
        "Az ajánlat érvényes",
        "a) ha a díj rendezett",
        "b) ha a szerződő nyilatkozott.",
    ]


def test_split_sentences_does_not_break_legal_reference_parenthesized_marker() -> None:
    text = "Az adatkezelésre a 12/A. § (2) bekezdés a) pontja és a 3. § (1) bek. irányadó."

    result = KnowledgeFacade._split_sentences(text)

    assert result == ["Az adatkezelésre a 12/A. § (2) bekezdés a) pontja és a 3. § (1) bek. irányadó."]


def test_build_sentence_units_for_paragraph_adds_split_metadata() -> None:
    facade = _build_facade()

    result = facade._build_sentence_units_for_paragraph(
        "Az ég kék. A fű zöld.",
        block_type="paragraph",
        paragraph_metadata={},
    )

    assert [item["text"] for item in result] == ["Az ég kék.", "A fű zöld."]
    assert result[0]["metadata"]["split_reason"] == "strong_punctuation"
    assert result[0]["metadata"]["split_confidence"] >= 0.6


def test_build_sentence_units_for_paragraph_can_use_claim_refinement_during_parser_phase() -> None:
    class _ObservedClaimSplitter:
        def __init__(self) -> None:
            self.called = False

        def split_block(self, *_args, **_kwargs):
            self.called = True
            return []

    facade = _build_facade()
    splitter = _ObservedClaimSplitter()
    facade._claim_fine_splitter = splitter

    result = facade._build_sentence_units_for_paragraph(
        "A biztosító szolgáltatása akkor teljesíthető ha a bejelentés hiánytalan és a díj rendezett",
        block_type="paragraph",
        paragraph_metadata={},
    )

    assert splitter.called is True
    assert result
    assert result[0]["text"].startswith("A biztosító szolgáltatása")


def test_build_sentence_units_for_paragraph_collects_refinement_diagnostics() -> None:
    class _ObservedClaimSplitter:
        def split_block(self, *_args, **_kwargs):
            class _Claim:
                def __init__(self, text_span: str, start: int, end: int) -> None:
                    self.text_span = text_span
                    self.char_start = start
                    self.char_end = end
                    self.split_reason = ["test"]
                    self.confidence = 0.91
                    self.subject_hint = "biztosító"
                    self.predicate_hint = "teljesít"
                    self.object_hint = "szolgáltatás"

            text = "A biztosító szolgáltatása akkor teljesíthető"
            return [_Claim(text, 0, len(text))]

    facade = _build_facade()
    facade._claim_fine_splitter = _ObservedClaimSplitter()

    result, diagnostics = facade._build_sentence_units_for_paragraph_with_diagnostics(
        "A biztosító szolgáltatása akkor teljesíthető ha a bejelentés hiánytalan és a díj rendezett",
        block_type="paragraph",
        paragraph_metadata={},
    )

    assert result
    assert diagnostics["candidate_count"] >= 1
    assert diagnostics["claim_refinement_attempts"] >= 1
    assert diagnostics["claim_refinement_hits"] == 1
    assert diagnostics["claim_refinement_units"] == 1


def test_build_sentence_units_for_paragraph_skips_claim_refinement_for_short_candidate() -> None:
    class _ObservedClaimSplitter:
        def __init__(self) -> None:
            self.called = False

        def split_block(self, *_args, **_kwargs):
            self.called = True
            return []

    facade = _build_facade()
    splitter = _ObservedClaimSplitter()
    facade._claim_fine_splitter = splitter
    facade._is_strong_sentence_candidate = lambda _candidate: False  # type: ignore[method-assign]

    result, diagnostics = facade._build_sentence_units_for_paragraph_with_diagnostics(
        "Rövid feltétel és kivétel.",
        block_type="paragraph",
        paragraph_metadata={},
    )

    assert result
    assert splitter.called is False
    assert diagnostics["claim_refinement_attempts"] == 0
    assert diagnostics["claim_refinement_gate_reason"] == "too_short"


def test_build_sentence_units_for_paragraph_skips_claim_refinement_when_budget_exhausted() -> None:
    class _ObservedClaimSplitter:
        def __init__(self) -> None:
            self.called = False

        def split_block(self, *_args, **_kwargs):
            self.called = True
            return []

    facade = _build_facade()
    splitter = _ObservedClaimSplitter()
    facade._claim_fine_splitter = splitter
    facade._is_strong_sentence_candidate = lambda _candidate: False  # type: ignore[method-assign]

    result, diagnostics = facade._build_sentence_units_for_paragraph_with_diagnostics(
        "A biztosító szolgáltatása akkor teljesíthető ha a bejelentés hiánytalan és a díj rendezett valamint a szerződő értesítést küld.",
        block_type="paragraph",
        paragraph_metadata={},
        refinement_state={"budget_blocks": 0, "attempted_blocks": 0, "hit_blocks": 0},
    )

    assert result
    assert splitter.called is False
    assert diagnostics["claim_refinement_attempts"] == 0
    assert diagnostics["claim_refinement_gate_reason"] == "budget_exhausted"


def test_build_sentence_units_for_paragraph_skips_claim_refinement_after_low_yield_early_stop() -> None:
    class _ObservedClaimSplitter:
        def __init__(self) -> None:
            self.called = False

        def split_block(self, *_args, **_kwargs):
            self.called = True
            return []

    facade = _build_facade()
    splitter = _ObservedClaimSplitter()
    facade._claim_fine_splitter = splitter
    facade._is_strong_sentence_candidate = lambda _candidate: False  # type: ignore[method-assign]

    result, diagnostics = facade._build_sentence_units_for_paragraph_with_diagnostics(
        "A biztosító szolgáltatása akkor teljesíthető ha a bejelentés hiánytalan és a díj rendezett valamint a szerződő értesítést küld.",
        block_type="paragraph",
        paragraph_metadata={},
        refinement_state={
            "budget_blocks": 40,
            "attempted_blocks": 24,
            "hit_blocks": 0,
            "early_stop_after_blocks": 24,
            "min_hit_blocks_to_continue": 2,
        },
    )

    assert result
    assert splitter.called is False
    assert diagnostics["claim_refinement_attempts"] == 0
    assert diagnostics["claim_refinement_gate_reason"] == "low_yield_early_stop"


def test_build_mentions_for_sentence_detects_roles_and_document_reference() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content="A Megbízó a 2008. évi XLVIII. törvény alapján felhatalmazza az Alkuszt.",
        char_start=0,
        char_end=76,
    )

    mentions = facade._build_mentions_for_sentence(sentence)

    assert any(item.mention_type == "role" and item.text_content == "Megbízó" for item in mentions)
    assert any(item.mention_type == "role" and item.text_content == "Alkuszt" for item in mentions) is False
    assert any(item.mention_type == "document_reference" for item in mentions)


def test_build_mentions_for_sentence_detects_legal_paragraph_reference() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content="Az adatkezelésre a 12/A. § (2) bekezdés a) pontja és a 3. § (1) bek. irányadó.",
        char_start=0,
        char_end=86,
    )

    mentions = facade._build_mentions_for_sentence(sentence)

    assert any(
        item.mention_type == "document_reference" and item.text_content == "12/A. § (2) bekezdés a) pont"
        for item in mentions
    )
    assert any(item.mention_type == "document_reference" and item.text_content == "3. § (1) bek." for item in mentions)


def test_build_mentions_for_sentence_detects_identifiers_and_contacts() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content=(
            "Kapcsolat: Kiss Péter, email: peter.kiss@example.com, telefon: +36 30 123 4567, "
            "születési dátum: 1985. 04. 12., adószám: 12345678-1-42, rendszám: ABC-123, "
            "alvázszám: WVWZZZ1JZXW000001, kód: AB12-CD34."
        ),
        char_start=0,
        char_end=220,
    )

    mentions = facade._build_mentions_for_sentence(sentence)

    assert any(item.mention_type == "person" and item.text_content == "Kiss Péter" for item in mentions)
    assert any(item.mention_type == "email" and item.normalized_value == "peter.kiss@example.com" for item in mentions)
    assert any(item.mention_type == "phone_number" and item.normalized_value == "36301234567" for item in mentions)
    assert any(item.mention_type == "birth_date" for item in mentions)
    assert any(item.mention_type == "tax_id" and item.text_content == "12345678-1-42" for item in mentions)
    assert any(item.mention_type == "license_plate" and item.text_content == "ABC-123" for item in mentions)
    assert any(item.mention_type == "vin" and item.text_content == "WVWZZZ1JZXW000001" for item in mentions)
    assert any(item.mention_type == "mixed_identifier" and item.text_content == "AB12-CD34" for item in mentions)


def test_build_mentions_for_sentence_detects_company_and_local_identifiers() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content=(
            "Az Alfa Beta Kft. képviselője bemutatta a forgalmi számot AB123456, "
            "a jogosítvány számát B1234567, a TB kártya számát 123 456 789 és a cégjegyzékszámot 01-09-999999."
        ),
        char_start=0,
        char_end=190,
    )

    mentions = facade._build_mentions_for_sentence(sentence)

    assert any(item.mention_type == "organization" and "Alfa Beta Kft." in item.text_content for item in mentions)
    assert any(item.mention_type == "traffic_permit_number" and item.normalized_value == "AB123456" for item in mentions)
    assert any(item.mention_type == "driver_license_number" and item.normalized_value == "B1234567" for item in mentions)
    assert any(item.mention_type == "social_security_number" for item in mentions)
    assert any(item.mention_type == "company_registration_number" and item.text_content == "01-09-999999" for item in mentions)


def test_build_mentions_for_sentence_detects_eu_identifiers_and_address() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content=(
            "Az ügyfél címe: Calle Mayor 12, 28013 Madrid, España. "
            "Azonosítók: X1234567L, B12345678, ESB12345678, FR1420041010050500013M02606, DEUTDEFF és 54321."
        ),
        char_start=0,
        char_end=180,
    )

    mentions = facade._build_mentions_for_sentence(sentence)

    assert any(item.mention_type == "address" and "Calle Mayor 12, 28013 Madrid, España" in item.text_content for item in mentions)
    assert any(item.mention_type == "spanish_nie" and item.normalized_value == "X1234567L" for item in mentions)
    assert any(item.mention_type == "spanish_cif" and item.normalized_value == "B12345678" for item in mentions)
    assert any(item.mention_type == "eu_vat_number" and item.normalized_value == "ESB12345678" for item in mentions)
    assert any(item.mention_type == "iban" and item.normalized_value == "FR1420041010050500013M02606" for item in mentions)
    assert any(item.mention_type == "bic_swift" and item.normalized_value == "DEUTDEFF" for item in mentions)
    assert any(item.mention_type == "generic_identifier" and item.normalized_value == "54321" for item in mentions)


def test_build_mentions_for_sentence_does_not_treat_common_words_as_bic_swift() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content=(
            "A rendeletben meghatározott esetekben a biztosítóval szemben, ha az tartalmazza az ügyfél nevét, "
            "akkor az adatkérés vizsgálható."
        ),
        char_start=0,
        char_end=130,
    )

    mentions = facade._build_mentions_for_sentence(sentence)

    assert not any(item.mention_type == "bic_swift" for item in mentions)


def test_build_claim_for_sentence_returns_rule_claim() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content="A Megbízó felhatalmazza az Alkuszt a hírlevél szolgáltatás rögzítésére.",
        char_start=0,
        char_end=74,
    )

    mentions = facade._build_mentions_for_sentence(sentence)
    interpretation, claims = facade._build_claim_for_sentence(sentence, mentions)

    assert interpretation.assertion_mode == "rule"
    assert interpretation.claim_type in {"rule_condition", "relational", "other"}
    assert claims
    assert claims[0].predicate_text.lower() == "felhatalmazza"
    assert interpretation.information_value_score >= 5
    assert interpretation.information_value_status in {"usable", "strong"}


def test_build_claim_for_fragment_sentence_gets_low_information_score() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content="és részére az Alkusz",
        char_start=0,
        char_end=20,
        metadata={"block_type": "paragraph"},
    )

    mentions = facade._build_mentions_for_sentence(sentence)
    interpretation, claims = facade._build_claim_for_sentence(sentence, mentions)

    assert claims
    assert interpretation.information_value_score < 3
    assert interpretation.information_value_status in {"merge_with_previous", "discard_candidate"}


def test_build_claim_for_heading_sentence_returns_context_without_claim() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content="3. Biztosítási események",
        char_start=0,
        char_end=25,
        metadata={"block_type": "heading"},
    )

    mentions = facade._build_mentions_for_sentence(sentence)
    interpretation, claims = facade._build_claim_for_sentence(sentence, mentions)

    assert claims == []
    assert interpretation.assertion_mode == "context_header"
    assert interpretation.claim_type == "context_header"
    assert interpretation.information_value_status == "context_strong"
    assert interpretation.information_value_score >= 6


def test_build_claim_for_metadata_sentence_is_skipped() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content="1. Bevezetés ........ 3",
        char_start=0,
        char_end=22,
        metadata={"block_type": "metadata", "metadata_kind": "table_of_contents"},
    )

    interpretation, claims = facade._build_claim_for_sentence(sentence, [])

    assert claims == []
    assert interpretation.assertion_mode == "ignored_structure"
    assert interpretation.claim_type == "table_of_contents"
    assert interpretation.information_value_status == "discard_candidate"


def test_build_claim_for_sentence_with_header_context_gets_score_bonus() -> None:
    facade = _build_facade()
    sentence = Sentence(
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-2",
        text_content="A szolgáltatás kizárólag írásbeli bejelentéssel kérhető.",
        char_start=0,
        char_end=58,
        metadata={"block_type": "paragraph", "header_context_text": "3. Bejelentés szabályai"},
    )

    mentions = facade._build_mentions_for_sentence(sentence)
    interpretation, claims = facade._build_claim_for_sentence(sentence, mentions)

    assert claims
    assert interpretation.metadata["header_context_text"] == "3. Bejelentés szabályai"
    assert interpretation.information_value_score >= 6


def test_delete_for_corpus_if_table_exists_skips_missing_table() -> None:
    class _MissingTableStore:
        def delete_for_corpus(self, _corpus_uuid: str) -> int:
            raise ProgrammingError(
                "DELETE FROM knowledge_claims WHERE knowledge_claims.corpus_uuid = %(corpus_uuid_1)s",
                {"corpus_uuid_1": "kb-1"},
                Exception('relation "knowledge_claims" does not exist'),
            )

    deleted = KnowledgeFacade._delete_for_corpus_if_table_exists(
        _MissingTableStore(),
        "kb-1",
        table_name="knowledge_claims",
    )

    assert deleted == 0


def test_truncate_error_message_limits_length() -> None:
    message = "x" * 1500

    truncated = KnowledgeFacade._truncate_error_message(message, max_length=1000)

    assert len(truncated) == 1000
    assert truncated.endswith("... [truncated]")


def test_compute_progress_percent_returns_integer_ratio() -> None:
    assert KnowledgeFacade._compute_progress_percent(7, 20) == 35
    assert KnowledgeFacade._compute_progress_percent(20, 20) == 100
    assert KnowledgeFacade._compute_progress_percent(0, 0) is None


def test_update_item_processing_summary_merges_modules_and_document_progress() -> None:
    facade = _build_facade()
    item = IngestItem(id="item-1", progress_message="kezdeti")

    updated = facade._update_item_processing_summary(
        item,
        progress_message="feldolgozás alatt",
        module_updates={
            "parser": facade._build_processing_module(
                key="parser",
                status="processing",
                label="Mondatkinyerés",
                processed_parts=2,
                total_parts=10,
            )
        },
        document_progress=facade._build_document_progress(
            phase="sentence_interpretation",
            processed_parts=2,
            total_parts=10,
            label="2 / 10 mondat kész",
        ),
    )

    summary = updated.metadata["processing_summary"]
    assert updated.progress_message == "feldolgozás alatt"
    assert summary["overall_status"] == "processing"
    assert summary["modules"]["parser"]["progress_percent"] == 20
    assert summary["document_progress"]["label"] == "2 / 10 mondat kész"


def test_refresh_ingest_run_builds_progress_summary_from_item_processing_state() -> None:
    facade = _build_facade()
    run_store = _InMemoryIngestRunStore()
    item_store = _InMemoryIngestItemStore()
    facade._ingest_run_store = run_store
    facade._ingest_item_store = item_store

    run = run_store.create(IngestRun(id="run-1", corpus_uuid="kb-1", status="processing"))
    processing_item = item_store.create(
        IngestItem(
            id="item-1",
            ingest_run_id=run.id,
            corpus_uuid="kb-1",
            queue_order=1,
            display_name="Szerzodes.pdf",
            status="processing",
            progress_message="Mondatok értelmezése folyamatban.",
            metadata={
                "processing_summary": {
                    "modules": {
                        "parser": {"key": "parser", "status": "completed", "label": "Mondatkinyerés", "progress_percent": 100},
                        "sentence_interpretation": {
                            "key": "sentence_interpretation",
                            "status": "processing",
                            "label": "Mondatértelmezés",
                            "progress_percent": 40,
                            "message": "4 / 10 mondat értelmezve.",
                        },
                    },
                    "document_progress": {
                        "phase": "sentence_interpretation",
                        "progress_percent": 40,
                        "label": "4 / 10 mondat kész",
                    },
                }
            },
        )
    )
    item_store.create(
        IngestItem(
            id="item-2",
            ingest_run_id=run.id,
            corpus_uuid="kb-1",
            queue_order=2,
            display_name="Masik.pdf",
            status="completed",
        )
    )

    refreshed = facade._refresh_ingest_run(run.id)

    progress_summary = refreshed.metadata["progress_summary"]
    assert refreshed.status == "processing"
    assert progress_summary["overall_percent"] == 86
    assert progress_summary["active_item_id"] == processing_item.id
    assert progress_summary["active_module"] == "sentence_interpretation"
    assert progress_summary["active_message"] == "4 / 10 mondat értelmezve."


def test_compute_item_progress_percent_estimates_early_parser_phase_above_one_percent() -> None:
    item = IngestItem(
        id="item-parser-early",
        status="processing",
        progress_message="A parser modul fut, a dokumentum szerkezetét készíti elő.",
        metadata={
            "processing_summary": {
                "modules": {
                    "parser": {
                        "key": "parser",
                        "status": "processing",
                        "label": "Mondatkinyerés",
                        "message": "A parser modul fut.",
                    },
                    "sentence_interpretation": {
                        "key": "sentence_interpretation",
                        "status": "queued",
                        "label": "Mondatértelmezés",
                    },
                    "sentence_evaluation": {
                        "key": "sentence_evaluation",
                        "status": "queued",
                        "label": "Mondatértékelés",
                    },
                },
                "document_progress": {
                    "phase": "parser",
                    "processed_parts": 0,
                    "total_parts": None,
                    "progress_percent": None,
                    "label": "A dokumentum előkészítése folyamatban van.",
                },
            }
        },
    )

    assert KnowledgeFacade._compute_item_progress_percent(item) == 30


def test_get_ingest_run_refreshes_stale_processing_status() -> None:
    facade = _build_facade()
    run_store = _InMemoryIngestRunStore()
    item_store = _InMemoryIngestItemStore()
    facade._ingest_run_store = run_store
    facade._ingest_item_store = item_store
    facade._ingest_event_store = _InMemoryIngestEventStore()

    run = run_store.create(IngestRun(id="run-stale", corpus_uuid="kb-1", status="processing"))
    item_store.create(
        IngestItem(
            id="item-stale",
            ingest_run_id=run.id,
            corpus_uuid="kb-1",
            queue_order=1,
            display_name="WABARD_szerzodes.pdf",
            status="completed",
        )
    )

    refreshed = facade.get_ingest_run(run.id)

    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.metadata["progress_summary"]["overall_percent"] == 100


def test_refresh_ingest_run_marks_partial_success_when_mixed_terminal_states() -> None:
    facade = _build_facade()
    run_store = _InMemoryIngestRunStore()
    item_store = _InMemoryIngestItemStore()
    facade._ingest_run_store = run_store
    facade._ingest_item_store = item_store

    run = run_store.create(IngestRun(id="run-partial", corpus_uuid="kb-1", status="processing"))
    item_store.create(
        IngestItem(
            id="item-ok",
            ingest_run_id=run.id,
            corpus_uuid="kb-1",
            queue_order=1,
            display_name="ok.txt",
            status="completed",
        )
    )
    item_store.create(
        IngestItem(
            id="item-failed",
            ingest_run_id=run.id,
            corpus_uuid="kb-1",
            queue_order=2,
            display_name="failed.txt",
            status="failed",
            error_message="parser error",
        )
    )

    refreshed = facade._refresh_ingest_run(run.id)

    assert refreshed.status == "partial_success"
    assert refreshed.completed_count == 1
    assert refreshed.failed_count == 1
    assert refreshed.metadata["progress_summary"]["overall_percent"] == 100


def test_is_stale_parser_processing_detects_half_finished_parse_state() -> None:
    facade = _build_facade()
    parser_run = ParserRun(source_id="source-1", corpus_uuid="kb-1", status="processing")
    document = Document(source_id="source-1", corpus_uuid="kb-1", parser_run_id=parser_run.id, title="doc", language="hu")
    facade._parser_run_store = _NoopStore()
    facade._document_store = _NoopStore()
    facade._paragraph_store = _NoopStore()
    facade._sentence_store = _NoopStore()

    facade._parser_run_store.get_for_source = lambda source_id: parser_run if source_id == "source-1" else None
    facade._document_store.get_for_source = lambda source_id: document if source_id == "source-1" else None

    assert facade._is_stale_parser_processing("source-1", updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc)) is True


def test_interpret_document_skips_missing_interpretation_tables() -> None:
    class _MissingInterpretationRunStore:
        def get_for_document(self, _document_id: str):
            raise ProgrammingError(
                "SELECT * FROM knowledge_interpretation_runs WHERE document_id = %(document_id_1)s",
                {"document_id_1": "doc-1"},
                Exception('relation "knowledge_interpretation_runs" does not exist'),
            )

    facade = _build_facade()
    facade._interpretation_run_store = _MissingInterpretationRunStore()
    facade._sentence_interpretation_store = _NoopStore()
    facade._mention_store = _NoopStore()
    facade._claim_store = _NoopStore()

    result = facade._interpret_document(
        source=facade.create_source(
            tenant="demo",
            corpus_uuid="kb-1",
            title="Pilot source",
            source_type="text",
            raw_content="A Megbízó felhatalmazza az Alkuszt.",
            file_ref=None,
            created_by=11,
        ),
        document=type(
            "_Doc",
            (),
            {"id": "doc-1", "language": "hu"},
        )(),
        sentences=[],
        created_by=11,
    )

    assert result is None


def test_get_sentence_interpretation_falls_back_to_on_the_fly_payload_without_stores() -> None:
    facade = _build_facade()
    sentence = Sentence(
        id="sentence-1",
        corpus_uuid="kb-1",
        source_id="source-1",
        document_id="doc-1",
        paragraph_id="par-1",
        text_content="A Megbízó felhatalmazza az Alkuszt a hírlevél szolgáltatás rögzítésére.",
        char_start=0,
        char_end=74,
    )
    facade._sentence_store = type(
        "_SentenceStore",
        (),
        {
            "get": staticmethod(lambda sentence_id: sentence if sentence_id == "sentence-1" else None),
            "list_for_document": staticmethod(lambda _document_id: [sentence]),
        },
    )()
    facade._sentence_interpretation_store = None
    facade._mention_store = None
    facade._claim_store = None

    detail = facade.get_sentence_interpretation("sentence-1")

    assert detail is not None
    assert detail["interpretation"].sentence_id == "sentence-1"
    assert detail["claims"]


def test_source_download_returns_typed_training_text_as_attachment_payload() -> None:
    facade = _build_facade()
    source = facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="Chatbol tanitott szoveg",
        source_type="text",
        raw_content="The London office is currently inactive.",
        file_ref=None,
        created_by=11,
    )

    download = facade.get_source_download(source.id)

    assert download is not None
    assert download["filename"] == "Chatbol tanitott szoveg.txt"
    assert download["content_type"] == "text/plain; charset=utf-8"
    assert download["body"].decode("utf-8") == "The London office is currently inactive."


@pytest.mark.anyio
async def test_schedule_and_run_index_build_ingests_sources_into_build_collection() -> None:
    vector_index = _VectorIndex()
    facade = _build_facade(vector_index=vector_index)
    source = facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="Pilot source",
        source_type="text",
        raw_content="Ez az elso mondat. Ez a masodik mondat. Ez a harmadik mondat.",
        file_ref=None,
        created_by=11,
    )

    build = facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="basic_chunk_v1",
        created_by=11,
    )
    finished = await facade.run_index_build(build.id)

    assert source.id in {item.id for item in facade.list_sources("kb-1")}
    assert finished.status == "ready"
    assert finished.chunk_count > 0
    assert finished.collection_name in vector_index.collections
    assert vector_index.collections[finished.collection_name]


def test_schedule_index_build_uses_requested_profile_key_and_collection_suffix() -> None:
    facade = _build_facade()

    build = facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="hybrid_v1",
        created_by=11,
    )

    assert build.index_profile_key == "hybrid_v1"
    assert build.collection_name.endswith("__hybrid_v1")


@pytest.mark.anyio
async def test_run_index_build_persists_build_and_profile_metadata_for_vector_rows() -> None:
    vector_index = _VectorIndex()
    facade = _build_facade(vector_index=vector_index)
    facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="Pilot source",
        source_type="text",
        raw_content="Az SK MAX rendszer kezeli a szerzodeseket es workflow-kat.",
        file_ref=None,
        created_by=11,
    )
    facade._load_existing_retrieval_chunks = lambda **_kwargs: [
        {
            "profile_id": "global-profile:sk-max",
            "entity_name": "SK MAX rendszer",
            "entity_type": "system_component",
            "canonical_key": "sk max rendszer",
            "retrieval_chunk_id": "retrieval_chunk:sk-max",
            "retrieval_chunk_text": "SK MAX rendszer workflow tamogatas",
            "structured_facts": {"relations": []},
            "source_ids": ["src-1"],
            "evidence_ids": ["claim-1"],
        }
    ]
    facade._load_existing_semantic_blocks = lambda **_kwargs: [
        {
            "id": "semantic-block-1",
            "corpus_uuid": "kb-1",
            "source_id": "src-1",
            "document_id": "doc-1",
            "claim_ids": ["claim-1"],
            "sentence_ids": ["sentence-1"],
            "primary_subject": "SK MAX rendszer",
            "summary": "Workflow tamogatas",
            "text": "Az SK MAX rendszer workflow folyamatokat tamogat.",
            "time_modes": ["current"],
            "space_modes": ["virtual"],
            "entity_keys": ["sk max rendszer"],
            "metadata": {"block_status": "approved"},
        }
    ]

    build = facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="hybrid_v1",
        created_by=11,
    )
    await facade.run_index_build(build.id)

    assert vector_index.ensure_calls[0] == (build.collection_name, 1024)
    rows = vector_index.collections[build.collection_name]
    assert rows
    assert any((row.get("payload") or {}).get("point_type") == "sentence" for row in rows)
    assert any((row.get("payload") or {}).get("point_type") == "retrieval_chunk" for row in rows)
    assert any((row.get("payload") or {}).get("point_type") == "semantic_block" for row in rows)
    for row in rows:
        payload = row.get("payload") or {}
        assert payload.get("build_id") == build.id
        assert payload.get("index_profile_key") == "hybrid_v1"


@pytest.mark.anyio
async def test_retrieve_creates_query_run_with_context_and_citations() -> None:
    facade = _build_facade()
    facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="Pilot source",
        source_type="text",
        raw_content="A rendszerbeallitasok pilot modban is merhetok es logolhatok.",
        file_ref=None,
        created_by=11,
    )
    build = facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="basic_chunk_v1",
        created_by=11,
    )
    await facade.run_index_build(build.id)

    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="Hogyan merheto a pilot?",
    )

    assert query_run.build_ids == [build.id]
    assert query_run.result_count >= 1
    assert query_run.context_text
    assert len(query_run.citations) >= 1
    assert query_run.metadata["query_profile"]["intent"] == "unknown"
    assert "query_resolution_confidence" in query_run.metadata


@pytest.mark.anyio
async def test_retrieve_stores_query_resolver_trace_metadata() -> None:
    facade = _build_facade()
    facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="London source",
        source_type="text",
        raw_content="The London office is currently active.",
        file_ref=None,
        created_by=11,
    )
    build = facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="basic_chunk_v1",
        created_by=11,
    )
    await facade.run_index_build(build.id)

    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="Was the London office inactive?",
    )

    assert query_run.metadata["query_intent"] == "state"
    assert query_run.metadata["query_detected_entities"] == [
        {"text": "London office", "entity_type": "location", "source": "query_pattern"}
    ]
    assert query_run.metadata["query_filters"] == {
        "entity_type": "location",
        "entity": "London office",
        "state": "inactive",
        "time_filter": "historical",
        "space_filter": "London office",
        "keywords": ["london", "office", "inactive", "state"],
    }
    assert query_run.metadata["query_resolution_confidence"] >= 0.85


@pytest.mark.anyio
async def test_retrieve_stores_query_aware_retrieval_matches() -> None:
    facade = _build_facade()
    facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="London source",
        source_type="text",
        raw_content="The London office is currently active.",
        file_ref=None,
        created_by=11,
    )
    build = facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="basic_chunk_v1",
        created_by=11,
    )
    await facade.run_index_build(build.id)
    facade._load_existing_global_profiles = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "canonical_key": "london office",
            "claims": [
                {"claim_id": "c-active", "subject": "London office", "predicate": "active", "object": "true", "status": "active"},
                {"claim_id": "c-inactive", "subject": "London office", "predicate": "active", "object": "false", "status": "active"},
            ],
        },
        {
            "profile_id": "global-profile:billing-service",
            "entity_name": "billing service",
            "entity_type": "system_component",
            "canonical_key": "billing service",
            "claims": [],
        },
    ]
    facade._load_existing_retrieval_chunks = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "canonical_key": "london office",
            "retrieval_chunk_text": "London office (location)\nConflicting current facts: London office active = true; London office active = false",
            "structured_facts": {
                "active": [
                    {
                        "claim_id": "c-active",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "true",
                        "status": "active",
                        "sentence_ids": ["s-active"],
                        "source_ids": ["src-london"],
                    },
                    {
                        "claim_id": "c-inactive",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "active",
                        "sentence_ids": ["s-inactive"],
                        "source_ids": ["src-london"],
                    },
                ],
                "conflicts": [
                    {
                        "claim_id": "c-active",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "true",
                        "status": "active",
                        "sentence_ids": ["s-active"],
                        "source_ids": ["src-london"],
                    },
                    {
                        "claim_id": "c-inactive",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "active",
                        "sentence_ids": ["s-inactive"],
                        "source_ids": ["src-london"],
                    },
                ],
            },
            "evidence_ids": ["c-active", "s-active", "c-inactive", "s-inactive"],
            "source_ids": ["src-london"],
            "conflicting": True,
        },
        {
            "profile_id": "global-profile:billing-service",
            "entity_name": "billing service",
            "retrieval_chunk_text": "billing service (system_component)",
            "structured_facts": {"active": []},
        },
    ]

    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="Which offices are active?",
    )

    assert query_run.metadata["query_retrieval_match_count"] == 1
    assert query_run.metadata["query_retrieval_filtered_count"] == 1
    assert query_run.metadata["conflict_marker_included"] is True
    assert query_run.metadata["matched_chunks"][0]["entity_name"] == "London office"
    assert {item["claim_id"] for item in query_run.metadata["matched_claims"]} == {"c-active", "c-inactive"}
    assert query_run.metadata["answer_mode"] == "conflict"
    assert "conflicting current status information" in query_run.metadata["answer_text"]
    assert set(query_run.metadata["cited_claim_ids"]) == {"c-active", "c-inactive"}
    assert query_run.metadata["synthesis_confidence"] > 0.0


def test_get_quality_report_uses_latest_global_profiles() -> None:
    facade = _build_facade()
    store = _InMemoryIngestRunStore()
    facade._interpretation_run_store = store
    store.create(
        InterpretationRun(
            id="run-quality",
            corpus_uuid="kb-1",
            status="completed",
            metadata={
                "global_profiles": [
                    {
                        "profile_id": "global-profile:london-office",
                        "entity_name": "London office",
                        "entity_type": "location",
                        "claims": [
                            {
                                "claim_id": "claim-london",
                                "sentence_ids": ["sentence-london"],
                                "source_ids": ["source-london"],
                                "status": "active",
                            }
                        ],
                    },
                    {
                        "profile_id": "global-profile:unknown",
                        "entity_name": "Unknown service",
                        "entity_type": "unknown",
                        "claims": [{"claim_id": "claim-unknown", "status": "active"}],
                    },
                ]
            },
        )
    )

    report = facade.get_quality_report(corpus_uuid="kb-1")

    assert report["total_profiles"] == 2
    assert report["profiles_without_evidence"] == 1
    assert report["metrics"]["coverage"] == 0.5
    assert report["metrics"]["unknown_entity_type_ratio"] == 0.5


@pytest.mark.anyio
async def test_retrieve_can_answer_from_indexed_retrieval_chunk_vector_hit() -> None:
    vector = _VectorIndex()
    facade = _build_facade(vector)
    store = _InMemoryIngestRunStore()
    facade._interpretation_run_store = store
    structured_facts = {
        "current": [
            {
                "claim_id": "claim-london",
                "subject": "London office",
                "predicate": "active",
                "object": "false",
                "status": "active",
                "sentence_ids": ["sentence-london"],
                "source_ids": ["source-london"],
            }
        ],
        "active": [
            {
                "claim_id": "claim-london",
                "subject": "London office",
                "predicate": "active",
                "object": "false",
                "status": "active",
                "sentence_ids": ["sentence-london"],
                "source_ids": ["source-london"],
            }
        ],
    }
    store.create(
        InterpretationRun(
            id="run-vector-chunk",
            corpus_uuid="kb-1",
            status="completed",
            metadata={
                "global_profiles": [
                    {
                        "profile_id": "global-profile:london-office",
                        "entity_name": "London office",
                        "entity_type": "location",
                        "canonical_key": "london office",
                        "claims": structured_facts["current"],
                    }
                ],
                "retrieval_chunks": [
                    {
                        "profile_id": "global-profile:london-office",
                        "entity_name": "London office",
                        "entity_type": "location",
                        "canonical_key": "london office",
                        "retrieval_chunk_text": "London office (location)\nCurrent facts:\n- currently inactive",
                        "structured_facts": structured_facts,
                        "evidence_ids": ["claim-london", "sentence-london"],
                        "source_ids": ["source-london"],
                    }
                ],
            },
        )
    )
    build = facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="hybrid_v1",
        created_by=11,
    )
    await facade.run_index_build(build.id)

    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
    )

    assert query_run.metadata["answer_text"] == "The London office is currently inactive."
    assert query_run.metadata["answer_mode"] == "direct"
    assert query_run.metadata["matched_chunks"][0]["profile_id"] == "global-profile:london-office"
    assert any((row["payload"] or {}).get("point_type") == "retrieval_chunk" for row in vector.collections[build.collection_name])


@pytest.mark.anyio
async def test_retrieve_synthesizes_status_answer_with_historical_context() -> None:
    facade = _build_facade()
    facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="London source",
        source_type="text",
        raw_content="The London office is currently inactive.",
        file_ref=None,
        created_by=11,
    )
    build = facade.schedule_index_build(
        tenant="demo",
        corpus_uuid="kb-1",
        index_profile_key="basic_chunk_v1",
        created_by=11,
    )
    await facade.run_index_build(build.id)
    facade._load_existing_global_profiles = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "canonical_key": "london office",
            "claims": [],
        }
    ]
    facade._load_existing_retrieval_chunks = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "canonical_key": "london office",
            "retrieval_chunk_text": "London office (location)\nCurrent facts:\n- currently inactive\nHistorical facts:\n- inactive in 2024",
            "structured_facts": {
                "current": [
                    {
                        "claim_id": "c-current",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "active",
                        "time_mode": "current",
                        "sentence_ids": ["s-current"],
                        "source_ids": ["src-london"],
                    }
                ],
                "historical": [
                    {
                        "claim_id": "c-2024",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "historical",
                        "time_mode": "bounded",
                        "time_values": ["2024"],
                        "sentence_ids": ["s-2024"],
                        "source_ids": ["src-london"],
                    }
                ],
            },
            "evidence_ids": ["e-current", "s-current", "e-2024", "s-2024"],
            "source_ids": ["src-london"],
            "conflicting": False,
            "temporal_context_included": True,
        }
    ]

    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
    )

    assert query_run.metadata["answer_text"] == "The London office is currently inactive. Historically, it was inactive in 2024."
    assert query_run.metadata["answer_mode"] == "state_with_history"
    assert query_run.metadata["cited_claim_ids"] == ["c-current", "c-2024"]
    assert query_run.metadata["cited_evidence_ids"] == ["c-current", "c-2024", "s-current", "s-2024", "e-current", "e-2024"]
    assert query_run.metadata["query_debug"]["matched_chunks_count"] == 1
    assert query_run.metadata["query_debug"]["matched_claims_count"] == 2
    assert query_run.metadata["query_debug"]["synthesis_called"] is True
    assert query_run.metadata["query_debug"]["answer_text"] == query_run.metadata["answer_text"]
    assert "temporal_answer_context" not in query_run.metadata


@pytest.mark.anyio
async def test_retrieve_without_ready_index_build_still_runs_query_aware_synthesis() -> None:
    facade = _build_facade()
    facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="London source",
        source_type="text",
        raw_content="The London office is currently inactive.",
        file_ref=None,
        created_by=11,
    )
    facade._load_existing_global_profiles = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "canonical_key": "london office",
            "claims": [],
        }
    ]
    facade._load_existing_retrieval_chunks = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "canonical_key": "london office",
            "retrieval_chunk_text": "London office (location)\nCurrent facts:\n- currently inactive",
            "structured_facts": {
                "current": [
                    {
                        "claim_id": "c-current",
                        "subject": "London office",
                        "predicate": "active",
                        "object": "false",
                        "status": "active",
                        "time_mode": "current",
                        "sentence_ids": ["s-current"],
                        "source_ids": ["src-london"],
                    }
                ],
            },
            "evidence_ids": ["c-current", "s-current"],
            "source_ids": ["src-london"],
            "conflicting": False,
        }
    ]

    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
    )

    assert query_run.build_ids == []
    assert query_run.metadata["no_ready_index_build"] is True
    assert query_run.metadata["query_debug"]["no_ready_index_build"] is True
    assert query_run.metadata["answer_text"] == "The London office is currently inactive."


@pytest.mark.anyio
async def test_retrieve_accepts_completed_index_status_as_ready() -> None:
    facade = _build_facade()
    completed_build = facade._index_build_store.create(  # noqa: SLF001 - unit test inspects facade internals
        IndexBuild(
            tenant="demo",
            corpus_uuid="kb-1",
            index_profile_key="basic_chunk_v1",
            status="completed",  # type: ignore[arg-type]
            collection_name="kb_1__basic_chunk_v1",
        )
    )

    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
    )

    assert query_run.build_ids == [completed_build.id]
    assert query_run.metadata["no_ready_index_build"] is False
    assert query_run.metadata["query_debug"]["no_ready_index_build"] is False


@pytest.mark.anyio
async def test_feedback_replace_updates_next_query_answer() -> None:
    facade = _build_facade()
    facade._load_existing_global_profiles = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "canonical_key": "london office",
            "claims": [
                {
                    "claim_id": "c-inactive",
                    "subject": "London office",
                    "predicate": "active",
                    "object": "false",
                    "status": "active",
                    "time_mode": "current",
                    "sentence_ids": ["s-inactive"],
                    "source_ids": ["src-london"],
                }
            ],
        }
    ]
    facade._load_existing_retrieval_chunks = lambda **_kwargs: []

    feedback = facade.apply_knowledge_feedback(
        tenant="demo",
        corpus_uuid="kb-1",
        target_entity="London office",
        claim_text="London office is currently inactive",
        feedback_type="replace",
        optional_new_claim="London office is currently active",
        user_input="This is wrong -> London office is active",
        user_id=11,
    )
    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
    )

    event = feedback["feedback_event"]
    assert event["affected_claim_ids"] == ["c-inactive"]
    assert event["new_claim_ids"]
    assert query_run.metadata["answer_text"] == "The London office is currently active."
    assert query_run.metadata["answer_mode"] == "direct"
    assert query_run.metadata["feedback_events"][0]["user_input"] == "This is wrong -> London office is active"
    assert query_run.metadata["cited_claim_ids"] == event["new_claim_ids"]


@pytest.mark.anyio
async def test_feedback_incorrect_weakened_claim_is_not_primary_fact() -> None:
    facade = _build_facade()
    facade._load_existing_global_profiles = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "canonical_key": "london office",
            "claims": [
                {
                    "claim_id": "c-active",
                    "subject": "London office",
                    "predicate": "active",
                    "object": "true",
                    "status": "active",
                    "time_mode": "current",
                    "sentence_ids": ["s-active"],
                    "source_ids": ["src-london"],
                }
            ],
        }
    ]
    facade._load_existing_retrieval_chunks = lambda **_kwargs: []

    facade.apply_knowledge_feedback(
        tenant="demo",
        corpus_uuid="kb-1",
        target_entity="London office",
        claim_text="London office is currently active",
        feedback_type="incorrect",
        user_input="This is wrong",
        user_id=11,
    )
    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
    )

    assert query_run.metadata["answer_mode"] == "no_answer"
    assert query_run.metadata["matched_claims"] == []


@pytest.mark.anyio
async def test_withdraw_source_removes_claim_from_next_query() -> None:
    facade = _build_facade()
    source = facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="London source",
        source_type="text",
        raw_content="The London office is currently inactive.",
        file_ref=None,
        created_by=11,
    )
    facade._load_existing_global_profiles = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "canonical_key": "london office",
            "claims": [
                {
                    "claim_id": "c-inactive",
                    "subject": "London office",
                    "predicate": "active",
                    "object": "false",
                    "status": "active",
                    "time_mode": "current",
                    "sentence_ids": ["s-inactive"],
                    "source_ids": [source.id],
                    "evidence": {"source_id": source.id, "source_ids": [source.id], "sentence_ids": ["s-inactive"]},
                }
            ],
        }
    ]
    facade._load_existing_retrieval_chunks = lambda **_kwargs: []

    withdrawal = facade.withdraw_source(
        tenant="demo",
        corpus_uuid="kb-1",
        source_id=source.id,
        user_input="withdraw_source",
        user_id=11,
    )
    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
    )

    event = withdrawal["source_withdrawal_event"]
    assert event["affected_claim_ids"] == ["c-inactive"]
    assert query_run.metadata["answer_mode"] == "no_answer"
    assert query_run.metadata["matched_claims"] == []
    assert query_run.metadata["source_withdrawal_events"][0]["source_id"] == source.id
    assert facade.list_sources("kb-1")[0].metadata["withdrawn"] is True


@pytest.mark.anyio
async def test_withdraw_source_keeps_other_source_evidence_active() -> None:
    facade = _build_facade()
    withdrawn_source = facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="Withdrawn London source",
        source_type="text",
        raw_content="The London office is currently inactive.",
        file_ref=None,
        created_by=11,
    )
    active_source = facade.create_source(
        tenant="demo",
        corpus_uuid="kb-1",
        title="Active London source",
        source_type="text",
        raw_content="The London office is currently active.",
        file_ref=None,
        created_by=11,
    )
    facade._load_existing_global_profiles = lambda **_kwargs: [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "canonical_key": "london office",
            "claims": [
                {
                    "claim_id": "c-inactive",
                    "subject": "London office",
                    "predicate": "active",
                    "object": "false",
                    "status": "active",
                    "time_mode": "current",
                    "sentence_ids": ["s-inactive"],
                    "source_ids": [withdrawn_source.id],
                    "evidence": {"source_id": withdrawn_source.id, "source_ids": [withdrawn_source.id], "sentence_ids": ["s-inactive"]},
                },
                {
                    "claim_id": "c-active",
                    "subject": "London office",
                    "predicate": "active",
                    "object": "true",
                    "status": "active",
                    "time_mode": "current",
                    "sentence_ids": ["s-active"],
                    "source_ids": [active_source.id],
                    "evidence": {"source_id": active_source.id, "source_ids": [active_source.id], "sentence_ids": ["s-active"]},
                },
            ],
        }
    ]
    facade._load_existing_retrieval_chunks = lambda **_kwargs: []

    facade.withdraw_source(
        tenant="demo",
        corpus_uuid="kb-1",
        source_id=withdrawn_source.id,
        user_input="withdraw old London source",
        user_id=11,
    )
    query_run = await facade.retrieve(
        tenant="demo",
        corpus_uuid="kb-1",
        query="What is the status of London office?",
    )

    assert query_run.metadata["answer_text"] == "The London office is currently active."
    assert query_run.metadata["answer_mode"] == "direct"
    assert query_run.metadata["cited_claim_ids"] == ["c-active"]
    assert [item["claim_id"] for item in query_run.metadata["matched_claims"]] == ["c-active"]
