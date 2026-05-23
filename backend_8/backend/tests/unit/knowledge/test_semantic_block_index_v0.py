from apps.knowledge.service.semantic_block_index_v0 import build_semantic_block_index_rows


def test_semantic_block_index_rows_use_block_id_and_context_payload() -> None:
    rows = build_semantic_block_index_rows(
        [
            {
                "id": "block-1",
                "corpus_uuid": "kb-1",
                "source_id": "source-1",
                "document_id": "doc-1",
                "sentence_ids": ["s1", "s2"],
                "claim_ids": ["c1", "c2"],
                "primary_subject": "SK MAX rendszer",
                "subject_key": "sk max rendszer",
                "primary_space": "",
                "primary_time": "jelenlegi",
                "time_modes": ["current"],
                "predicates": ["kezeli a szerződéseket", "figyeli a lejáratokat"],
                "text": "Az SK MAX rendszer kezeli a szerződéseket és figyeli a lejáratokat.",
                "summary": "SK MAX rendszer működése",
            }
        ],
        build_id="build-1",
        index_profile_key="hybrid_v1",
    )

    assert rows[0]["id"] == "block-1"
    assert "Alany: SK MAX rendszer" in rows[0]["text"]
    assert "Állítások: kezeli a szerződéseket, figyeli a lejáratokat" in rows[0]["text"]
    assert rows[0]["payload"]["block_id"] == "block-1"
    assert rows[0]["payload"]["subject_key"] == "sk max rendszer"
    assert rows[0]["payload"]["time_modes"] == ["current"]
    assert rows[0]["payload"]["claim_ids"] == ["c1", "c2"]
    assert rows[0]["payload"]["metadata"]["sentence_ids"] == ["s1", "s2"]
