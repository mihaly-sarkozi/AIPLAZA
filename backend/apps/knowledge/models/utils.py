# Ez a fájl az adott terület adatmodelljeit és kapcsolódó struktúráit tartalmazza.
from datetime import datetime

from core.kernel.clock import utc_now_naive


def _utcnow_naive() -> datetime:
    """UTC now timezone-naive formában (SQLAlchemy defaulthoz)."""
    return utc_now_naive()


__all__ = ['_utcnow_naive']
