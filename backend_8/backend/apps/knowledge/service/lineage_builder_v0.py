from __future__ import annotations

from typing import Any


LINEAGE_BUILDER_VERSION = "lineage_builder_v0"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _append_unique(items: list[str], value: Any) -> None:
    text = _text(value)
    if text and text not in items:
        items.append(text)


def _claim_id(claim: dict[str, Any]) -> str:
    return _text(claim.get("claim_id"))


def _claim_text(claim: dict[str, Any]) -> str:
    return (
        _text(claim.get("display_claim_text"))
        or _text(claim.get("canonical_claim_text"))
        or _text(claim.get("claim_text"))
        or " ".join(part for part in [_text(claim.get("subject")), _text(claim.get("predicate")), _text(claim.get("object"))] if part)
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


def _technical_entity_id(profile: dict[str, Any]) -> str:
    for key in ("technical_entity_id", "selected_candidate_id", "source_candidate_entity_id", "local_entity_id"):
        value = _text(profile.get(key))
        if value:
            return f"technical_entity:{value}"
    profile_id = _text(profile.get("profile_id"))
    return f"technical_entity:{profile_id or _text(profile.get('canonical_key')) or 'unknown'}"


class LineageBuilderV0:
    version = LINEAGE_BUILDER_VERSION

    def __init__(self) -> None:
        self._nodes: dict[str, dict[str, Any]] = {}

    def _node(self, node_id: str, node_type: str, **metadata: Any) -> dict[str, Any]:
        node = self._nodes.setdefault(
            node_id,
            {
                "id": node_id,
                "type": node_type,
                "parent_ids": [],
                "child_ids": [],
                "metadata": {},
            },
        )
        node["metadata"].update({key: value for key, value in metadata.items() if value not in (None, "", [])})
        return node

    def _edge(self, parent_id: str, child_id: str) -> None:
        parent = self._nodes.get(parent_id)
        child = self._nodes.get(child_id)
        if parent is None or child is None:
            return
        _append_unique(parent["child_ids"], child_id)
        _append_unique(child["parent_ids"], parent_id)

    def build(self, *, global_profiles: list[dict[str, Any]], retrieval_chunks: list[dict[str, Any]]) -> dict[str, Any]:
        self._nodes = {}
        chunks_by_profile_id = {_text(chunk.get("profile_id")): chunk for chunk in retrieval_chunks if _text(chunk.get("profile_id"))}

        for profile in global_profiles:
            if not isinstance(profile, dict):
                continue
            profile_id = _text(profile.get("profile_id"))
            if not profile_id:
                continue
            technical_id = _technical_entity_id(profile)
            self._node(technical_id, "technical_entity", entity_name=profile.get("entity_name"), entity_type=profile.get("entity_type"))
            self._node(profile_id, "global_profile", entity_name=profile.get("entity_name"), canonical_key=profile.get("canonical_key"))
            self._edge(technical_id, profile_id)

            chunk = chunks_by_profile_id.get(profile_id)
            if chunk is not None:
                chunk_id = _text(chunk.get("retrieval_chunk_id")) or f"retrieval_chunk:{profile_id}"
                self._node(chunk_id, "retrieval_chunk", profile_id=profile_id, entity_name=chunk.get("entity_name"))
                self._edge(profile_id, chunk_id)

            for claim in profile.get("claims") or []:
                if not isinstance(claim, dict):
                    continue
                claim_id = _claim_id(claim)
                if not claim_id:
                    continue
                sentence_ids = _claim_sentence_ids(claim)
                source_ids = _claim_source_ids(claim)
                claim_node_id = f"claim:{claim_id}"
                self._node(
                    claim_node_id,
                    "claim",
                    claim_id=claim_id,
                    claim_text=_claim_text(claim),
                    claim_status=claim.get("claim_status") or claim.get("status"),
                    profile_id=profile_id,
                )
                self._edge(claim_node_id, technical_id)
                if not sentence_ids:
                    for source_id in source_ids:
                        source_node_id = f"source:{source_id}"
                        self._node(source_node_id, "source", source_id=source_id)
                        self._edge(source_node_id, claim_node_id)
                for sentence_id in sentence_ids:
                    sentence_node_id = f"sentence:{sentence_id}"
                    sentence_text = _text(claim.get("sentence_text"))
                    self._node(sentence_node_id, "sentence", sentence_id=sentence_id, sentence_text=sentence_text)
                    self._edge(sentence_node_id, claim_node_id)
                    for source_id in source_ids:
                        source_node_id = f"source:{source_id}"
                        self._node(source_node_id, "source", source_id=source_id)
                        self._edge(source_node_id, sentence_node_id)

        return {
            "nodes": list(self._nodes.values()),
            "builder_version": self.version,
        }

    @staticmethod
    def _ancestors(nodes_by_id: dict[str, dict[str, Any]], node_id: str) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        def visit(current: str) -> None:
            for parent_id in nodes_by_id.get(current, {}).get("parent_ids") or []:
                if parent_id in seen:
                    continue
                seen.add(parent_id)
                visit(parent_id)
                ordered.append(parent_id)

        visit(node_id)
        return ordered

    @staticmethod
    def _descendants(nodes_by_id: dict[str, dict[str, Any]], node_id: str) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        def visit(current: str) -> None:
            for child_id in nodes_by_id.get(current, {}).get("child_ids") or []:
                if child_id in seen:
                    continue
                seen.add(child_id)
                ordered.append(child_id)
                visit(child_id)

        visit(node_id)
        return ordered

    def focus(self, graph: dict[str, Any], *, target_type: str, target_id: str) -> dict[str, Any]:
        nodes_by_id = {node["id"]: node for node in graph.get("nodes") or [] if isinstance(node, dict) and node.get("id")}
        node_id = target_id if target_id in nodes_by_id else f"{target_type}:{target_id}"
        focus_node = nodes_by_id.get(node_id)
        if focus_node is None:
            return {
                "target_type": target_type,
                "target_id": target_id,
                "found": False,
                "nodes": [],
                "debug": {},
                "builder_version": self.version,
            }
        related_ids = [*self._ancestors(nodes_by_id, node_id), node_id, *self._descendants(nodes_by_id, node_id)]
        related_nodes = [nodes_by_id[item] for item in related_ids if item in nodes_by_id]
        return {
            "target_type": target_type,
            "target_id": target_id,
            "found": True,
            "nodes": related_nodes,
            "debug": self._debug_payload(related_nodes, target_type=target_type),
            "builder_version": self.version,
        }

    @staticmethod
    def _debug_payload(nodes: list[dict[str, Any]], *, target_type: str) -> dict[str, Any]:
        claims = [node for node in nodes if node.get("type") == "claim"]
        sentences = [node for node in nodes if node.get("type") == "sentence"]
        sources = [node for node in nodes if node.get("type") == "source"]
        profiles = [node for node in nodes if node.get("type") == "global_profile"]
        chunks = [node for node in nodes if node.get("type") == "retrieval_chunk"]
        if target_type == "claim":
            return {
                "Claim": [node.get("metadata", {}).get("claim_text") or node.get("id") for node in claims],
                "Sentence": [node.get("metadata", {}).get("sentence_text") or node.get("id") for node in sentences],
                "Source": [node.get("metadata", {}).get("source_id") or node.get("id") for node in sources],
            }
        return {
            "Profile": [node.get("metadata", {}).get("entity_name") or node.get("id") for node in profiles],
            "Claims": [node.get("metadata", {}).get("claim_text") or node.get("id") for node in claims],
            "Sources": [node.get("metadata", {}).get("source_id") or node.get("id") for node in sources],
            "RetrievalChunks": [node.get("id") for node in chunks],
        }


__all__ = ["LINEAGE_BUILDER_VERSION", "LineageBuilderV0"]
