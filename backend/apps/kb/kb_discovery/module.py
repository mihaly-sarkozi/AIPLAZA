from __future__ import annotations


class KbDiscoveryModule:
    name = "kb.discovery"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        from apps.kb.kb_discovery.bootstrap.service_keys import (
            KB_DISCOVERY_ENTITY_REPOSITORY,
            KB_DISCOVERY_JOB_REPOSITORY,
            KB_DISCOVERY_KEYWORD_REPOSITORY,
            KB_DISCOVERY_MENTION_REPOSITORY,
            KB_DISCOVERY_RELATIONSHIP_REPOSITORY,
            KB_DISCOVERY_SCORE_REPOSITORY,
            KB_DISCOVERY_SPATIAL_REPOSITORY,
            KB_DISCOVERY_TEMPORAL_REPOSITORY,
            KB_DISCOVERY_TOPIC_REPOSITORY,
        )
        from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
        from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository
        from apps.kb.kb_discovery.repository.KeywordRepository import KeywordRepository
        from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository
        from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
        from apps.kb.kb_discovery.repository.SpatialRepository import SpatialRepository
        from apps.kb.kb_discovery.repository.TemporalRepository import TemporalRepository
        from apps.kb.kb_discovery.repository.TopicRepository import TopicRepository

        sf = container.session_factory
        container.register_repository(KB_DISCOVERY_JOB_REPOSITORY, DiscoveryJobRepository(sf))
        container.register_repository(KB_DISCOVERY_ENTITY_REPOSITORY, EntityRepository(sf))
        container.register_repository(KB_DISCOVERY_MENTION_REPOSITORY, EntityMentionRepository(sf))
        container.register_repository(KB_DISCOVERY_KEYWORD_REPOSITORY, KeywordRepository(sf))
        container.register_repository(KB_DISCOVERY_TOPIC_REPOSITORY, TopicRepository(sf))
        container.register_repository(KB_DISCOVERY_TEMPORAL_REPOSITORY, TemporalRepository(sf))
        container.register_repository(KB_DISCOVERY_SPATIAL_REPOSITORY, SpatialRepository(sf))
        container.register_repository(KB_DISCOVERY_RELATIONSHIP_REPOSITORY, RelationshipRepository(sf))
        container.register_repository(KB_DISCOVERY_SCORE_REPOSITORY, ScoreRepository(sf))

    def register_event_handlers(self, event_bus) -> None:
        # Event handlers: apps/kb/events.py (canonical wiring)
        pass


__all__ = ["KbDiscoveryModule"]
