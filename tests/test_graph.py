import pytest

import app.graph as graph_module
from app.graph import FinalState, build_quote_graph


CANDIDATE = {
    "sku": "SMC-MCU-32F4",
    "product_name": "32-Bit ARM Cortex-M4 Microcontroller",
    "unit_price_usd": 3.45,
    "minimum_quantity": 500,
    "lead_time_weeks": 12,
    "supported_application": "IoT Edge Devices",
    "max_discount": "15% (orders > 5,000)",
    "similarity": 0.92,
}


@pytest.mark.parametrize(
    ("provider", "requested_discount", "expected_status", "expected_total"),
    [("qwen", None, "quote_completed", 1552.50),
     ("qwen", 15, "human_review_required", 1466.25)],
)
def test_quote_graph_routes_to_expected_terminal_node(
    monkeypatch,
    provider,
    requested_discount,
    expected_status,
    expected_total,
):
    providers_used = []

    def fake_extract(message, model_provider):
        providers_used.append(model_provider)
        return FinalState(
            use_case="IoT edge device",
            quantity=500,
            delivery_weeks=12,
            requested_discount=requested_discount,
        )

    def fake_select(state, candidates, model_provider):
        providers_used.append(model_provider)
        return FinalState(
            selected_products=[
                {"sku": CANDIDATE["sku"], "reason": "Best match"}
            ]
        )

    monkeypatch.setattr(graph_module, "_extract_with_llm", fake_extract)
    monkeypatch.setattr(graph_module, "_select_with_llm", fake_select)
    monkeypatch.setattr(
        graph_module, "search_products", lambda **kwargs: [CANDIDATE]
    )

    workflow = build_quote_graph(provider)
    result = FinalState.model_validate(
        workflow.invoke(FinalState(message="Need 500 IoT MCUs"))
    )

    assert result.status == expected_status
    assert result.total_usd == expected_total
    assert result.quote["provisional"] == (
        expected_status == "human_review_required"
    )
    assert providers_used == [provider, provider]


def test_graph_stops_when_no_candidates_are_found(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "_extract_with_llm",
        lambda message, provider: FinalState(
            use_case="quantum computer", quantity=100
        ),
    )
    monkeypatch.setattr(graph_module, "search_products", lambda **kwargs: [])

    result = FinalState.model_validate(
        build_quote_graph("qwen").invoke(FinalState(message="Need a product"))
    )

    assert result.status == "no_candidate_products"
    assert result.candidate_products == []
    assert result.errors == ["No products satisfy the quote requirements"]


def test_graph_rejects_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported model provider"):
        build_quote_graph("unknown")
