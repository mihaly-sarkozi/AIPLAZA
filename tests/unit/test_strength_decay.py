from __future__ import annotations

import pytest

from apps.knowledge.application.scoring import decay_strength

pytestmark = pytest.mark.unit


def test_strength_decay_never_drops_below_baseline():
    out = decay_strength(current_strength=0.2, baseline_strength=0.05, decay_rate=0.015, delta_days=10_000)
    assert out >= 0.05
