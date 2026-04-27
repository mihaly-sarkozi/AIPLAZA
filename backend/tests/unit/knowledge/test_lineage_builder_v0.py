from apps.knowledge.service.lineage_builder_v0 import LineageBuilderV0


def test_lineage_builder_links_source_sentence_claim_profile_and_chunk() -> None:
    global_profiles = [
        {
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
            "entity_type": "location",
            "claims": [
                {
                    "claim_id": "claim-1",
                    "claim_text": "The London office is currently inactive.",
                    "sentence_ids": ["sentence-1"],
                    "source_ids": ["source-1"],
                    "evidence": {
                        "sentence_ids": ["sentence-1"],
                        "source_ids": ["source-1"],
                    },
                }
            ],
        }
    ]
    retrieval_chunks = [
        {
            "retrieval_chunk_id": "retrieval_chunk:global-profile:london-office",
            "profile_id": "global-profile:london-office",
            "entity_name": "London office",
        }
    ]

    builder = LineageBuilderV0()
    graph = builder.build(global_profiles=global_profiles, retrieval_chunks=retrieval_chunks)
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert nodes["source:source-1"]["child_ids"] == ["sentence:sentence-1"]
    assert nodes["sentence:sentence-1"]["parent_ids"] == ["source:source-1"]
    assert nodes["sentence:sentence-1"]["child_ids"] == ["claim:claim-1"]
    assert nodes["claim:claim-1"]["parent_ids"] == ["sentence:sentence-1"]
    assert "retrieval_chunk:global-profile:london-office" in nodes["global-profile:london-office"]["child_ids"]


def test_lineage_builder_focuses_claim_and_profile_debug_views() -> None:
    builder = LineageBuilderV0()
    graph = builder.build(
        global_profiles=[
            {
                "profile_id": "global-profile:admin-user",
                "entity_name": "admin user",
                "claims": [
                    {
                        "claim_id": "claim-admin-rule",
                        "claim_text": "admin user must enable two-factor authentication",
                        "sentence_ids": ["sentence-admin"],
                        "source_ids": ["source-admin"],
                    }
                ],
            }
        ],
        retrieval_chunks=[
            {
                "retrieval_chunk_id": "retrieval_chunk:global-profile:admin-user",
                "profile_id": "global-profile:admin-user",
            }
        ],
    )

    claim_focus = builder.focus(graph, target_type="claim", target_id="claim-admin-rule")
    profile_focus = builder.focus(graph, target_type="global_profile", target_id="global-profile:admin-user")

    assert claim_focus["found"] is True
    assert claim_focus["debug"]["Claim"] == ["admin user must enable two-factor authentication"]
    assert claim_focus["debug"]["Source"] == ["source-admin"]
    assert profile_focus["found"] is True
    assert profile_focus["debug"]["Claims"] == ["admin user must enable two-factor authentication"]
    assert profile_focus["debug"]["Sources"] == ["source-admin"]
