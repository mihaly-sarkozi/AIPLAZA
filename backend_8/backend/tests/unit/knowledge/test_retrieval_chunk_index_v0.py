from apps.knowledge.service.retrieval_chunk_index_v0 import build_retrieval_chunk_index_rows


def test_retrieval_chunk_index_rows_use_profile_id_and_payload_filters() -> None:
    rows = build_retrieval_chunk_index_rows(
        [
            {
                "profile_id": "global-profile:london-office",
                "retrieval_chunk_id": "retrieval_chunk:global-profile:london-office",
                "entity_name": "London office",
                "entity_type": "location",
                "canonical_key": "london office",
                "retrieval_chunk_text": "London office (location)\nCurrent facts:\n- currently inactive",
                "structured_facts": {
                    "current": [
                        {
                            "claim_id": "claim-london",
                            "claim_group": "state",
                            "claim_type": "state",
                            "predicate": "active",
                            "object": "false",
                            "time_mode": "current",
                        }
                    ]
                },
                "evidence_ids": ["claim-london", "sentence-london"],
                "source_ids": ["source-london"],
            }
        ],
        build_id="build-1",
        index_profile_key="hybrid_v1",
    )

    assert rows == [
        {
            "id": "global-profile:london-office",
            "text": "London office (location)\nCurrent facts:\n- currently inactive",
            "payload": {
                "profile_id": "global-profile:london-office",
                "entity_name": "London office",
                "entity_type": "location",
                "canonical_key": "london office",
                "claim_types": ["state", "current"],
                "states": ["inactive"],
                "time_modes": ["current"],
                "metadata": {
                    "profile_id": "global-profile:london-office",
                    "canonical_key": "london office",
                    "retrieval_chunk_id": "retrieval_chunk:global-profile:london-office",
                    "retrieval_chunk_text": "London office (location)\nCurrent facts:\n- currently inactive",
                    "structured_facts": {
                        "current": [
                            {
                                "claim_id": "claim-london",
                                "claim_group": "state",
                                "claim_type": "state",
                                "predicate": "active",
                                "object": "false",
                                "time_mode": "current",
                            }
                        ]
                    },
                    "evidence_ids": ["claim-london", "sentence-london"],
                    "source_ids": ["source-london"],
                    "conflicting": False,
                    "temporal_context_included": False,
                },
                "text": "London office (location)\nCurrent facts:\n- currently inactive",
                "build_id": "build-1",
                "index_profile_key": "hybrid_v1",
            },
        }
    ]
