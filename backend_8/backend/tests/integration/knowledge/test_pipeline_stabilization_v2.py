from __future__ import annotations

import pytest

from tests.integration.knowledge.test_pipeline_regression_v1 import (
    PipelineRegressionHarnessV1,
    _entity_has_empty_predicate_fact,
    _entity_profile_contains,
    _entity_type_for_name,
    _has_admin_candidate_or_similarity_link,
    _has_duplicate_candidate_per_profile,
    _has_entity,
    _has_entity_containing,
    _london_berlin_similarity_is_low,
)


pytestmark = [pytest.mark.integration]


MIXED_STABILIZATION_TEXT_V2 = """Nagy Eszter a Zalka 2000 adatvédelmi felelőse.
Korábban a belső incidenskezelési folyamatért felelt.

A Budapesti iroda jelenleg aktív támogatási központ.
A billing service jelenleg Stripe rendszert használ kártyás fizetésekhez.

The London office is currently inactive.
It was active before January 2025.
The Berlin office is currently inactive.
It was active before February 2025.

Az admin felhasználónak kötelező kétfaktoros azonosítást használnia.
The admin user must enable two-factor authentication.
El usuario administrador debe activar la autenticación de dos factores.

A régi Helpdesk import 2024-ben megszűnt.
The legacy helpdesk import was deprecated in 2024.

The account was created in March 2025.
Fue actualizada en abril de 2026.
Later, the account was updated in April 2026.

Ez csak zaj, nem kell belőle fontos claim.
Csak claim extraction / sanitizer javítás kell.
Teszteljük, hogy működik-e.
Ignore this line.
"""


def test_pipeline_stabilization_v2_mixed_text_trace() -> None:
    trace = PipelineRegressionHarnessV1().run_text(MIXED_STABILIZATION_TEXT_V2)
    summary = dict(trace.get("summary") or {})
    quality = dict(summary.get("quality") or {})

    assert int(quality.get("noise_sentence_skipped_count") or 0) >= 3
    assert int(summary.get("context_carryover_applied_count") or 0) >= 1
    assert int(summary.get("context_carryover_blocked_count") or 0) >= 1

    assert _has_entity(trace, "Nagy Eszter")
    assert _has_entity(trace, "billing service")
    assert not _has_entity_containing(trace, "Later, the account")
    assert not _has_entity_containing(trace, "Ignore this line")
    assert not _entity_profile_contains(trace, "Budapesti iroda", "használ", "kártyás fizetésekhez")

    assert _entity_type_for_name(trace, "régi Helpdesk import") != "unknown"
    assert _entity_type_for_name(trace, "legacy helpdesk import") != "unknown"

    assert not _has_duplicate_candidate_per_profile(trace)
    assert _london_berlin_similarity_is_low(trace)
    assert _has_admin_candidate_or_similarity_link(trace)

    assert not _entity_has_empty_predicate_fact(trace, "cuenta", "Fue")
