# backend/core/modules/users/router/requests/demo_unsubscribe_request.py
# Feladat: Demo unsubscribe HTTP request DTO. A demo leiratkozási token vagy email adatokat hordozza a profile router opt-out folyamatához. Users web request contract.
# Sárközi Mihály - 2026.05.21

from pydantic import BaseModel


class DemoUnsubscribeRequest(BaseModel):
    email: str
