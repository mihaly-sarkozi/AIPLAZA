from __future__ import annotations

import pytest

from apps.knowledge.application.scoring import compute_confidence, decay_strength, reinforce_strength

pytestmark = pytest.mark.unit


def test_compute_confidence_increases_with_evidence():
    low = compute_confidence(0.6, 0.8, evidence_count=1, source_diversity=1)
    high = compute_confidence(0.6, 0.8, evidence_count=4, source_diversity=2)
    assert high > low
    assert 0.0 <= low <= 1.0
    assert 0.0 <= high <= 1.0


def test_decay_strength_never_below_baseline():
    decayed = decay_strength(current_strength=0.7, baseline_strength=0.05, decay_rate=0.02, delta_days=365.0)
    assert decayed >= 0.05
    assert decayed < 0.7


def test_reinforcement_moves_towards_one():
    updated = reinforce_strength(old_strength=0.2, alpha=0.35, baseline_strength=0.05)
    assert updated > 0.2
    assert updated <= 1.0
