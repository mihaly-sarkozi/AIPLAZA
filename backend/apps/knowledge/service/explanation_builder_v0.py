from __future__ import annotations

from typing import Any


EXPLANATION_BUILDER_VERSION = "explanation_builder_v0"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _append_unique(values: list[str], value: Any) -> None:
    text = _text(value)
    if text and text not in values:
        values.append(text)


def _claim_text(claim: dict[str, Any]) -> str:
    return (
        _text(claim.get("display_claim_text"))
        or _text(claim.get("canonical_claim_text"))
        or _text(claim.get("claim_text"))
        or _text(claim.get("raw_claim_text"))
    )


def _claim_sentence_ids(claim: dict[str, Any]) -> list[str]:
    evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
    ids: list[str] = []
    for value in [
        *_str_list(claim.get("sentence_id")),
        *_str_list(claim.get("sentence_ids")),
        *_str_list(evidence.get("sentence_id")),
        *_str_list(evidence.get("sentence_ids")),
    ]:
        _append_unique(ids, value)
    return ids


def _claim_source_ids(claim: dict[str, Any]) -> list[str]:
    evidence = claim.get("evidence") if isinstance(claim.get("evidence"), dict) else {}
    ids: list[str] = []
    for value in [
        *_str_list(claim.get("source_id")),
        *_str_list(claim.get("source_ids")),
        *_str_list(evidence.get("source_id")),
        *_str_list(evidence.get("source_ids")),
    ]:
        _append_unique(ids, value)
    return ids


def _claim_sentence_texts(claim: dict[str, Any]) -> dict[str, str]:
    ids = _claim_sentence_ids(claim)
    text_by_id: dict[str, str] = {}
    explicit_texts = _str_list(claim.get("sentence_texts"))
    if ids and explicit_texts:
        for index, sentence_id in enumerate(ids):
            if index < len(explicit_texts):
                text_by_id[sentence_id] = explicit_texts[index]
    first_text = _text(claim.get("sentence_text"))
    if first_text and ids:
        text_by_id.setdefault(ids[0], first_text)
    return text_by_id


class ExplanationBuilderV0:
    version = EXPLANATION_BUILDER_VERSION

    def build(
        self,
        *,
        answer_text: str,
        matched_claims: list[dict[str, Any]],
        cited_claim_ids: list[str],
        cited_sentence_ids: list[str],
        cited_source_ids: list[str],
    ) -> dict[str, Any]:
        cited_claim_set = set(cited_claim_ids)
        cited_sentence_set = set(cited_sentence_ids)
        cited_source_set = set(cited_source_ids)
        claims: list[dict[str, Any]] = []
        sentences_by_id: dict[str, dict[str, Any]] = {}
        sources_by_id: dict[str, dict[str, Any]] = {}

        for claim in matched_claims:
            claim_id = _text(claim.get("claim_id"))
            if not claim_id or (cited_claim_set and claim_id not in cited_claim_set):
                continue
            sentence_ids = [item for item in _claim_sentence_ids(claim) if not cited_sentence_set or item in cited_sentence_set]
            source_ids = [item for item in _claim_source_ids(claim) if not cited_source_set or item in cited_source_set]
            text = _claim_text(claim)
            claims.append(
                {
                    "claim_id": claim_id,
                    "claim_text": text,
                    "sentence_ids": sentence_ids,
                    "source_ids": source_ids,
                }
            )

            sentence_texts = _claim_sentence_texts(claim)
            for sentence_id in sentence_ids:
                sentence = sentences_by_id.setdefault(
                    sentence_id,
                    {
                        "sentence_id": sentence_id,
                        "sentence_text": sentence_texts.get(sentence_id, ""),
                        "claim_ids": [],
                        "source_ids": [],
                    },
                )
                if sentence_texts.get(sentence_id) and not sentence.get("sentence_text"):
                    sentence["sentence_text"] = sentence_texts[sentence_id]
                _append_unique(sentence["claim_ids"], claim_id)
                for source_id in source_ids:
                    _append_unique(sentence["source_ids"], source_id)

            for source_id in source_ids:
                source = sources_by_id.setdefault(
                    source_id,
                    {
                        "source_id": source_id,
                        "claim_ids": [],
                        "sentence_ids": [],
                    },
                )
                _append_unique(source["claim_ids"], claim_id)
                for sentence_id in sentence_ids:
                    _append_unique(source["sentence_ids"], sentence_id)

        return {
            "answer_text": _text(answer_text),
            "explanation": {
                "claims": claims,
                "sentences": list(sentences_by_id.values()),
                "sources": list(sources_by_id.values()),
                "builder_version": self.version,
            },
        }


__all__ = ["EXPLANATION_BUILDER_VERSION", "ExplanationBuilderV0"]
