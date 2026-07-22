import os
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any, Dict, Optional

from app.graph import FinalState, quote_graph, qwen_quote_graph


def _selected_skus(state: FinalState):
    return [product["sku"] for product in state.selected_products or []]


def _run_workflow(provider: str, workflow, message: str) -> Dict[str, Any]:
    started_at = perf_counter()
    try:
        state = FinalState.model_validate(
            workflow.invoke(FinalState(message=message))
        )
        error: Optional[str] = None
    except Exception as exc:
        state = None
        error = f"{type(exc).__name__}: {exc}"

    latency_ms = round((perf_counter() - started_at) * 1000, 2)
    return {
        "provider": provider,
        "model": (
            os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
            if provider == "openai"
            else os.getenv("QWEN_CHAT_MODEL", "qwen3:4b")
        ),
        "latency_ms": latency_ms,
        "result": state.model_dump() if state else None,
        "error": error,
    }


def _compare_successful_runs(
    openai_run: Dict[str, Any], qwen_run: Dict[str, Any]
) -> Dict[str, Any]:
    openai_state = FinalState.model_validate(openai_run["result"])
    qwen_state = FinalState.model_validate(qwen_run["result"])

    openai_total = openai_state.total_usd
    qwen_total = qwen_state.total_usd
    total_difference = (
        round(abs(openai_total - qwen_total), 2)
        if openai_total is not None and qwen_total is not None
        else None
    )

    latency_difference = round(
        abs(openai_run["latency_ms"] - qwen_run["latency_ms"]), 2
    )
    if latency_difference == 0:
        faster_provider = "tie"
    elif openai_run["latency_ms"] < qwen_run["latency_ms"]:
        faster_provider = "openai"
    else:
        faster_provider = "qwen"

    return {
        "available": True,
        "same_status": openai_state.status == qwen_state.status,
        "same_selected_skus": _selected_skus(openai_state)
        == _selected_skus(qwen_state),
        "same_human_review_decision": openai_state.requires_human_approval
        == qwen_state.requires_human_approval,
        "same_total": openai_total == qwen_total,
        "total_difference_usd": total_difference,
        "faster_provider": faster_provider,
        "latency_difference_ms": latency_difference,
    }


def run_model_comparison(
    message: str, workflows: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    workflows = workflows or {
        "openai": quote_graph,
        "qwen": qwen_quote_graph,
    }

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            provider: executor.submit(
                _run_workflow, provider, workflow, message
            )
            for provider, workflow in workflows.items()
        }
        runs = {provider: future.result() for provider, future in futures.items()}

    successful_providers = [
        provider for provider, run in runs.items() if run["error"] is None
    ]
    if len(successful_providers) == 2:
        status = "completed"
        comparison = _compare_successful_runs(runs["openai"], runs["qwen"])
    else:
        status = "partial_failure" if successful_providers else "failed"
        comparison = {
            "available": False,
            "reason": "Both model workflows must succeed to compare results",
        }

    return {
        "status": status,
        "openai": runs["openai"],
        "qwen": runs["qwen"],
        "comparison": comparison,
    }
