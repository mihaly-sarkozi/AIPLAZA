"""
Legacy PII entity names and sensitivity sets. Source of truth: pii_gdpr.entity_registry.

This module re-exports sensitivity sets and implemented/partial/not_yet sets from the
canonical entity registry. Do not edit the sets here; edit apps.knowledge.pii_gdpr.entity_registry.
"""
from __future__ import annotations

from typing import Set

from apps.knowledge.pii_gdpr.entity_registry import (
    ENTITY_REGISTRY,
    ImplementationStatus,
    get_sensitivity_set,
)
from apps.knowledge.pii_gdpr.enums import EntityType

# Sensitivity sets: which legacy types are in scope for weak / medium / strong
WEAK_ENTITIES: Set[str] = set(get_sensitivity_set("weak"))
MEDIUM_ENTITIES: Set[str] = set(get_sensitivity_set("medium"))
STRONG_ENTITIES: Set[str] = set(get_sensitivity_set("strong"))

# Implemented: has detector and is in pipeline; legacy name present
IMPLEMENTED_LEGACY_NAMES: frozenset[str] = frozenset(
    legacy for _et, status, legacy, _sens, _note in ENTITY_REGISTRY
    if status == ImplementationStatus.IMPLEMENTED and legacy
)

# Partially implemented: format/language/context limited
PARTIAL_LEGACY_NAMES: frozenset[str] = frozenset(
    legacy for _et, status, legacy, _sens, _note in ENTITY_REGISTRY
    if status == ImplementationStatus.PARTIALLY_IMPLEMENTED and legacy
)

# Not implemented: no detector or placeholder only
NOT_YET_LEGACY_NAMES: frozenset[str] = frozenset(
    legacy for _et, status, legacy, _sens, _note in ENTITY_REGISTRY
    if status == ImplementationStatus.NOT_IMPLEMENTED and legacy
) | frozenset({"felhasználónév", "becenév", "gps"})  # documented backlog

SUPPORTED_LEGACY_NAMES: frozenset[str] = IMPLEMENTED_LEGACY_NAMES
