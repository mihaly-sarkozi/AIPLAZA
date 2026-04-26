from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class DevAppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    app_name: str = "BrainBankCenter.com"
    app_description: str = "API dokumentáció – auth, users, settings, chat, knowledge base."
    app_version: str = "1.0"

    openai_api_key: str = ""
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    object_storage_enabled: bool = True
    object_storage_provider: str = "s3_compatible"
    object_storage_endpoint: str = "http://localhost:39000"
    object_storage_region: str = "us-east-1"
    object_storage_access_key: str = "minioadmin"
    object_storage_secret_key: str = "minioadmin"
    object_storage_bucket: str = "test-bucket-aiplaza"
    object_storage_secure: bool = False
    object_storage_force_path_style: bool = True
    
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    kb_upload_max_mb: int = 40
    kb_store_raw_content: bool = False
    pii_encryption_key: str = ""
    pii_retention_days: int = 90
    pii_allow_legacy_plaintext_read: bool = True

    rerank_semantic_match_weight: float = 0.22
    rerank_entity_match_weight: float = 0.20
    rerank_lexical_match_weight: float = 0.08
    rerank_time_match_weight: float = 0.16
    rerank_place_match_weight: float = 0.08
    rerank_graph_proximity_weight: float = 0.10
    rerank_strength_weight: float = 0.10
    rerank_confidence_weight: float = 0.10
    rerank_recency_weight: float = 0.04
    rerank_status_weight: float = 1.0
    rerank_relation_confidence_weight: float = 0.06

    qdrant_fusion_semantic_weight: float = 0.72
    qdrant_fusion_lexical_weight: float = 0.28
    qdrant_lexical_overlap_weight: float = 0.72
    qdrant_lexical_substring_weight: float = 0.28
    qdrant_timeout_sec: int = 120

    kb_max_seed_assertions: int = 8
    kb_max_expanded_assertions: int = 12
    kb_max_relation_hops: int = 2
    kb_min_confidence: float = 0.20
    kb_min_current_strength: float = 0.03
    kb_context_token_budget: int = 2200
    kb_context_max_evidence_per_assertion: int = 2
    kb_context_max_key_assertions: int = 8
    kb_context_max_supporting_assertions: int = 10
    kb_context_max_source_chunks: int = 3
    kb_context_include_conflicts: bool = True
    kb_context_include_superseded: bool = False

    kb_debug_trace_persist: bool = True
    kb_debug_trace_path: str = "logs/retrieval_traces.jsonl"
