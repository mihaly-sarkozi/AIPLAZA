from __future__ import annotations

import base64
from typing import Any


def sanitize_s3_metadata_value(value: Any) -> str:
    text = str(value)
    try:
        text.encode("ascii")
        return text
    except UnicodeEncodeError:
        encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")
        return f"b64url:{encoded}"


def sanitize_s3_metadata(metadata: dict[str, Any]) -> dict[str, str]:
    return {str(key): sanitize_s3_metadata_value(value) for key, value in metadata.items()}


__all__ = ["sanitize_s3_metadata", "sanitize_s3_metadata_value"]
