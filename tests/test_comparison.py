from fastapi.testclient import TestClient

import app.main as main_module
from app.comparison import run_model_comparison
from app.graph import FinalState


class FakeWorkflow:
    def __init__(self, state=None, error=None):
        self.state = state
        self.error = error

    def invoke(self, state):
        if self.error:
            raise self.error
        return self.state


def _state(sku, total, status="quote_completed", approval=False):
    return FinalState(
        status=status,
        selected_products=[{"sku": sku}],
        total_usd=total,
        requires_human_approval=approval,
    )


def test_model_comparison_reports_result_differences():
    result = run_model_comparison(
        "Need 500 MCUs",
        workflows={
            "openai": FakeWorkflow(_state("SKU-A", 1000)),
            "qwen": FakeWorkflow(_state("SKU-B", 1050)),
        },
    )

    assert result["status"] == "completed"
    assert result["openai"]["result"]["total_usd"] == 1000
    assert result["qwen"]["result"]["total_usd"] == 1050
    assert result["comparison"]["available"] is True
    assert result["comparison"]["same_selected_skus"] is False
    assert result["comparison"]["same_total"] is False
    assert result["comparison"]["total_difference_usd"] == 50


def test_model_comparison_isolates_one_provider_failure():
    result = run_model_comparison(
        "Need 500 MCUs",
        workflows={
            "openai": FakeWorkflow(_state("SKU-A", 1000)),
            "qwen": FakeWorkflow(error=ConnectionError("Ollama unavailable")),
        },
    )

    assert result["status"] == "partial_failure"
    assert result["openai"]["result"] is not None
    assert "ConnectionError" in result["qwen"]["error"]
    assert result["comparison"]["available"] is False


def test_compare_endpoint_returns_comparison(monkeypatch):
    expected = {
        "status": "completed",
        "openai": {"result": {}},
        "qwen": {"result": {}},
        "comparison": {"available": True},
    }
    monkeypatch.setattr(
        main_module, "run_model_comparison", lambda message: expected
    )

    response = TestClient(main_module.app).post(
        "/compare", json={"message": "Need 500 MCUs"}
    )

    assert response.status_code == 200
    assert response.json() == expected
