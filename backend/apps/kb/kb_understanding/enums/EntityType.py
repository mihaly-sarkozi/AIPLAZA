from __future__ import annotations

# backend/apps/kb/kb_understanding/enums/EntityType.py
# Feladat: A felismerhető entitástípusok kanonikus listája.
# Sárközi Mihály - 2026.06.11

from enum import Enum


class EntityType(str, Enum):
    PERSON = "person"
    CUSTOMER = "customer"
    COMPANY = "company"
    PROJECT = "project"
    PRODUCT = "product"
    SYSTEM = "system"
    PROCESS = "process"
    DOCUMENT = "document"
    CONTRACT_NUMBER = "contract_number"
    INVOICE_NUMBER = "invoice_number"
    TICKET_ID = "ticket_id"
    DATE = "date"
    DEADLINE = "deadline"
    OTHER = "other"


__all__ = ["EntityType"]
