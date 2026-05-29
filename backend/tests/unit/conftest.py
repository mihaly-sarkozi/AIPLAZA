"""Unit tesztek (``tests/unit``): gyors, önálló modulok, stub/fake.

Ne hivatkozz ``app``, ``client``, ``ensure_demo_test_tenant`` fixture-ökre –
azok csak ``tests/integration/`` alatt érhetők el (lásd ``integration/conftest.py``).

Önállóan tesztelhető core területek: ``core.testability`` modul-dokumentáció.
"""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
