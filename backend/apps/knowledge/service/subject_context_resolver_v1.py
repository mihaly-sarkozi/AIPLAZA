"""Dokumentumon belüli implicit alany átvitel (v1, szigorú feltételekkel).

Csak akkor alkalmaz, ha egyszerre teljesül:
1. az aktuális claim alanya **gyenge** (lásd ``_is_weak_subject``: üres / ``is_bad_subject`` /
   csak idő- vagy általános szó / túl rövid nem-entitás / tárgy-szerű HU -ért farok);
2. van **utolsó erős subject** (explicit, a saját mondat szövegében igazolható): csak ezt lehet
   továbbvinni; új explicit subject **felülírja** a kontextust (más típus is); a horgony legfeljebb
   **2 mondatnyira** lehet a jelenlegi sortól index szerint;
3. a horgony subject **típusa** engedélyezett: person / module / system / software /
   location / account / user (mention + szabályalapú heurisztika, fuzzy nélkül);
4. az aktuális mondat nem vezet be új explicit entitást (mention vagy kezdő propernév);
5–6. a mondat nem kérdés, nem zaj / fragment (ugyanaz a szűrés mint ``ClaimQualityGate``).

Bizonyíték: ``Claim.metadata`` vagy dict claim kulcsai. Opcionális:
``context_subject_sentence_pattern_id`` — ``subject_context_patterns_v1`` illesztés.
"""
from __future__ import annotations

import logging
import re
from dataclasses import replace
from typing import Any, Mapping

from apps.knowledge.domain.claim import Claim
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate
from apps.knowledge.service.claim_sanitizer import is_bad_subject
from apps.knowledge.service.language_rules import fold_text, get_language_rules
from apps.knowledge.service.subject_context_patterns_v1 import match_implicit_subject_sentence_pattern_id


logger = logging.getLogger(__name__)


def _norm_ws(value: str | None) -> str:
    return " ".join((value or "").split())


# Csak időhatároló / „korábban” típusú egyszavas subject (explicit lista).
_WEAK_SUBJECT_PREFIX_FOLD: dict[str, tuple[str, ...]] = {
    "hu": (
        fold_text("korábban"),
        fold_text("korabban"),
        fold_text("előtte"),
        fold_text("elotte"),
        fold_text("később"),
        fold_text("kesobb"),
        fold_text("jelenleg"),
        fold_text("jelenleg is"),
        fold_text("most"),
        fold_text("akkoriban"),
    ),
    "en": (
        fold_text("previously"),
        fold_text("earlier"),
        fold_text("later"),
        fold_text("at that time"),
        fold_text("was inactive"),
        fold_text("is inactive"),
        fold_text("was active"),
        fold_text("is active"),
        fold_text("currently"),
        fold_text("responsible"),
    ),
    "es": (
        fold_text("anteriormente"),
        fold_text("antes"),
        fold_text("luego"),
        fold_text("en ese momento"),
        fold_text("estaba"),
        fold_text("está"),
        fold_text("esta"),
        fold_text("fue"),
        fold_text("era"),
        fold_text("actualmente"),
    ),
}

# Általános névmás / mutató (egész subject = egy token).
_GENERAL_SUBJECT_TOKEN_FOLD = frozenset(
    {
        fold_text("ő"),
        fold_text("it"),
        fold_text("este"),
        fold_text("ez"),
        fold_text("az"),
    }
)


def _is_hu_object_like_subject_tail(*, tokens: list[str], language: str) -> bool:
    """HU: többszavas subject, utolsó token tárgyeset-szerű -ért / -ert farok (object-szerű)."""
    if language != "hu" or len(tokens) < 2:
        return False
    return fold_text(tokens[-1]).endswith("ert")


def _is_weak_subject(subject: str | None, *, language: str) -> bool:
    """Subject pótolható / nem erős: üres, sanitizer szerint rossz, csak idő/általános szó, túl rövid, HU tárgyfarok."""
    s = _norm_ws(subject)
    if not s:
        return True
    s_fold = fold_text(s)
    weak_prefixes = _WEAK_SUBJECT_PREFIX_FOLD.get(language, ())
    if any(s_fold == prefix or s_fold.startswith(prefix + " ") for prefix in weak_prefixes):
        return True
    if is_bad_subject(s, language=language):
        return True
    tokens = [t for t in re.findall(r"[\w\-]+", s, flags=re.UNICODE) if t]
    if not tokens:
        return True
    if len(tokens) == 1:
        tok_f = fold_text(tokens[0])
        if tok_f in _GENERAL_SUBJECT_TOKEN_FOLD:
            return True
        if len(tok_f) <= 2:
            return True
    if _is_hu_object_like_subject_tail(tokens=tokens, language=language):
        return True
    return False


def _subject_evidence_in_sentence(subject: str, sentence_text: str) -> bool:
    sub = _norm_ws(subject)
    if not sub:
        return False
    return sub in _norm_ws(sentence_text)


def _claim_id(claim: Claim | Mapping[str, Any]) -> str:
    if isinstance(claim, Claim):
        return str(claim.id)
    return str(claim.get("claim_id") or claim.get("id") or "")


def _get_predicate(claim: Claim | Mapping[str, Any]) -> str:
    if isinstance(claim, Claim):
        return str(claim.predicate_text or "")
    return str(claim.get("predicate_text") or claim.get("predicate") or "")


def _get_object(claim: Claim | Mapping[str, Any]) -> str:
    if isinstance(claim, Claim):
        return str(claim.object_text or "")
    return str(claim.get("object_text") or "")


def _get_subject(claim: Claim | Mapping[str, Any]) -> str:
    if isinstance(claim, Claim):
        return str(claim.subject_text or "")
    return str(claim.get("subject_text") or "")


def _get_subject_mention_id(claim: Claim | Mapping[str, Any]) -> str | None:
    if isinstance(claim, Claim):
        return str(claim.subject_mention_id) if claim.subject_mention_id else None
    mid = claim.get("subject_mention_id")
    return str(mid) if mid else None


def _get_md(claim: Claim | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(claim, Claim):
        return dict(claim.metadata or {})
    d = dict(claim)
    meta = d.get("metadata")
    out = dict(meta) if isinstance(meta, dict) else {}
    for k in (
        "context_subject_applied",
        "context_subject_source_sentence_id",
        "context_subject_source_claim_id",
        "context_subject_source_subject",
        "context_subject_sentence_pattern_id",
    ):
        if k in d and k not in out:
            out[k] = d[k]
    return out


def _set_subject(claim: Claim | Mapping[str, Any], subject: str) -> Claim | dict[str, Any]:
    if isinstance(claim, Claim):
        return replace(claim, subject_text=subject, subject_mention_id=None)
    out = dict(claim)
    out["subject_text"] = subject
    return out


_PREDICATE_DISPLAY_LOWER_FOLD = frozenset(
    {
        fold_text("Was inactive"),
        fold_text("Was active"),
        fold_text("Is inactive"),
        fold_text("Is active"),
        fold_text("Estaba inactiva"),
        fold_text("Estaba inactivo"),
        fold_text("Está activa"),
        fold_text("Esta activa"),
    }
)

_ES_ROLE_AT_ORG_RE = re.compile(
    r"^\s*(?P<role>responsable(?:\s+de\s+.+?)?)\s+en\s+(?P<org>.+?)\s*$",
    flags=re.IGNORECASE | re.UNICODE,
)


def _lower_initial(value: str) -> str:
    return value[:1].lower() + value[1:] if value else value


def _normalize_predicate_display_after_context(claim: Claim | Mapping[str, Any]) -> Claim | dict[str, Any]:
    """Csak kijelzési normalizálás subject context apply után: mondatkezdő nagybetűt kisbetűsíti célzott state phrase-eknél."""
    pred = _get_predicate(claim)
    if not pred or fold_text(pred) not in _PREDICATE_DISPLAY_LOWER_FOLD:
        return claim
    updated_pred = _lower_initial(pred)
    if updated_pred == pred:
        return claim
    if isinstance(claim, Claim):
        return replace(claim, predicate_text=updated_pred)
    out = dict(claim)
    if "predicate_text" in out:
        out["predicate_text"] = updated_pred
    else:
        out["predicate"] = updated_pred
    return out


def _normalize_es_role_claim(claim: Claim | Mapping[str, Any], *, language: str) -> Claim | dict[str, Any]:
    if language != "es":
        return claim
    predicate = _get_predicate(claim)
    object_text = _get_object(claim)
    if fold_text(predicate) != "es" or not object_text:
        return claim
    match = _ES_ROLE_AT_ORG_RE.match(object_text)
    if match is None:
        return claim
    role = _norm_ws(match.group("role"))
    org = _norm_ws(match.group("org"))
    if not role or not org:
        return claim
    if isinstance(claim, Claim):
        return replace(claim, predicate_text=f"{role} en", object_text=org)
    out = dict(claim)
    if "predicate_text" in out:
        out["predicate_text"] = f"{role} en"
    else:
        out["predicate"] = f"{role} en"
    out["object_text"] = org
    return out


def _attach_context_meta(
    claim: Claim | dict[str, Any],
    *,
    applied: bool,
    source_sentence_id: str | None,
    source_claim_id: str | None,
    reason: str,
    source_subject: str | None = None,
    sentence_pattern_id: str | None = None,
) -> Claim | dict[str, Any]:
    fields: dict[str, Any] = {
        "context_subject_applied": applied,
        "context_subject_source_sentence_id": source_sentence_id,
        "context_subject_source_claim_id": source_claim_id,
        "context_subject_reason": reason,
    }
    if source_subject:
        fields["context_subject_source_subject"] = source_subject
    if sentence_pattern_id:
        fields["context_subject_sentence_pattern_id"] = sentence_pattern_id
    if isinstance(claim, Claim):
        return replace(claim, metadata={**(claim.metadata or {}), **fields})
    out = dict(claim)
    out.update(fields)
    return out


_ALLOWED_CARRY_KINDS = frozenset(
    {"person", "organization", "module", "system", "software", "location", "account", "user"}
)
_RESPONSIBILITY_CARRY_KINDS = frozenset({"person"})
_STATE_CARRY_KINDS = frozenset({"location", "system", "module", "software"})

_RESPONSIBILITY_HINTS = frozenset(
    {
        fold_text("responsible"),
        fold_text("responsable"),
        fold_text("felelt"),
        fold_text("felel"),
        fold_text("fue responsable"),
    }
)
_STATE_HINTS = frozenset(
    {
        fold_text("inactive"),
        fold_text("active"),
        fold_text("was inactive"),
        fold_text("is inactive"),
        fold_text("was active"),
        fold_text("is active"),
        fold_text("inactiva"),
        fold_text("inactivo"),
        fold_text("activa"),
        fold_text("activo"),
        fold_text("estaba inactiva"),
        fold_text("está activa"),
        fold_text("esta activa"),
        fold_text("aktív"),
        fold_text("aktiv"),
        fold_text("inaktív"),
        fold_text("inaktiv"),
        fold_text("működik"),
        fold_text("mukodik"),
    }
)

_ACCOUNT_FOLD = frozenset(
    {
        fold_text("account"),
        fold_text("cuenta"),
        fold_text("fiok"),
        fold_text("fiók"),
    }
)

_USER_FOLD = frozenset(
    {
        fold_text("user"),
        fold_text("usuario"),
        fold_text("felhasználó"),
        fold_text("felhasznalo"),
    }
)

_SYSTEM_TOKEN_FOLD = frozenset(
    {
        fold_text("rendszer"),
        fold_text("system"),
        fold_text("sistema"),
    }
)

_INTRODUCER_MENTION_TYPES = frozenset(
    {"person", "organization", "company", "software", "module", "feature", "location", "account", "user"}
)

_LEADING_PROPER_HU = re.compile(
    r"^([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+(?:\s+[A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+)+)\b"
)
_LEADING_PROPER_LATIN = re.compile(r"^([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+)+)\b")


def _mention_surface(m: Any) -> str:
    if isinstance(m, dict):
        return str(m.get("surface_text") or m.get("text_content") or "")
    return str(getattr(m, "surface_text", None) or getattr(m, "text_content", "") or "")


def _mention_type(m: Any) -> str:
    if isinstance(m, dict):
        return str(m.get("mention_type") or "")
    return str(getattr(m, "mention_type", "") or "")


def _mention_start(m: Any) -> int:
    if isinstance(m, dict):
        return int(m.get("char_start") or 0)
    return int(getattr(m, "char_start", 0) or 0)


def _mention_id(m: Any) -> str:
    if isinstance(m, dict):
        return str(m.get("mention_id") or m.get("id") or "")
    return str(getattr(m, "mention_id", None) or getattr(m, "id", "") or "")


def _find_mention(mentions: list[Any], mention_id: str | None, subject: str) -> Any | None:
    if mention_id:
        for m in mentions:
            if _mention_id(m) == str(mention_id):
                return m
    sub_f = fold_text(_norm_ws(subject))
    if not sub_f:
        return None
    best: Any | None = None
    for m in mentions:
        sf = fold_text(_mention_surface(m))
        if sf == sub_f:
            return m
        if sf and (sf in sub_f or sub_f in sf):
            best = m
    return best


def _map_mention_type_to_kind(mt: str) -> str | None:
    key = str(mt or "").strip().lower()
    if key == "person":
        return "person"
    if key in {"organization", "company"}:
        return "organization"
    if key in {"module", "feature"}:
        return "module"
    if key == "software":
        return "software"
    if key == "location":
        return "location"
    return None


def _infer_subject_kind(claim: Claim | Mapping[str, Any], row: Mapping[str, Any], *, language: str) -> str | None:
    mentions = list(row.get("mentions") or [])
    subj = _get_subject(claim)
    subj_f = fold_text(subj)
    tokens = [fold_text(t) for t in re.findall(r"[\w\-]+", subj, flags=re.UNICODE) if t]

    m = _find_mention(mentions, _get_subject_mention_id(claim), subj)
    if m is not None:
        mk = _map_mention_type_to_kind(_mention_type(m))
        if mk is not None:
            return mk

    if subj_f in _ACCOUNT_FOLD or any(t in _ACCOUNT_FOLD for t in tokens):
        return "account"
    if subj_f in _USER_FOLD or any(t in _USER_FOLD for t in tokens):
        return "user"
    if any(t in _SYSTEM_TOKEN_FOLD for t in tokens):
        return "system"

    rules = get_language_rules(language)
    mod_kw = {fold_text(x) for x in rules.module_keywords}
    feat_kw = {fold_text(x) for x in rules.feature_keywords}
    sw_kw = {fold_text(x) for x in rules.software_keywords}
    loc_kw = {fold_text(x) for x in rules.location_keywords}
    if any(t in mod_kw or t in feat_kw for t in tokens):
        return "module"
    if any(t in sw_kw for t in tokens):
        return "software"
    if any(t in loc_kw for t in tokens):
        return "location"

    if language == "hu":
        if _LEADING_PROPER_HU.match(_norm_ws(subj)):
            return "person"
    else:
        if _LEADING_PROPER_LATIN.match(_norm_ws(subj)):
            return "person"

    return None


# A horgony utolsó explicit mondatának sorindexe és a jelenlegi sor között legfeljebb ennyi.
_MAX_CARRY_ROW_DISTANCE = 2


def _first_verified_strong_in_row(
    row_dict: dict[str, Any],
    claims: list[Any],
    *,
    language: str,
) -> tuple[str, str, str, str] | None:
    """Első explicit erős subject a mondatban: szövegben igazolt, típus engedélyezett.

    Csak ilyen frissíti az „utolsó erős subject'' állapotot; láncolt meta nélkül.
    """
    text = str(row_dict.get("text") or "")
    sid = str(row_dict.get("sentence_id") or "")
    for claim in claims:
        subj = _get_subject(claim)
        if _is_weak_subject(subj, language=language):
            continue
        if not _subject_evidence_in_sentence(subj, text):
            continue
        kind = _infer_subject_kind(claim, row_dict, language=language)
        if kind not in _ALLOWED_CARRY_KINDS:
            continue
        cid = _claim_id(claim)
        if not cid:
            continue
        return (_norm_ws(subj), sid, cid, kind)
    return None


def _overlap_fold(a: str, b: str) -> bool:
    af = fold_text(_norm_ws(a))
    bf = fold_text(_norm_ws(b))
    if not af or not bf:
        return False
    return af == bf or af in bf or bf in af


def _new_explicit_entity_blocks(
    text: str,
    *,
    language: str,
    anchor_subj: str,
    mentions: list[Any],
) -> tuple[bool, str | None]:
    anchor_f = fold_text(_norm_ws(anchor_subj))
    if mentions:
        sorted_ms = sorted(mentions, key=_mention_start)
        for m in sorted_ms:
            mt = _mention_type(m)
            if mt not in _INTRODUCER_MENTION_TYPES:
                continue
            surf = _mention_surface(m)
            if not _subject_evidence_in_sentence(surf, text):
                continue
            if _overlap_fold(surf, anchor_subj):
                continue
            # Spec: a mention.char_start a globális dokumentum-pozíció, nem mondat-relatív.
            # A mondaton belüli pozíciót find()-del állapítjuk meg, hogy a "near_start"
            # blokkolás megfelelően aktiválódjon (B. carryover guard).
            sentence_relative_pos = _norm_ws(text).find(_norm_ws(surf))
            if sentence_relative_pos < 0:
                sentence_relative_pos = 0
            if sentence_relative_pos <= 20 or sentence_relative_pos <= max(12, len(text) // 3):
                return True, "new_explicit_entity_mention_near_start"
        return False, None

    t = _norm_ws(text)
    if language == "hu":
        m = _LEADING_PROPER_HU.match(t)
    else:
        m = _LEADING_PROPER_LATIN.match(t)
    if not m:
        return False, None
    lead = m.group(1).strip()
    if anchor_f and fold_text(lead) == anchor_f:
        return False, None
    return True, "leading_proper_name_differs_from_anchor"


def _folded_claim_context(claim: Claim | Mapping[str, Any], sentence_text: str) -> str:
    return " ".join(
        part
        for part in (
            fold_text(_get_subject(claim)),
            fold_text(_get_predicate(claim)),
            fold_text(_get_object(claim)),
            fold_text(sentence_text),
        )
        if part
    )


def _has_any_hint(context: str, hints: frozenset[str]) -> bool:
    return any(hint and hint in context for hint in hints)


def _compatible_anchor_kind(
    anchor_kind: str,
    claim: Claim | Mapping[str, Any],
    *,
    sentence_text: str,
) -> bool:
    """Célmondat-típus szerinti carry kompatibilitás.

    responsibility → person; state/active/inactive/működik → location/system/module/software.
    Ismeretlen cél esetén a korábbi, szigorú anchor-kind whitelist marad érvényben.
    """
    ctx = _folded_claim_context(claim, sentence_text)
    if _has_any_hint(ctx, _RESPONSIBILITY_HINTS):
        return anchor_kind in _RESPONSIBILITY_CARRY_KINDS
    if _has_any_hint(ctx, _STATE_HINTS):
        return anchor_kind in _STATE_CARRY_KINDS
    return anchor_kind in _ALLOWED_CARRY_KINDS


class SubjectContextResolverV1:
    """Mondatsorrendű, dokumentum-lokális implicit alany feloldás."""

    version: str = "subject_context_resolver_v1"

    def __init__(self) -> None:
        self._sentence_gate = ClaimQualityGate()

    def resolve_claims(self, sentence_claims: list) -> list:
        rows: list[dict[str, Any]] = [dict(r) for r in sentence_claims]
        rows.sort(key=lambda r: (int(r.get("order_index") or 0), str(r.get("sentence_id") or "")))

        # (subject, sentence_id, claim_id, kind, anchor_row_index) — csak szövegben igazolt explicit erős subject
        last_strong: tuple[str, str, str, str, int] | None = None

        for i, row in enumerate(rows):
            sentence_id = str(row.get("sentence_id") or "")
            text = str(row.get("text") or "")
            language = str(row.get("language") or "en").strip().lower() or "en"
            claims_in = list(row.get("claims") or [])
            mentions = list(row.get("mentions") or [])

            ok, bad_reason = self._sentence_gate.should_process_sentence(text, language)
            anchor: tuple[str, str, str, str] | None = None
            if ok and last_strong is not None:
                _subj_a, _sid_a, _cid_a, _kind_a, anchor_row_i = last_strong
                if i - anchor_row_i <= _MAX_CARRY_ROW_DISTANCE:
                    anchor = (_subj_a, _sid_a, _cid_a, _kind_a)

            updated_claims: list[Any] = []
            for claim in claims_in:
                updated = self._resolve_single_claim(
                    claim,
                    language=language,
                    sentence_text=text,
                    mentions=mentions,
                    sentence_ok=ok,
                    sentence_block_reason=bad_reason,
                    anchor=anchor,
                    sentence_id=sentence_id,
                )
                updated = _normalize_es_role_claim(updated, language=language)
                updated_claims.append(updated)

            row["claims"] = updated_claims

            refreshed = _first_verified_strong_in_row(row, updated_claims, language=language)
            if refreshed is not None:
                last_strong = (*refreshed, i)

        return rows

    def _resolve_single_claim(
        self,
        claim: Any,
        *,
        language: str,
        sentence_text: str,
        mentions: list[Any],
        sentence_ok: bool,
        sentence_block_reason: str | None,
        anchor: tuple[str, str, str, str] | None,
        sentence_id: str,
    ) -> Any:
        subj = _get_subject(claim)
        replaceable = _is_weak_subject(subj, language=language)
        pattern_id = match_implicit_subject_sentence_pattern_id(sentence_text, language)

        if not sentence_ok:
            reason = f"sentence_not_eligible_for_carry:{sentence_block_reason or 'unknown'}"
            return _attach_context_meta(
                claim,
                applied=False,
                source_sentence_id=None,
                source_claim_id=None,
                reason=reason,
                sentence_pattern_id=pattern_id,
            )

        if anchor is None:
            return _attach_context_meta(
                claim,
                applied=False,
                source_sentence_id=None,
                source_claim_id=None,
                reason="no_strong_anchor_in_previous_two_sentences",
                sentence_pattern_id=pattern_id,
            )

        anchor_subj, anchor_sid, anchor_cid, anchor_kind = anchor

        if not replaceable:
            if _norm_ws(subj) == _norm_ws(anchor_subj):
                return _attach_context_meta(
                    claim,
                    applied=False,
                    source_sentence_id=anchor_sid,
                    source_claim_id=anchor_cid,
                    reason="explicit_subject_matches_carry_anchor",
                    sentence_pattern_id=pattern_id,
                )
            return _attach_context_meta(
                claim,
                applied=False,
                source_sentence_id=None,
                source_claim_id=None,
                reason="explicit_subject_kept",
                sentence_pattern_id=pattern_id,
            )

        if not _compatible_anchor_kind(anchor_kind, claim, sentence_text=sentence_text):
            return _attach_context_meta(
                claim,
                applied=False,
                source_sentence_id=None,
                source_claim_id=None,
                reason=f"incompatible_subject_context:{anchor_kind}",
                sentence_pattern_id=pattern_id,
            )

        blocked, block_reason = _new_explicit_entity_blocks(
            sentence_text, language=language, anchor_subj=anchor_subj, mentions=mentions
        )
        if blocked:
            return _attach_context_meta(
                claim,
                applied=False,
                source_sentence_id=None,
                source_claim_id=None,
                reason=block_reason or "blocked_new_explicit_entity",
                sentence_pattern_id=pattern_id,
            )

        old_subj = _get_subject(claim)
        carried = _set_subject(claim, anchor_subj)
        carried = _normalize_predicate_display_after_context(carried)
        apply_reason = "weak_subject_override" if _norm_ws(old_subj) else "implicit_subject"
        logger.debug(
            "[SUBJECT CONTEXT]\napplied=true\nsentence_id=%s\nold_subject=%s\nnew_subject=%s\nsource_sentence_id=%s\nreason=%s",
            sentence_id,
            (old_subj or "").replace("\n", " ").strip(),
            (anchor_subj or "").replace("\n", " ").strip(),
            anchor_sid,
            apply_reason,
        )
        return _attach_context_meta(
            carried,
            applied=True,
            source_sentence_id=anchor_sid,
            source_claim_id=anchor_cid,
            reason=apply_reason,
            source_subject=anchor_subj,
            sentence_pattern_id=pattern_id,
        )


__all__ = ["SubjectContextResolverV1"]
