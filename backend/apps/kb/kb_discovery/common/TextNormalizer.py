from __future__ import annotations

import re
import unicodedata


class TextNormalizer:
    _WS = re.compile(r"\s+")

    def normalize(self, text: str) -> str:
        lowered = unicodedata.normalize("NFKC", text).lower().strip()
        return self._WS.sub(" ", lowered)

    def normalize_token(self, token: str) -> str:
        return self.normalize(token)


__all__ = ["TextNormalizer"]
