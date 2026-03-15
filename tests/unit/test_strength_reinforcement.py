from __future__ import annotations

import pytest

from apps.knowledge.application.scoring import reinforce_strength

pytestmark = pytest.mark.unit


def test_strength_reinforcement_moves_up():
    out = reinforce_strength(old_strength=0.2, alpha=0.35, baseline_strength=0.05)
    assert out > 0.2
    assert out <= 1.0
