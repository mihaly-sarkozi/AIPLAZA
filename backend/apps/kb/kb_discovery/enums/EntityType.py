from __future__ import annotations

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
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    OTHER = "other"


__all__ = ["EntityType"]
