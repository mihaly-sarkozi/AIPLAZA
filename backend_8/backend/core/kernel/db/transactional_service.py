# backend/core/kernel/db/transactional_service.py
# Feladat: Szolgáltatásosztályoknak ad opcionális tranzakciós context helper mixint. Ha van transaction_manager, azon keresztül futtatja a műveletet, különben no-op contextet ad vissza, így a service-ek egységes mintával írhatók. Core helper, mert általános tranzakciókezelési szerződést ad üzleti logika nélkül.
# Sárközi Mihály - 2026.05.21

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
