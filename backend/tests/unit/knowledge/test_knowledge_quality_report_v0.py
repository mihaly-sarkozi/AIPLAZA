from apps.knowledge.service.knowledge_quality_report_v0 import KnowledgeQualityReportV0


def test_quality_report_calculates_coverage_conflicts_and_evidence_density() -> None:
    report = KnowledgeQualityReportV0().build(
        corpus_uuid="kb-1",
        global_profiles=[
            {
                "profile_id": "profile-active",
                "entity_name": "London office",
                "entity_type": "location",
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "sentence_ids": ["sentence-1"],
                        "source_ids": ["source-1"],
                        "status": "active",
                    }
                ],
            },
            {
                "profile_id": "profile-conflict",
                "entity_name": "billing service",
                "entity_type": "software",
                "conflicting": True,
                "claims": [
                    {
                        "claim_id": "claim-2",
                        "sentence_ids": ["sentence-2"],
                        "source_ids": ["source-2"],
                        "status": "disputed",
                    },
                    {
                        "claim_id": "claim-3",
                        "sentence_ids": ["sentence-3"],
                        "source_ids": ["source-3"],
                        "status": "active",
                    },
                ],
            },
            {
                "profile_id": "profile-unknown",
                "entity_name": "mystery thing",
                "entity_type": "unknown",
                "claims": [{"claim_id": "claim-4", "status": "active"}],
            },
        ],
    )

    assert report["total_profiles"] == 3
    assert report["profiles_with_conflict"] == 1
    assert report["profiles_without_evidence"] == 1
    assert report["avg_claims_per_profile"] == 1.3333
    assert report["metrics"]["coverage"] == 0.6667
    assert report["metrics"]["conflict_ratio"] == 0.3333
    assert report["metrics"]["freshness"] == 1.0
    assert report["metrics"]["evidence_density"] == 0.75
    assert report["metrics"]["unknown_entity_type_ratio"] == 0.3333


def test_quality_report_handles_empty_corpus() -> None:
    report = KnowledgeQualityReportV0().build(corpus_uuid="kb-empty", global_profiles=[])

    assert report["total_profiles"] == 0
    assert report["profiles_with_conflict"] == 0
    assert report["profiles_without_evidence"] == 0
    assert report["avg_claims_per_profile"] == 0.0
    assert report["metrics"] == {
        "coverage": 0.0,
        "conflict_ratio": 0.0,
        "freshness": 0.0,
        "evidence_density": 0.0,
        "unknown_entity_type_ratio": 0.0,
    }
