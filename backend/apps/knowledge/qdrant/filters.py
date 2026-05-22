# backend/apps/knowledge/qdrant/filters.py
# Feladat: Qdrant payload filter építő helper függvényt tartalmaz. Dict alapú egyenlőség, lista MatchAny és range feltételeket alakít Qdrant Filter objektummá, hogy a wrapper keresési logikája vékonyabb maradjon. Program-specifikus Qdrant filter adapter.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from qdrant_client import models as qm


def build_payload_filter(payload_filter: dict[str, Any] | None = None) -> qm.Filter | None:
    if not payload_filter:
        return None
    must: list[qm.FieldCondition] = []
    for key, value in payload_filter.items():
        if value is None:
            continue
        if isinstance(value, list):
            must.append(
                qm.FieldCondition(
                    key=key,
                    match=qm.MatchAny(any=value),
                )
            )
        elif isinstance(value, dict) and any(k in value for k in ["gte", "lte", "gt", "lt"]):
            must.append(
                qm.FieldCondition(
                    key=key,
                    range=qm.Range(
                        gte=value.get("gte"),
                        lte=value.get("lte"),
                        gt=value.get("gt"),
                        lt=value.get("lt"),
                    ),
                )
            )
        else:
            must.append(
                qm.FieldCondition(
                    key=key,
                    match=qm.MatchValue(value=value),
                )
            )
    if not must:
        return None
    return qm.Filter(must=must)


__all__ = ["build_payload_filter"]
