# apps/knowledge/pii_gdpr/detectors/regex_detector.py
"""
Rule-based regex detector for deterministic PII patterns.
Multilingual patterns for EN, HU, ES where relevant.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from apps.knowledge.pii_gdpr.enums import EntityType, RiskClass, RecommendedAction
from apps.knowledge.pii_gdpr.models import DetectionResult
from apps.knowledge.pii_gdpr.detectors.base import BaseDetector


# (entity_type, pattern, base_confidence, risk_class) vagy (..., capture_group) ha csak a captured részt maszkoljuk
_REGEX_RULES: List[Tuple] = [
    # Email
    (EntityType.EMAIL_ADDRESS, r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", 0.95, RiskClass.DIRECT_PII),
    # Phone – international, HU, ES
    (EntityType.PHONE_NUMBER, r"\+\d{1,3}[\s\-.]?(?:\d[\s\-.]?){8,14}\d\b", 0.88, RiskClass.DIRECT_PII),
    (EntityType.PHONE_NUMBER, r"\b(?:\+36|06)[\s\-/]?\d{1,2}[\s\-/]?\d{3}[\s\-/]?\d{4}\b", 0.92, RiskClass.DIRECT_PII),
    (EntityType.PHONE_NUMBER, r"(?<!\d)(?:\+34|0034)[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{3}\b", 0.85, RiskClass.DIRECT_PII),
    (EntityType.PHONE_NUMBER, r"\b(?:\+34|0034)?[\s\-]?\d{2,3}[\s\-]?\d{3}[\s\-]?\d{3}\b", 0.85, RiskClass.DIRECT_PII),
    (EntityType.PHONE_NUMBER, r"\b\d{2}[\s\-/]\d{3}[\s\-/]\d{4}\b", 0.75, RiskClass.DIRECT_PII),
    # IBAN
    (EntityType.IBAN, r"\b[A-Z]{2}\d{2}\s?(?:[A-Z0-9]\s?){4}(?:[A-Z0-9]\s?){4,28}\b", 0.92, RiskClass.DIRECT_PII),
    # Bank account HU style
    (EntityType.BANK_ACCOUNT_NUMBER, r"\b\d{8}[\- ]?\d{8}[\- ]?\d{8}\b", 0.85, RiskClass.DIRECT_PII),
    # Payment card (simplified – 4 groups of 4 digits)
    (EntityType.PAYMENT_CARD_NUMBER, r"\b(?:\d{4}[\s\-]){3}\d{4}\b", 0.82, RiskClass.DIRECT_PII),
    # Általános dátum (dátum) – nincs születési kontextus
    (EntityType.DATE, r"\b(?:19|20)\d{2}[.\-/](?:0[1-9]|1[0-2])[.\-/](?:0[1-9]|[12]\d|3[01])\b", 0.68, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.DATE, r"\b(?:0[1-9]|[12]\d|3[01])[.\-/](?:0[1-9]|1[0-2])[.\-/](?:19|20)\d{2}\b", 0.68, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.DATE, r"\b(?:19|20)\d{2}\.\s*(?:0[1-9]|1[0-2])\.\s*(?:0[1-9]|[12]\d|3[01])\.?", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    # Hónapnév + szám előtte/utána = dátum egységként (HU, EN, ES)
    # év. hónapnév nap (pl. 1992. március 14., 2025. február 18-án)
    (EntityType.DATE, r"(?i)\b(?:19|20)\d{2}\.\s*(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december|january|february|march|april|may|june|july|august|september|october|november|december|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{1,2}[.\s\-]*(?:án|én)?\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    # nap. hónapnév év (pl. 14. március 1992, 18 de febrero de 2025)
    (EntityType.DATE, r"(?i)\b(?:0[1-9]|[12]\d|3[01])[.\s]*(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december|january|february|march|april|may|june|july|august|september|october|november|december|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)[.\s]+(?:de\s+)?(?:19|20)\d{2}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    # hónapnév nap (pl. március 14., március 14-én, February 18)
    (EntityType.DATE, r"(?i)\b(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december|january|february|march|april|may|june|july|august|september|october|november|december|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+\d{1,2}[.\s\-]*(?:án|én)?\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    # nap hónapnév (pl. 14 március, 18 February)
    (EntityType.DATE, r"(?i)\b(?:0[1-9]|[12]\d|3[01])\s+(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december|january|february|march|april|may|june|july|august|september|october|november|december|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    # hónapnév nap, év (pl. February 18, 2025)
    (EntityType.DATE, r"(?i)\b(?:january|february|march|april|may|june|july|august|september|october|november|december|január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s+\d{1,2}\s*,\s*(?:19|20)\d{2}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    # Születési dátum – CSAK a dátum maszkolódik, a kulcsszó (szül.:, dob, date of birth) nem (capture group 1)
    (EntityType.DATE_OF_BIRTH, r"(?i)\b(?:született|szül\.?|dob|date of birth|fecha de nacimiento)\s*:\s*((?:19|20)\d{2}[.\s\-/]*(?:0[1-9]|1[0-2])[.\s\-/]*(?:0[1-9]|[12]\d|3[01])\b)", 0.90, RiskClass.DIRECT_PII, 1),
    (EntityType.DATE_OF_BIRTH, r"(?i)\b(?:született|szül\.?|dob|date of birth|fecha de nacimiento)\s*:\s*((?:0[1-9]|[12]\d|3[01])[.\s\-/]*(?:0[1-9]|1[0-2])[.\s\-/]*(?:19|20)\d{2}\b)", 0.90, RiskClass.DIRECT_PII, 1),
    # Magyar hónapnévvel: szül.: 1989. augusztus 17. – csak a dátum
    (EntityType.DATE_OF_BIRTH, r"(?i)\b(?:született|szül\.?)\s*:\s*((?:19|20)\d{2}\.\s*(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s+\d{1,2}\.?)", 0.92, RiskClass.DIRECT_PII, 1),
    # IP
    (EntityType.IP_ADDRESS, r"\b(?:\d{1,3}\.){3}\d{1,3}\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.IP_ADDRESS, r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b", 0.85, RiskClass.INDIRECT_IDENTIFIER),
    # MAC
    (EntityType.MAC_ADDRESS, r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b", 0.88, RiskClass.INDIRECT_IDENTIFIER),
    # IMEI – csak a 15 számjegy maszkolódik, az "IMEI" kulcsszó nem
    (EntityType.IMEI, r"\b\d{15}\b", 0.65, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.IMEI, r"(?i)\bIMEI\s*[:\s]+\s*(\d{15})\b", 0.92, RiskClass.INDIRECT_IDENTIFIER, 1),
    # VIN / alvázszám – csak a 17 karakter maszkolódik, a kulcsszó nem
    (EntityType.VIN, r"\b[A-HJ-NPR-Z0-9]{17}\b", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.VIN, r"(?i)\b(?:VIN\s*/\s*alvázszám|VIN\s*:\s*|alvázszám\s*[:\s]*|chassis\s*[:\s]*)\s*([A-HJ-NPR-Z0-9]{17})\b", 0.92, RiskClass.INDIRECT_IDENTIFIER, 1),
    # Vehicle registration – HU, ES, generic
    (EntityType.VEHICLE_REGISTRATION, r"\b[A-Z]{3}[- ]?\d{3}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.VEHICLE_REGISTRATION, r"\b[A-Z]{2}[- ]?\d{2}[- ]?[A-Z]{2}[- ]?\d{2}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.VEHICLE_REGISTRATION, r"\b\d{4}\s+[A-Z]{3}\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    # Customer ID / Contract / Ticket
    (EntityType.CUSTOMER_ID, r"\b(?:UGY|UGYFEL|CLIENT|cliente|cust)[\- ]?\d{4,10}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CUSTOMER_ID, r"\b(?:HU|HU-)[\- ]?\d{4,10}\b", 0.88, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CUSTOMER_ID, r"#\d{4,12}\b", 0.60, RiskClass.INDIRECT_IDENTIFIER),
    # CONTRACT-2025-00481: több szegmens is (a sor végéig), ne csak CONTRACT-2025
    (EntityType.CONTRACT_NUMBER, r"\b(?:SZ|Szerz\.?|Szerződés|CONTRACT|contrato)[\- ]?(?:\d+[\-])*\d{4,12}\b", 0.80, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.TICKET_ID, r"\b(?:TKT|TICKET|JIRA)[\- ]?\d{4,10}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.EMPLOYEE_ID, r"\b(?:EMP|employee|dolgozói|empleado)[\- ]?\d{4,10}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    # Session / Cookie / Device
    (EntityType.SESSION_ID, r"\b(?:sess(?:ion)?_?|sessionid)[\w\-]{8,64}\b", 0.72, RiskClass.INDIRECT_IDENTIFIER),
    # device identifier DEV-998877 – "identifier" és opcionális delimiter
    (EntityType.DEVICE_ID, r"\b(?:device\s+identifier|device[_\s]?id|deviceid)[\s:=]?\s*[\w\-]{8,40}\b", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    # Hungarian address (irányítószám + város + utca + szám, opcionálisan emelet/ajtó 3/12.)
    (EntityType.POSTAL_ADDRESS, r"\b\d{4}\s+[A-ZÁÉÍÓÖÜŐÚ][a-záéíóöüőú]+(?:\s+[A-Za-záéíóöüőú]+)*\s*,\s*[A-ZÁÉÍÓÖÜŐÚa-záéíóöüőú][^,]*?\s+\d+[a-z]?(?:\s*\.?\s*\d+/\d+\.?)?\b", 0.82, RiskClass.DIRECT_PII),
    # Magyar cím: város, név + közterület + szám (pl. Budaörs, Szabadság út 22)
    (EntityType.POSTAL_ADDRESS, r"\b[A-ZÁÉÍÓÖÜŐÚ][a-záéíóöüőú]+(?:\s+[A-Za-záéíóöüőú]+)*\s*,\s*[A-Za-záéíóöüőú\s\-]*(?:utca|út|útja|tér|tere|körút|sétány|rakpart|liget|park|köz|sor)\s+[\wáéíóöüőú\-]*\s*\d+(?:\s*[./]\s*\d+(?:\s*/\s*\d+)?\.?)*\b", 0.80, RiskClass.DIRECT_PII),
    # Magyar rövidített cím: Város, Név 18-24., 2/7. (közterület nélkül)
    (EntityType.POSTAL_ADDRESS, r"\b[A-ZÁÉÍÓÖÜŐÚ][a-záéíóöüőú]+(?:\s+[A-Za-záéíóöüőú]+)*\s*,\s*[A-ZÁÉÍÓÖÜŐÚa-záéíóöüőú]+(?:\s+[A-Za-záéíóöüőú]+)*\s+\d+[\-\d]*(?:\s*\.\s*,\s*\d+/\d+\.?)?\b", 0.72, RiskClass.DIRECT_PII),
    # Spanish address: Calle/Plaza Name Number, City (e.g. Calle Mayor 12, Madrid)
    (EntityType.POSTAL_ADDRESS, r"\b(?:Calle|Plaza|Callejón|Avenida|Av\.?)\s+[A-Za-záéíóúñÁÉÍÓÚÑ0-9\s]+\d+\.?,?\s+[A-Za-záéíóúñÁÉÍÓÚÑ\s]+", 0.78, RiskClass.DIRECT_PII),
    # Spanish address with continuation: Calle X 12, Edificio B, Planta 3, Puerta 2/7, Madrid
    (EntityType.POSTAL_ADDRESS, r"\b(?:Calle|Avenida|Av\.?|Plaza|Paseo)\s+[A-Za-záéíóúñÁÉÍÓÚÑ0-9\s]+\d+(?:\s*,\s*(?:Edificio|Portal|Planta|Piso|Puerta|Bloque|Escalera)\s+[A-Z0-9/\s]+)*\.?,?\s+[A-Za-záéíóúñÁÉÍÓÚÑ\s]*", 0.82, RiskClass.DIRECT_PII),
    # Spanish shortened: Madrid, Mayor 12, Piso 4, Puerta 2/7
    (EntityType.POSTAL_ADDRESS, r"\b[A-ZÁÉÍÓÚÑa-záéíóúñ]+\s*,\s*[A-Za-záéíóúñÁÉÍÓÚÑ0-9\s]+\d+(?:\s*,\s*(?:Piso|Planta|Puerta|Edificio)\s+[\w/\s]+)?\b", 0.82, RiskClass.DIRECT_PII),
    # Spanish customer/contract labels (plate 1234 ABC already covered by \d{4}\s+[A-Z]{3} above)
    (EntityType.CUSTOMER_ID, r"\b(?:cliente|id\s*cliente|número\s*de\s*cliente)\s*[:\-]?\s*\d{4,12}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CONTRACT_NUMBER, r"\b(?:contrato|número\s*de\s*contrato|contrato\s*n\.?º?)\s*[:\-]?\s*\d{4,12}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    # TAJ (Hungarian personal id) – 9 digits in 3-3-3
    (EntityType.PERSONAL_ID, r"\b\d{3}\s?\d{3}\s?\d{3}\b", 0.65, RiskClass.DIRECT_PII),
    (EntityType.TAX_ID, r"\b\d{8}[\- ]?\d{1}[\- ]?\d{2}\b", 0.72, RiskClass.DIRECT_PII),
    # Passport / Driver license – csak az azonosító maszkolódik, a kulcsszó nem (pl. CD7654321)
    (EntityType.PASSPORT_NUMBER, r"(?i)(?:(?<=passport: )|(?<=passport )|(?<=útlevél: )|(?<=útlevél )|(?<=pasaporte: ))\b[A-Z0-9]{6,15}\b", 0.85, RiskClass.DIRECT_PII),
    (EntityType.PASSPORT_NUMBER, r"(?i)(?:(?<=passport number )|(?<=passport szám )|(?<=útlevél szám ))\b[A-Z0-9]{6,12}\b", 0.85, RiskClass.DIRECT_PII),
    (EntityType.DRIVER_LICENSE_NUMBER, r"(?i)(?:(?<=driver license: )|(?<=jogosítvány: )|(?<=permiso: ))\b[A-Z0-9]{6,12}\b", 0.82, RiskClass.DIRECT_PII),
    (EntityType.DRIVER_LICENSE_NUMBER, r"(?i)(?:(?<=jogosítványszám )|(?<=jogosítvány száma )|(?<=permiso de conducir ))\b[A-Z0-9\-]{6,15}\b", 0.88, RiskClass.DIRECT_PII),
    # Dátum + egészségügyi kontextus (pl. 2025. február 18-án orvosi vizsgálat miatt)
    (EntityType.HEALTH_DATA_HINT, r"(?i)\b(?:19|20)\d{2}\.\s*(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s+\d{1,2}[.-]*(?:án|én)?\s+orvosi\s+vizsgálat(?:\s+miatt)?", 0.90, RiskClass.SENSITIVE_DATA),
    # --- Kontextus alapú azonosítók (HU/EN/ES + elírások) ---
    # Személyi igazolvány – csak a szám/azonosító maszkolódik, a kulcsszó nem (pl. BB654321)
    (EntityType.PERSONAL_ID, r"(?i)(?:(?<=személyi igazolvány száma )|(?<=személyi igazolvány: )|(?<=személyi igazolvány )|(?<=személyi igazolványszám )|(?<=személyi igazolványszám: ))\b[A-Z0-9]{6,15}\b", 0.88, RiskClass.DIRECT_PII),
    (EntityType.PASSPORT_NUMBER, r"(?i)(?:(?<=útlevélszáma )|(?<=útlevél száma )|(?<=útlevél száma: ))\b[A-Z0-9]{6,12}\b", 0.88, RiskClass.DIRECT_PII),
    # Belső ügyazonosító CUST-775544, ügyfélazonosító CUSTOMER-009912
    (EntityType.CUSTOMER_ID, r"(?i)\b(?:belső\s+)?(?:ügyazonosító|ügyaznosító|ügyfélazonosító|customer\s+id)\s*[:\-]?\s*(?:CUST|CUSTOMER)[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.85, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CUSTOMER_ID, r"\b(?:CUST|CUSTOMER)[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.72, RiskClass.INDIRECT_IDENTIFIER),
    # Belső flottakód FLEET-2026-11
    (EntityType.CONTRACT_NUMBER, r"(?i)\b(?:belső\s+)?flottakód\s*[:\-]?\s*FLEET[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.85, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CONTRACT_NUMBER, r"\bFLEET[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    # device ID DEV-445566 – csak az azonosító maszkolódik, az "ID" / "identifier" kulcsszó nem
    (EntityType.DEVICE_ID, r"(?i)\b(?:device\s+id|deviceid|device\s+identifier)\s*[:\-]?\s*((?:DEV|LAPTOP|DESKTOP)[\w\-]{4,30})\b", 0.82, RiskClass.INDIRECT_IDENTIFIER, 1),
    (EntityType.DEVICE_ID, r"(?i)\b(?:device\s+whose\s+hostname\s+was|hostname\s+is?)\s+[\w\-]{6,40}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    # Spanyol: número de cliente CL-884421
    (EntityType.CUSTOMER_ID, r"(?i)\b(?:número\s+de\s+cliente|nº?\s*cliente)\s*[:\-]?\s*(?:CL[\- ]?)?[\w\-]{4,20}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CUSTOMER_ID, r"\bCL[\- ]?\d{4,10}\b", 0.65, RiskClass.INDIRECT_IDENTIFIER),
    # el número de contrato CONTRATO-2025-7788
    (EntityType.CONTRACT_NUMBER, r"(?i)\b(?:el\s+)?(?:número\s+de\s+contrato|contrato\s*n\.?º?)\s*[:\-]?\s*CONTRATO[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.85, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CONTRACT_NUMBER, r"\bCONTRATO[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    # el ticket TKT-ES-4412, TKT- prefix kiterjesztve
    (EntityType.TICKET_ID, r"\b(?:TKT|TICKET|JIRA)[\- ]?(?:ES[\- ]?)?(?:\d+[\-])*\d{4,10}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    # su DNI 12345678Z, su NIF ESX1234567Y, su NIE X1234567Y (spanyol személyi/adó)
    (EntityType.PERSONAL_ID, r"(?i)(?:(?<=DNI: )|(?<=DNI )|(?<=su DNI ))\b[0-9]{8}[A-Z]\b", 0.90, RiskClass.DIRECT_PII),
    # NIF – csak az azonosító maszkolódik (pl. ESZ4455667K), a kulcsszó nem
    (EntityType.TAX_ID, r"(?i)(?:(?<=NIF: )|(?<=NIF ))\b[A-Z0-9]{7,15}[A-Z]?\b", 0.88, RiskClass.DIRECT_PII),
    (EntityType.TAX_ID, r"\b(?:ES[A-Z0-9]\d{7}[A-Z]?|ESX\d{7}[A-Z])\b", 0.75, RiskClass.DIRECT_PII),
    # NIE (Número de Identidad de Extranjero): X/Y/Z + 7 számjegy + ellenőrző betű (pl. X1234567Y)
    (EntityType.PERSONAL_ID, r"(?i)(?:(?<=NIE: )|(?<=NIE ))\b[XYZ]\d{7}[A-Z]\b", 0.90, RiskClass.DIRECT_PII),
    (EntityType.PERSONAL_ID, r"\b[XYZ]\d{7}[A-Z]\b", 0.70, RiskClass.DIRECT_PII),
    # identificador de dispositivo DEV-ES-2025-44
    (EntityType.DEVICE_ID, r"(?i)\b(?:identificador\s+de\s+dispositivo|id\s+de\s+dispositivo)\s*[:\-]?\s*[\w\-]{8,40}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.DEVICE_ID, r"\bDEV[\- ]?(?:ES[\- ]?)?(?:\d+[\-])*\d{4,10}\b", 0.68, RiskClass.INDIRECT_IDENTIFIER),
    # Spanyol dátum: el 18 de febrero de 2025
    (EntityType.DATE, r"(?i)\b(?:el\s+)?\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\s+(?:19|20)\d{2}\b", 0.78, RiskClass.INDIRECT_IDENTIFIER),
    # driver license number is SMITH-554433 – csak az azonosító
    (EntityType.DRIVER_LICENSE_NUMBER, r"(?i)(?:(?<=driver license number is )|(?<=jogosítvány száma is ))\b[\w\-]{6,20}\b", 0.85, RiskClass.DIRECT_PII),
    # his tax ID is 555-44-3333 – csak az azonosító
    (EntityType.TAX_ID, r"(?i)(?:(?<=tax id is )|(?<=adóazonosító jele is ))\b\d{3}[\- ]?\d{2}[\- ]?\d{4}\b", 0.88, RiskClass.DIRECT_PII),
    # user ID usr_882211, cookie ID ck_abcd9988 – csak az azonosító
    (EntityType.USER_ID, r"(?i)(?:(?<=user id: )|(?<=user id )|(?<=userid: ))\b(?:usr_|user_)?[\w\-]{6,40}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.USER_ID, r"\busr_[\w\-]{6,40}\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.COOKIE_ID, r"(?i)(?:(?<=cookie id: )|(?<=cookie id )|(?<=cookieid: ))\b(?:ck_|cookie_)?[\w\-]{6,40}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.COOKIE_ID, r"\bck_[\w\-]{6,40}\b", 0.72, RiskClass.INDIRECT_IDENTIFIER),
    # claim number CLM-2025-8881
    (EntityType.TICKET_ID, r"(?i)\b(?:claim\s+number|panasz\s+száma?|reklamáció)\s*[:\-]?\s*CLM[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.TICKET_ID, r"\bCLM[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    # fájl neve ugyfel_panasz_2026_final.docx
    (EntityType.TICKET_ID, r"(?i)\b(?:fájl\s+neve|file\s+name|nombre\s+de\s+archivo)\s*[:\-]?\s*[\w\-]+\.[a-z]{3,5}\b", 0.75, RiskClass.INDIRECT_IDENTIFIER),
    # Amerikai cím: 1600 Pennsylvania Avenue NW, Washington, DC 20500
    (EntityType.POSTAL_ADDRESS, r"\b\d{1,5}\s+[A-Za-z\s]+(?:Avenue|Ave|Street|St|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct)[\w\s]*,?\s+[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", 0.82, RiskClass.DIRECT_PII),
    # English address with Apt/Flat/Unit: 2458 Westlake Avenue, Apt 4B, Seattle, WA 98109
    (EntityType.POSTAL_ADDRESS, r"\b\d{1,5}\s+[A-Za-z\s]+(?:Avenue|Ave|Street|St|Road|Rd|Drive|Dr|Lane|Ln)[\w\s]*(?:\s*,\s*(?:Apt|Apartment|Flat|Unit|Suite|Building|Floor)\s+[\w/\-]+)*,?\s+[A-Za-z\s]+(?:,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)?\b", 0.78, RiskClass.DIRECT_PII),
    # English shortened: Manchester, King 78, Unit 2/7 (City, StreetName Number, Unit)
    (EntityType.POSTAL_ADDRESS, r"\b[A-Za-z][A-Za-z\s]*\s*,\s*[A-Za-z][A-Za-z\s]*\d+(?:\s*,\s*(?:Building|Block|Floor|Apt|Flat|Unit|Suite)\s+[\w/\-]+)?\b", 0.82, RiskClass.DIRECT_PII),
    # printer asset tag PRN-4477, network identifier node-77-eu
    (EntityType.DEVICE_ID, r"(?i)\b(?:printer\s+asset\s+tag|asset\s+tag)\s*[:\-]?\s*[\w\-]{6,30}\b", 0.80, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.DEVICE_ID, r"(?i)\b(?:network\s+identifier|node\s+id)\s*[:\-]?\s*[\w\-]{6,40}\b", 0.80, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.DEVICE_ID, r"\b(?:PRN|node)[\- ][\w\-]{4,30}\b", 0.68, RiskClass.INDIRECT_IDENTIFIER),
    # billing account number ACC-556677
    (EntityType.CUSTOMER_ID, r"(?i)\b(?:billing\s+account\s+number|számlázási\s+számla)\s*[:\-]?\s*[\w\-]{6,30}\b", 0.80, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.CUSTOMER_ID, r"\bACC[\- ]?\d{4,10}\b", 0.68, RiskClass.INDIRECT_IDENTIFIER),
    # recovery code RC-991122 – csak a kód (RC-xxx) maszkolódik, a "recovery code" címke nem
    (EntityType.SESSION_ID, r"(?i)(?:(?<=recovery code )|(?<=recovery code: )|(?<=recovery code - )|(?<=helyreállítási kód )|(?<=helyreállítási kód: ))\b[\w\-]{6,30}\b", 0.82, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.SESSION_ID, r"\bRC[\- ]?\d{4,10}\b", 0.65, RiskClass.INDIRECT_IDENTIFIER),
    # belső audit azonosító AUD-2026-0044
    (EntityType.TICKET_ID, r"(?i)\b(?:belső\s+)?(?:audit\s+azonosító|audit\s+id)\s*[:\-]?\s*AUD[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.85, RiskClass.INDIRECT_IDENTIFIER),
    (EntityType.TICKET_ID, r"\bAUD[\- ]?(?:\d+[\-])*\d{4,10}\b", 0.70, RiskClass.INDIRECT_IDENTIFIER),
    # GPS coordinate pair 47.4979, 19.0402 (helyadatként) – pozíció, koordináta, GPS, coordinates
    (EntityType.POSTAL_ADDRESS, r"(?i)\b(?:GPS\s+coordinate[s]?|koordináta|coordenada|pozíció|posición)\s*(?:pair|pár)?\s*[:\-]?\s*-?\d{1,3}\.\d{2,6}\s*,\s*-?\d{1,3}\.\d{2,6}\b", 0.85, RiskClass.INDIRECT_IDENTIFIER),
]


class RegexDetector(BaseDetector):
    """Detector using predefined regex rules. No external models required."""

    name = "regex"

    def detect(self, text: str, language: str = "en") -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for rule in _REGEX_RULES:
            entity_type, pattern, confidence, risk = rule[:4]
            capture_group = rule[4] if len(rule) >= 5 else 0
            try:
                for m in re.finditer(pattern, text):
                    if capture_group and m.lastindex >= capture_group:
                        start, end = m.start(capture_group), m.end(capture_group)
                        matched = m.group(capture_group).strip()
                    else:
                        start, end = m.start(), m.end()
                        matched = m.group(0).strip()
                    if not matched:
                        continue
                    action = RecommendedAction.MASK if confidence >= 0.85 else RecommendedAction.REVIEW_REQUIRED
                    results.append(
                        DetectionResult(
                            entity_type=entity_type,
                            matched_text=matched,
                            start=start,
                            end=end,
                            language=language,
                            source_detector=self.name,
                            confidence_score=confidence,
                            risk_level=risk,
                            recommended_action=action,
                        )
                    )
            except re.error:
                continue
        return results
