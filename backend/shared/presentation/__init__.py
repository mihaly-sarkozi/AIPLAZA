# backend/shared/presentation/__init__.py
# Feladat: A shared presentation csomag exportfelülete. A LocalizedPresenterBase helper osztályt adja tovább core és app routerek számára, hogy egységes lokalizált HTTP detail payloadot építhessenek. Általános presentation utility belépési pont.
# Sárközi Mihály - 2026.05.21

from shared.presentation.localized_presenter_base import LocalizedPresenterBase

__all__ = ["LocalizedPresenterBase"]
