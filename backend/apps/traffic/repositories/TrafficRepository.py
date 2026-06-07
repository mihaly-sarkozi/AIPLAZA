# backend/apps/traffic/repositories/TrafficRepository.py
# Feladat: A TrafficRepository read-only adat-hozzáférési osztályt tartalmazza. Public traffic usage táblákból és tenant-sémás knowledge/user táblákból olvas forgalmi nyers adatokat.

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from sqlalchemy import text

from core.modules.users.models.user_orm import UserORM


class TrafficRepository:
    """Read-only adat-hozzáférés a forgalom oldalhoz szükséges táblákhoz."""

    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]) -> None:
        self._session_factory = session_factory

    def list_catalog(self) -> list[dict[str, Any]]:
        """Visszaadja az aktív billing catalog sorokat public sémából a limitek és addon opciók számolásához."""

        with self._session_factory() as db:
            db.execute(text("SET search_path TO public"))
            rows = db.execute(
                text(
                    """
                    SELECT entry_type, code, name, currency, price_cents, included, metadata
                    FROM billing_catalog_entries
                    WHERE is_active IS TRUE
                    ORDER BY entry_type ASC, id ASC
                    """
                )
            ).mappings()
            return [dict(row) for row in rows]

    def get_subscription(self, tenant_id: int) -> dict[str, Any] | None:
        """Lekéri a tenant aktuális előfizetését public sémából, ha már létezik."""

        with self._session_factory() as db:
            db.execute(text("SET search_path TO public"))
            row = db.execute(
                text(
                    """
                    SELECT plan_code, billing_period, status, extra_kb_count, extra_storage_gb,
                           carryover_addon_questions, carryover_training_chars
                    FROM billing_subscriptions
                    WHERE tenant_id = :tenant_id
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings().first()
            return dict(row) if row else None

    def list_question_usage(self, tenant_id: int, period_key: str) -> list[dict[str, Any]]:
        """Felhasználónként visszaadja az adott időszak kérdéshasználatát public sémából."""

        with self._session_factory() as db:
            db.execute(text("SET search_path TO public"))
            rows = db.execute(
                text(
                    """
                    SELECT user_id, question_count
                    FROM traffic_question_usage
                    WHERE tenant_id = :tenant_id AND period_key = :period_key
                    ORDER BY question_count DESC, user_id ASC
                    """
                ),
                {"tenant_id": tenant_id, "period_key": period_key},
            ).mappings()
            return [dict(row) for row in rows]

    def get_training_usage(self, tenant_id: int, period_key: str) -> dict[str, Any] | None:
        """Lekéri az adott időszak tanítási karakter- és tárhelyhasználatát public sémából."""

        with self._session_factory() as db:
            db.execute(text("SET search_path TO public"))
            row = db.execute(
                text(
                    """
                    SELECT trained_chars, storage_bytes
                    FROM billing_training_usage
                    WHERE tenant_id = :tenant_id AND period_key = :period_key
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "period_key": period_key},
            ).mappings().first()
            return dict(row) if row else None

    def list_training_addon_invoice_lines(self, tenant_id: int) -> list[dict[str, Any]]:
        """A kifizetett tanítási addon számlák sorait adja vissza, mert ezek növelik a tanítási keretet."""

        with self._session_factory() as db:
            db.execute(text("SET search_path TO public"))
            rows = db.execute(
                text(
                    """
                    SELECT lines
                    FROM billing_invoices
                    WHERE tenant_id = :tenant_id
                      AND invoice_type IN ('addon:training_initial_500k', 'addon:training_extra_500k')
                      AND status IN ('simulated_paid', 'paid')
                    """
                ),
                {"tenant_id": tenant_id},
            ).mappings()
            lines: list[dict[str, Any]] = []
            for row in rows:
                for line in list(row.get("lines") or []):
                    if isinstance(line, dict):
                        lines.append(line)
            return lines

    def load_user_map(self) -> dict[int, UserORM]:
        """Tenant-sémából felolvassa az aktív user sorokat, hogy a kérdéshasználat névvel és emaillel jelenjen meg."""

        with self._session_factory() as db:
            return {int(row.id): row for row in db.query(UserORM).filter(UserORM.deleted_at.is_(None)).all()}

    def load_resource_counts(self) -> dict[str, int]:
        """Tenant-sémás táblákból aggregálja a user, tudástár és feltöltött fájlméret mutatókat."""

        with self._session_factory() as db:
            user_count = db.query(UserORM).filter(UserORM.deleted_at.is_(None)).count()
            schema = db.execute(text("select current_schema()")).scalar_one()

            def table_exists(table_name: str) -> bool:
                return bool(
                    db.execute(
                        text(
                            """
                            select 1
                            from information_schema.tables
                            where table_schema = :schema and table_name = :table_name
                            """
                        ),
                        {"schema": schema, "table_name": table_name},
                    ).scalar_one_or_none()
                )

            def column_exists(table_name: str, column_name: str) -> bool:
                return bool(
                    db.execute(
                        text(
                            """
                            select 1
                            from information_schema.columns
                            where table_schema = :schema and table_name = :table_name and column_name = :column_name
                            """
                        ),
                        {"schema": schema, "table_name": table_name, "column_name": column_name},
                    ).scalar_one_or_none()
                )

            has_kb_table = table_exists("knowledge_bases")
            has_deleted_at = has_kb_table and column_exists("knowledge_bases", "deleted_at")
            kb_where = "WHERE deleted_at IS NULL" if has_deleted_at else ""
            kb_count = (
                db.execute(text(f"SELECT COUNT(*) FROM knowledge_bases {kb_where}")).scalar() or 0
                if has_kb_table
                else 0
            )
            storage_bytes = 0
            if has_kb_table and table_exists("knowledge_ingest_inputs") and table_exists("knowledge_ingest_items"):
                deleted_filter = "WHERE kb.deleted_at IS NULL" if has_deleted_at else ""
                storage_bytes = db.execute(
                    text(
                        f"""
                        SELECT COALESCE(SUM(COALESCE(inp.size_bytes, 0)), 0)
                        FROM knowledge_ingest_inputs inp
                        JOIN knowledge_ingest_items item ON item.id = inp.ingest_item_id
                        JOIN knowledge_bases kb ON kb.uuid = item.corpus_uuid
                        {deleted_filter}
                        """
                    )
                ).scalar() or 0
            return {
                "users": int(user_count or 0),
                "knowledge_bases": int(kb_count or 0),
                "storage_bytes": int(storage_bytes or 0),
            }


__all__ = ["TrafficRepository"]
