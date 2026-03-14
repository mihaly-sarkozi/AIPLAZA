# tests/integration/test_pii_pipeline.py
"""
PII szűrés tesztek: a pipeline kiszűri-e a megadott személyes adat példákat.
Erősség: weak = email, telefon; medium = + IBAN, rendszám, dátum, ügyfél/szerz/ticket, név; strong = + szervezet, hely.
"""
from __future__ import annotations

import pytest

from apps.knowledge.pii.pipeline import filter_pii, apply_pii_replacements
from apps.knowledge.pii.policy import entities_for_sensitivity

pytestmark = [pytest.mark.integration, pytest.mark.must_pass]


def _has_match(matches: list, entity_type: str, value: str | None = None) -> bool:
    """Van-e olyan találat, ahol a típus egyezik és (ha megadott) az érték egyezik vagy tartalmazza."""
    for _s, _e, dtype, val in matches:
        if dtype != entity_type:
            continue
        if value is None:
            return True
        if val == value or (value in val) or (val in value):
            return True
    return False


def _any_match_contains(matches: list, entity_type: str, substring: str) -> bool:
    """Van-e adott típusú találat, ami tartalmazza a substringet (pl. email része)."""
    for _s, _e, dtype, val in matches:
        if dtype == entity_type and substring in val:
            return True
    return False


# --- 1. Közvetlen személyes adatok ---


class TestKozvetlenSzemelyesAdatok:
    """Teljes név, becenév, születési dátum, lakcím, email, telefonszám."""

    @pytest.mark.release_acceptance
    @pytest.mark.parametrize("text,expected_value", [
        ("Ügyfél: Kovács Anna érkezett.", "Kovács Anna"),
        ("John Smith hívta a supportot.", "John Smith"),
    ])
    def test_teljes_nev_kiszurve_medium(self, text: str, expected_value: str):
        """Név: Keresztnév Vezetéknév – medium erősségnél kiszűri."""
        matches = filter_pii(text, "medium")
        assert _has_match(matches, "név", expected_value), (
            f"Név nem került kiszűrésre: {expected_value!r}, találatok: {[(m[2], m[3]) for m in matches]}"
        )

    def test_email_kiszurve(self):
        """email: valami@domain.tld – weak/medium/strong mind kiszűri."""
        text = "Írj nekem: anna.kovacs@example.com vagy anna.kovacs@ceg.hu"
        for sensitivity in ("weak", "medium", "strong"):
            matches = filter_pii(text, sensitivity)
            assert _any_match_contains(matches, "email", "anna.kovacs@example.com"), (
                f"Email nem került kiszűrésre {sensitivity}: {[(m[2], m[3]) for m in matches]}"
            )
            assert _any_match_contains(matches, "email", "@"), (
                f"Legalább egy email kiszűrve kell legyen {sensitivity}"
            )

    @pytest.mark.parametrize("text", [
        "+36 30 123 4567",
        "+36 30 123 4567 hívás",
        "Telefon: 06 30 123 4567",
        "Spanyol: +34 612 345 678",
    ])
    def test_telefonszam_kiszurve(self, text: str):
        """telefon: +orszagkod körzetszám szám – weak/medium kiszűri."""
        matches = filter_pii(text, "weak")
        assert any(m[2] == "telefonszám" for m in matches), (
            f"Telefonszám nem került kiszűrésre: {text!r}, találatok: {[m[3] for m in matches]}"
        )

    @pytest.mark.release_acceptance
    @pytest.mark.parametrize("text", [
        "Született: 1992-03-14.",
        "Dátum: 1992.03.14",
        "Dátum: 14/03/1992",
        "1992. 03. 14.",  # magyar szóközös forma
        "Született: 1992. 03. 14.",  # születési dátum kontextussal
        "date of birth: 14/03/1992",
    ])
    def test_szuletesi_datum_kiszurve_medium(self, text: str):
        """Dátum/születési dátum: általános → 'dátum', Született:/dob kontextus → 'születési_dátum'; medium kiszűri."""
        matches = filter_pii(text, "medium")
        assert any(m[2] in ("dátum", "születési_dátum") for m in matches), (
            f"Dátum nem került kiszűrésre: {text!r}, találatok: {[(m[2], m[3]) for m in matches]}"
        )

    @pytest.mark.release_acceptance
    def test_datum_vs_szuletesi_datum_szetvalasztva(self):
        """Dátum vs születési dátum: kontextus nélküli → 'dátum', Született:/dob → 'születési_dátum'."""
        matches_gen = filter_pii("Esedék: 2024-06-15.", "medium")
        assert any(m[2] == "dátum" for m in matches_gen), "Általános dátum → legacy 'dátum'"
        matches_dob = filter_pii("Született: 1992-03-14.", "medium")
        assert any(m[2] == "születési_dátum" for m in matches_dob), "Született kontextus → legacy 'születési_dátum'"

    @pytest.mark.release_acceptance
    def test_nev_es_email_egy_szovegben(self):
        """Kovács Anna + email + telefon + lakcím – mind kiszűrve (medium)."""
        text = "Kovács Anna, anna.kovacs@example.com, +36 30 123 4567. Lakcím: 1123 Budapest, Alkotás utca 15."
        matches = filter_pii(text, "medium")
        assert _has_match(matches, "név", "Kovács Anna")
        assert _any_match_contains(matches, "email", "anna.kovacs@example.com")
        assert any(m[2] == "telefonszám" for m in matches)
        assert _any_match_contains(matches, "cím", "1123 Budapest") or any(m[2] == "cím" for m in matches)

    @pytest.mark.release_acceptance
    def test_lakcim_kiszurve_medium(self):
        """Lakcím: 1123 Budapest, Alkotás utca 15. – medium erősségnél kiszűri (cím regex)."""
        text = "Lakcím: 1123 Budapest, Alkotás utca 15."
        matches = filter_pii(text, "medium")
        assert any(m[2] == "cím" for m in matches), (
            f"Cím nem került kiszűrésre: {[(m[2], m[3]) for m in matches]}"
        )
        assert _any_match_contains(matches, "cím", "1123 Budapest") or _any_match_contains(
            matches, "cím", "Alkotás"
        )


# --- 2. Erős személyazonosítók ---


class TestErosSzemelyazonositok:
    """Ügyfélazonosító, prefixelt azonosítók – medium már szűri egy részt."""

    def test_ugyfelazonosito_UGY_prefix(self):
        """Ügyfélazonosító: UGY-12345, UGYFEL-123, CLIENT-999."""
        text = "Ügyfél: UGY-12345 és CLIENT-99124."
        matches = filter_pii(text, "medium")
        assert _any_match_contains(matches, "ügyfélazonosító", "UGY") or _any_match_contains(
            matches, "ügyfélazonosító", "CLIENT"
        ), f"Ügyfélazonosító kellett volna: {[(m[2], m[3]) for m in matches]}"

    def test_ugyfelazonosito_hash_szam(self):
        """#12345678 formátum."""
        text = "Azonosító: #12345678"
        matches = filter_pii(text, "medium")
        assert any(m[2] == "ügyfélazonosító" for m in matches), (
            f"# azonosító kellett volna: {[(m[2], m[3]) for m in matches]}"
        )

    @pytest.mark.release_acceptance
    def test_ticket_id(self):
        """TKT-, TICKET-, JIRA- prefix."""
        text = "Ticket JIRA-12345 megnyitva. TKT-9999."
        matches = filter_pii(text, "medium")
        assert any(m[2] == "ticket_id" for m in matches), (
            f"Ticket ID kellett volna: {[(m[2], m[3]) for m in matches]}"
        )

    @pytest.mark.release_acceptance
    def test_szerzodeszam(self):
        """Szerződésszám: SZ-123, Szerződés-456."""
        text = "Szerződés SZ-123456 aláírva. Szerződés-7890."
        matches = filter_pii(text, "medium")
        assert any(m[2] == "szerződésszám" for m in matches), (
            f"Szerződésszám kellett volna: {[(m[2], m[3]) for m in matches]}"
        )


# --- 3. Pénzügyi adatok ---


class TestPenzugyiAdatok:
    """IBAN, bankszámla (regex csak IBAN), kártyaszám jelenleg nincs."""

    def test_iban_kiszurve_medium(self):
        """IBAN: HU42 1177 3016 1111 1018 0000 0000 – medium kiszűri."""
        text = "IBAN: HU42 1177 3016 1111 1018 0000 0000"
        matches = filter_pii(text, "medium")
        assert any(m[2] == "iban" for m in matches), (
            f"IBAN kellett volna kiszűrve: {[(m[2], m[3]) for m in matches]}"
        )

    def test_iban_szokozokkel(self):
        """IBAN szóköz nélkül is detektálódjon (regex opcionális szóköz)."""
        text = "HU42117730161111101800000000"
        matches = filter_pii(text, "medium")
        assert any(m[2] == "iban" for m in matches), (
            f"IBAN szóköz nélkül kellett volna detektálódjon; találatok: {[(m[2], m[3]) for m in matches]}"
        )


# --- 4–5. Online / céges (email, telefon már tesztelve) ---
# IP, cookie, session: jelenleg nincs recognizer → teszt csak dokumentálja


# --- 6. Járműadatok ---


class TestJarmuAdatok:
    """Rendszám: ABC-123, magyar új formátum – medium kiszűri."""

    def test_rendszam_abc_123(self):
        """Rendszám: ABC-123 (magyar régi)."""
        text = "Jármű rendszám: ABC-123"
        matches = filter_pii(text, "medium")
        assert _has_match(matches, "rendszám", "ABC-123") or any(
            m[2] == "rendszám" for m in matches
        ), f"Rendszám kellett volna: {[(m[2], m[3]) for m in matches]}"

    def test_rendszam_uj_hu(self):
        """Magyar új: 2 betű 2 szám 2 betű 2 szám."""
        text = "Rendszám: AB 12 CD 34"
        matches = filter_pii(text, "medium")
        assert any(m[2] == "rendszám" for m in matches), (
            f"Rendszám (új forma) kellett volna: {[(m[2], m[3]) for m in matches]}"
        )


# --- Technikai azonosítók (VIN, IMEI, MAC) – pii_gdpr adapter ---


def test_vin_imei_mac_detektalva_legacy_adapteren_keresztul():
    """VIN, IMEI, MAC – pii_gdpr adapteren keresztül; mindhárom típus és konkrét érték detektálódik."""
    text = "VIN: WVWZZZ1JZXW000001. IMEI: 490154203237518. MAC: 00:1A:2B:3C:4D:5E"
    matches = filter_pii(text, "medium")
    by_type = {}
    for _s, _e, dtype, val in matches:
        by_type.setdefault(dtype, []).append(val)
    assert any("WVWZZZ1JZXW000001" in (v or "") for v in by_type.get("vin", [])), (
        f"VIN WVWZZZ1JZXW000001 detektálódjon; találatok: {[(m[2], m[3]) for m in matches]}"
    )
    assert any("490154203237518" in (v or "") for v in by_type.get("imei", [])), (
        f"IMEI 490154203237518 detektálódjon; találatok: {[(m[2], m[3]) for m in matches]}"
    )
    assert any("00:1A:2B:3C:4D:5E" in (v or "") for v in by_type.get("mac_cím", [])), (
        f"MAC 00:1A:2B:3C:4D:5E detektálódjon; találatok: {[(m[2], m[3]) for m in matches]}"
    )
    assert len(matches) >= 2, "Legalább két találat (VIN, IMEI, MAC közül)"


# --- Policy és replace ---


class TestPolicyEsReplace:
    """Policy erősség és apply_pii_replacements."""

    @pytest.mark.release_acceptance
    def test_weak_csak_email_telefon(self):
        """Weak: csak email és telefonszám engedélyezett."""
        allowed = entities_for_sensitivity("weak")
        assert "email" in allowed
        assert "telefonszám" in allowed
        assert "név" not in allowed
        assert "iban" not in allowed

    @pytest.mark.release_acceptance
    def test_medium_tartalmazza_nevet(self):
        """Medium: név, iban, rendszám, dátum, születési_dátum, ügyfél, szerződés, ticket is."""
        allowed = entities_for_sensitivity("medium")
        assert "név" in allowed
        assert "iban" in allowed
        assert "rendszám" in allowed
        assert "dátum" in allowed
        assert "születési_dátum" in allowed

    @pytest.mark.release_acceptance
    def test_strong_tartalmazza_szervezet_helyet(self):
        """Strong: szervezet, hely is (NER)."""
        allowed = entities_for_sensitivity("strong")
        assert "szervezet" in allowed
        assert "hely" in allowed

    @pytest.mark.release_acceptance
    def test_apply_pii_replacements_helyettesit(self):
        """apply_pii_replacements: standard placeholders [EMAIL_ADDRESS], [PERSON_NAME]; név és email helyettesítve."""
        text = "Ügyfél Kovács Anna, anna@example.com."
        matches = filter_pii(text, "medium")
        assert len(matches) >= 1
        refs = [f"ref{i}" for i in range(len(matches))]
        result = apply_pii_replacements(text, matches, refs)
        assert "anna@example.com" not in result
        assert "[EMAIL_ADDRESS]" in result
        # Név is kiszűrve (legacy fallback vagy NER), ha van név találat
        name_matches = [m for m in matches if m[2] == "név"]
        if name_matches:
            assert "Kovács Anna" not in result
            assert "[PERSON_NAME]" in result


# --- Nem (még) implementált típusok – dokumentációs tesztek (xfail) ---


@pytest.mark.expected_fail_not_implemented
class TestNemImplementaltTipusok:
    """
    Ezekre jelenleg nincs (vagy korlátozott) recognizer; xfail: dokumentáljuk,
    hogy a pipeline nem dob hibát; implementáláskor a teszt átírható és xfail eltávolítva.
    """

    def test_becenev_felhasznalonev_nem_szurodik(self):
        """becenév/felhasználónév pl. annakovacs92 – nincs recognizer; when implemented assert entity."""
        text = "User: annakovacs92"
        matches = filter_pii(text, "medium")
        assert isinstance(matches, list)
        assert all(len(m) == 4 for m in matches)
        assert not any(m[2] in ("felhasználónév", "becenév") for m in matches), "When implemented: expect one of these types"

    def test_taj_ado_azonosito_nincs(self):
        """TAJ, adóazonosító – detected as személyi_azonosító / adóazonosító (document_identifiers_recognizer)."""
        text = "TAJ: 123 456 789. Adóazonosító: 12345678-1-12."
        matches = filter_pii(text, "medium")
        assert isinstance(matches, list)
        types = {m[2] for m in matches}
        assert "személyi_azonosító" in types or "adóazonosító" in types, (
            "When TAJ/adó support is added, expect at least one of these types."
        )

    def test_bankkartya_szam_nincs(self):
        """Bankkártya: 4111 1111 1111 1111 – nincs/korlátolt recognizer; pipeline nem dob hibát."""
        text = "Kártya: 4111 1111 1111 1111"
        matches = filter_pii(text, "medium")
        assert isinstance(matches, list)
        # Not yet required: kártyaszám may or may not be in matches
        for _s, _e, dtype, _v in matches:
            assert isinstance(dtype, str)

    @pytest.mark.release_acceptance
    def test_ip_cim_detected_as_entity(self):
        """IP: 192.168.1.10 → ip_cím entity (pii_gdpr implements)."""
        text = "IP: 192.168.1.10"
        matches = filter_pii(text, "medium")
        assert isinstance(matches, list)
        assert all(len(m) == 4 and isinstance(m[2], str) for m in matches)
        assert any(m[2] == "ip_cím" for m in matches), f"Expected ip_cím in {[(m[2], m[3]) for m in matches]}"

    def test_gps_koordinata_nincs(self):
        """GPS: 47.4979, 19.0402 – nincs recognizer; xfail until implemented."""
        text = "Pozíció: 47.4979, 19.0402"
        matches = filter_pii(text, "medium")
        assert isinstance(matches, list)
        assert all(len(m) == 4 for m in matches)
        types = {m[2] for m in matches}
        # When GPS recognizer exists: expect gps/latitude/longitude; today expect none
        assert "gps" in types or "latitude" in types or "longitude" in types or len(types) == 0
