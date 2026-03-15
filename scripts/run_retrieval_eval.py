from __future__ import annotations

import argparse
import asyncio
import json

from apps.core.container.app_container import container
from apps.knowledge.application.evaluation import RetrievalEvaluationService


async def _run(dataset_path: str, kb_uuid: str, user_id: int, role: str, ablation_mode: str) -> None:
    retrieval_service = container.retrieval_service
    evaluator = RetrievalEvaluationService(retrieval_service=retrieval_service)
    result = await evaluator.run_retrieval_eval(
        dataset_path=dataset_path,
        kb_uuid=kb_uuid,
        current_user_id=user_id,
        current_user_role=role,
        ablation_mode=ablation_mode,
    )
    result["weight_suggestions"] = evaluator.suggest_weight_adjustments(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge retrieval offline evaluator")
    parser.add_argument("--dataset", required=True, help="JSON/YAML evaluation dataset path")
    parser.add_argument("--kb-uuid", required=True, help="Target KB UUID")
    parser.add_argument("--user-id", required=False, type=int, default=1, help="User ID in permission scope")
    parser.add_argument("--role", required=False, default="owner", help="User role")
    parser.add_argument(
        "--ablation-mode",
        required=False,
        default="full_context",
        choices=["assertion_only", "assertion_neighbors", "assertion_neighbors_evidence", "full_context"],
    )
    args = parser.parse_args()
    asyncio.run(
        _run(
            dataset_path=args.dataset,
            kb_uuid=args.kb_uuid,
            user_id=args.user_id,
            role=args.role,
            ablation_mode=args.ablation_mode,
        )
    )


if __name__ == "__main__":
    main()
