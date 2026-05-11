from __future__ import annotations

import pytest

from apps.chat.channel_access import ChannelAccessRepository

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_widget_origin_normalization_defaults_to_https() -> None:
    normalized = ChannelAccessRepository._normalize_widget_origin("pelda.hu")
    assert normalized == "https://pelda.hu"


def test_widget_origin_wildcard_rejected() -> None:
    with pytest.raises(ValueError):
        ChannelAccessRepository._normalize_widget_origin("https://*.pelda.hu")


def test_origin_value_requires_scheme_and_host() -> None:
    assert ChannelAccessRepository._origin_value("https://www.pelda.hu/path?q=1") == "https://www.pelda.hu"
    assert ChannelAccessRepository._origin_value("not-a-url") == ""


