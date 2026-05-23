# backend/apps/billing/payment.py
# Feladat: A billing app payment provider adaptere. Manual, simulated és stripe_test módokhoz egységes PaymentExecutionResult választ ad, Stripe teszt fizetésnél környezeti secretet és timeoutos HTTP hívást használ. Program-specifikus payment gateway integráció.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
import os
import hmac
import hashlib
import time
from dataclasses import dataclass

import requests

from apps.billing.models import DEFAULT_CURRENCY

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentExecutionResult:
    success: bool
    status: str
    payment_method: str
    message: str | None = None
    external_id: str | None = None


class BillingPaymentGateway:
    @staticmethod
    def verify_webhook_signature(*, payload: bytes, signature: str | None, secret: str | None) -> bool:
        normalized_secret = str(secret or "").strip()
        normalized_signature = str(signature or "").strip()
        if not normalized_secret or not normalized_signature:
            return False
        if "v1=" in normalized_signature and "t=" in normalized_signature:
            parts = {}
            for item in normalized_signature.split(","):
                key, _, value = item.partition("=")
                parts[key.strip()] = value.strip()
            timestamp = parts.get("t") or ""
            try:
                skew = abs(int(time.time()) - int(timestamp))
            except ValueError:
                return False
            max_skew = int(os.getenv("BILLING_WEBHOOK_SIGNATURE_MAX_SKEW_SEC") or "300")
            if skew > max(1, max_skew):
                return False
            signed_payload = f"{timestamp}.".encode("utf-8") + (payload or b"")
            expected = hmac.new(normalized_secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, parts.get("v1") or "")
        expected = hmac.new(
            normalized_secret.encode("utf-8"),
            payload or b"",
            hashlib.sha256,
        ).hexdigest()
        incoming = normalized_signature.removeprefix("sha256=").strip()
        return hmac.compare_digest(expected, incoming)

    @staticmethod
    def provider() -> str:
        return (os.getenv("BILLING_PROVIDER") or "manual").strip().lower()

    def is_simulated_provider(self) -> bool:
        return self.provider() == "simulated"

    def invoice_paid_status(self) -> str:
        if self.is_simulated_provider():
            return "simulated_paid"
        if self.provider() == "stripe_test":
            return "paid"
        return "manual_paid"

    def invoice_payment_method(self) -> str:
        if self.is_simulated_provider():
            return "simulated_card"
        if self.provider() == "stripe_test":
            return "stripe_test_card"
        return "manual"

    @staticmethod
    def _stripe_test_secret_key() -> str:
        return (os.getenv("STRIPE_TEST_SECRET_KEY") or "").strip()

    @staticmethod
    def _stripe_test_currency() -> str:
        return (os.getenv("STRIPE_TEST_CURRENCY") or DEFAULT_CURRENCY).strip().lower() or "eur"

    @staticmethod
    def _stripe_test_default_payment_method() -> str:
        return (os.getenv("STRIPE_TEST_PAYMENT_METHOD") or "pm_card_visa").strip()

    def _charge_with_stripe_test(
        self,
        *,
        amount_cents: int,
        description: str,
        metadata: dict[str, str] | None = None,
    ) -> PaymentExecutionResult:
        secret_key = self._stripe_test_secret_key()
        if not secret_key:
            return PaymentExecutionResult(
                success=False,
                status="config_error",
                payment_method="stripe_test_card",
                message="Hiányzik a STRIPE_TEST_SECRET_KEY.",
            )
        if amount_cents <= 0:
            return PaymentExecutionResult(
                success=True,
                status="no_charge",
                payment_method="stripe_test_card",
                message="Nulla összegű fizetés.",
            )
        body: list[tuple[str, str]] = [
            ("amount", str(max(0, int(amount_cents)))),
            ("currency", self._stripe_test_currency()),
            ("payment_method", self._stripe_test_default_payment_method()),
            ("confirm", "true"),
            ("off_session", "true"),
            ("description", description),
        ]
        for key, value in (metadata or {}).items():
            body.append((f"metadata[{key}]", value))
        try:
            response = requests.post(
                "https://api.stripe.com/v1/payment_intents",
                data=body,
                headers={"Authorization": f"Bearer {secret_key}"},
                timeout=20,
            )
            payload = response.json()
        except Exception as exc:
            logger.exception("Stripe test payment request failed")
            return PaymentExecutionResult(
                success=False,
                status="provider_error",
                payment_method="stripe_test_card",
                message=f"Stripe elérés sikertelen: {exc}",
            )
        if response.status_code >= 400:
            detail = ""
            if isinstance(payload, dict):
                err = payload.get("error")
                if isinstance(err, dict):
                    detail = str(err.get("message") or "")
            return PaymentExecutionResult(
                success=False,
                status="provider_rejected",
                payment_method="stripe_test_card",
                message=f"Stripe elutasította a fizetést. {detail}".strip(),
                external_id=str(payload.get("id") or "") if isinstance(payload, dict) else None,
            )
        status = str(payload.get("status") or "unknown") if isinstance(payload, dict) else "unknown"
        success = status in {"succeeded", "processing", "requires_capture"}
        return PaymentExecutionResult(
            success=success,
            status=status,
            payment_method="stripe_test_card",
            message=None if success else f"Sikertelen Stripe státusz: {status}",
            external_id=str(payload.get("id") or "") if isinstance(payload, dict) else None,
        )

    def execute_payment(
        self,
        *,
        amount_cents: int,
        description: str,
        metadata: dict[str, str] | None = None,
    ) -> PaymentExecutionResult:
        provider = self.provider()
        if provider == "simulated":
            return PaymentExecutionResult(
                success=True,
                status="simulated_paid",
                payment_method="simulated_card",
            )
        if provider == "stripe_test":
            return self._charge_with_stripe_test(
                amount_cents=amount_cents,
                description=description,
                metadata=metadata,
            )
        if provider == "manual":
            return PaymentExecutionResult(
                success=False,
                status="manual_required",
                payment_method="manual",
                message="Manual billing mode: fizetés admin jóváhagyással történik.",
            )
        return PaymentExecutionResult(
            success=False,
            status="provider_not_supported",
            payment_method="unknown",
            message=f"Nem támogatott billing provider: {provider}",
        )


__all__ = ["BillingPaymentGateway", "PaymentExecutionResult"]
