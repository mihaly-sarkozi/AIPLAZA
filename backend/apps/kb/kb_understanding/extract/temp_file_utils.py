from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def safe_delete_temp_file(path: str | None, *, keep_on_error: bool = False) -> None:
    if not path or keep_on_error:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except Exception:
        logger.warning("Temp fájl törlése sikertelen: %s", path, exc_info=True)


__all__ = ["safe_delete_temp_file"]
