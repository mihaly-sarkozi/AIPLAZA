from __future__ import annotations

# backend/apps/settings/service/eu_vat_validation_service.py
# Feladat: EU VIES adószám-ellenőrző adapter a settings számlázási adatok validációjához.
# Sárközi Mihály - 2026.05.24

from dataclasses import dataclass
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

from apps.settings.domain.billing_countries import normalize_eu_vat_id, vat_prefix_for_country


class EuVatValidationUnavailableError(RuntimeError):
    """Raised when the external VIES service cannot be reached reliably."""


@dataclass(frozen=True)
class EuVatValidationResult:
    country_code: str
    vat_number: str
    valid: bool
    name: str = ""
    address: str = ""


class EuVatValidationService:
    endpoint = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"

    def __init__(self, *, timeout_seconds: float = 5.0) -> None:
        self._timeout_seconds = timeout_seconds

    def validate(self, *, country_code: str, vat_id: str) -> EuVatValidationResult:
        vat_prefix = vat_prefix_for_country(country_code)
        normalized = normalize_eu_vat_id(vat_id)
        vat_number = normalized.removeprefix(vat_prefix)
        if not re.fullmatch(r"[A-Z0-9]{2,14}", vat_number):
            return EuVatValidationResult(country_code=vat_prefix, vat_number=vat_number, valid=False)
        payload = self._build_payload(vat_prefix, vat_number)
        request = urllib.request.Request(
            self.endpoint,
            data=payload.encode("utf-8"),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": "",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                body = response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise EuVatValidationUnavailableError("VIES VAT validation is unavailable.") from exc
        return self._parse_response(body, vat_prefix, vat_number)

    @staticmethod
    def _build_payload(country_code: str, vat_number: str) -> str:
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns1="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
  <soap:Body>
    <tns1:checkVat>
      <tns1:countryCode>{country_code}</tns1:countryCode>
      <tns1:vatNumber>{vat_number}</tns1:vatNumber>
    </tns1:checkVat>
  </soap:Body>
</soap:Envelope>"""

    @staticmethod
    def _parse_response(body: bytes, country_code: str, vat_number: str) -> EuVatValidationResult:
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise EuVatValidationUnavailableError("VIES VAT validation returned invalid XML.") from exc
        fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            raise EuVatValidationUnavailableError("VIES VAT validation returned a SOAP fault.")
        valid_text = root.findtext(".//{urn:ec.europa.eu:taxud:vies:services:checkVat:types}valid", default="false")
        name = root.findtext(".//{urn:ec.europa.eu:taxud:vies:services:checkVat:types}name", default="") or ""
        address = root.findtext(".//{urn:ec.europa.eu:taxud:vies:services:checkVat:types}address", default="") or ""
        return EuVatValidationResult(
            country_code=country_code,
            vat_number=vat_number,
            valid=str(valid_text).strip().lower() == "true",
            name=name.strip(),
            address=address.strip(),
        )


__all__ = ["EuVatValidationResult", "EuVatValidationService", "EuVatValidationUnavailableError"]
