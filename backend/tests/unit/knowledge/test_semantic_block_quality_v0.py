from apps.knowledge.service.semantic_block_quality_v0 import enrich_semantic_blocks_with_quality


def test_semantic_block_quality_marks_same_context_different_assertions_as_disputed() -> None:
    blocks = enrich_semantic_blocks_with_quality(
        [
            {
                "id": "new-block",
                "subject_key": "sk max rendszer",
                "space_key": "",
                "time_key": "current",
                "primary_subject": "SK MAX rendszer",
                "predicates": ["kezeli a szerződéseket"],
                "text": "Az SK MAX kezeli a szerződéseket.",
                "confidence": 0.9,
                "metadata": {},
            }
        ],
        existing_blocks=[
            {
                "id": "old-block",
                "subject_key": "sk max rendszer",
                "space_key": "",
                "time_key": "current",
                "primary_subject": "SK MAX rendszer",
                "predicates": ["nem kezeli a szerződéseket"],
                "text": "Az SK MAX nem kezeli a szerződéseket.",
            }
        ],
        source_type="file",
    )

    block = blocks[0]
    assert block["block_status"] == "disputed"
    assert block["conflict_count"] == 1
    assert block["conflicts"][0]["block_id"] == "old-block"
    assert block["retrieval_weight"] < 1.0
    assert block["metadata"]["block_quality"]["active_for_retrieval"] is True


def test_semantic_block_quality_respects_manual_withdrawn_status() -> None:
    blocks = enrich_semantic_blocks_with_quality(
        [
            {
                "id": "block-1",
                "subject_key": "sk max rendszer",
                "time_key": "current",
                "predicates": ["riportot készít"],
                "text": "Riportot készít.",
                "confidence": 0.8,
                "metadata": {"block_status": "withdrawn"},
            }
        ],
        source_type="file",
    )

    assert blocks[0]["block_status"] == "withdrawn"
    assert blocks[0]["retrieval_weight"] == 0.0
    assert blocks[0]["metadata"]["block_quality"]["active_for_retrieval"] is False
