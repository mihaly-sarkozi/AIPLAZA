# Ez a fájl az adott terület szolgáltatás- és üzleti logikáját tartalmazza.
from __future__ import annotations

from contextlib import nullcontext


class TransactionalServiceMixin:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, transaction_manager=None) -> None:
        self._transaction_manager = transaction_manager

    # Ez a metódus a(z) transaction logikáját valósítja meg.
    def _transaction(self):
        return self._transaction_manager() if self._transaction_manager else nullcontext()


TransactionalService = TransactionalServiceMixin

__all__ = ["TransactionalService", "TransactionalServiceMixin"]
