import json
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.pricing import calculate_pricing
from app.retrieval import search_products


class FinalState(BaseModel):
    """The quote workflow state, populated incrementally by each graph node."""

    message: Optional[str] = None

    use_case: Optional[str] = None
    quantity: Optional[int] = None
    budget: Optional[float] = None
    delivery_weeks: Optional[int] = None
    requested_discount: Optional[float] = None

    candidate_products: Optional[List[Dict[str, Any]]] = None
    selected_products: Optional[List[Dict[str, Any]]] = None

    subtotal_usd: Optional[float] = None
    volume_discount_percent: Optional[float] = None
    applied_discount_percent: Optional[float] = None
    discount_amount_usd: Optional[float] = None
    total_usd: Optional[float] = None

    requires_human_approval: Optional[bool] = None
    human_review_reason: Optional[str] = None
    quote: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    errors: Optional[List[str]] = None


@lru_cache(maxsize=1)
def _structured_llm():
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o"),
        temperature=0,
    )
    return llm.with_structured_output(FinalState)


def _extract_with_llm(message: str) -> FinalState:
    return _structured_llm().invoke(
        [
            (
                "system",
                """Extract quote requirements from the customer's message.
Only populate use_case, quantity, budget, delivery_weeks, and
requested_discount. Treat budget as the total budget in USD and discount as a
percentage number. Leave information that was not provided as null.""",
            ),
            ("human", message),
        ]
    )


def _select_with_llm(
    state: FinalState, candidates: List[Dict[str, Any]]
) -> FinalState:
    return _structured_llm().invoke(
        [
            (
                "system",
                """Select the single best product for the customer's quote.
Only choose a SKU from the supplied candidates. Populate selected_products
with one object containing the sku and a short reason. Do not populate any
other state fields.""",
            ),
            (
                "human",
                json.dumps(
                    {
                        "requirements": {
                            "use_case": state.use_case,
                            "quantity": state.quantity,
                            "budget": state.budget,
                            "delivery_weeks": state.delivery_weeks,
                        },
                        "candidates": candidates,
                    }
                ),
            ),
        ]
    )


def extract_requirements_node(state: FinalState) -> Dict[str, Any]:
    if not state.message or not state.message.strip():
        return {
            "status": "invalid_request",
            "errors": ["A customer message is required"],
        }

    extracted = _extract_with_llm(state.message)
    errors = []
    if not extracted.use_case:
        errors.append("The product use case could not be determined")
    if extracted.quantity is None or extracted.quantity <= 0:
        errors.append("A quantity greater than zero is required")
    if extracted.budget is not None and extracted.budget <= 0:
        errors.append("The budget must be greater than zero")
    if extracted.delivery_weeks is not None and extracted.delivery_weeks <= 0:
        errors.append("Delivery weeks must be greater than zero")
    if extracted.requested_discount is not None and not (
        0 <= extracted.requested_discount <= 100
    ):
        errors.append("The requested discount must be between 0 and 100 percent")

    if errors:
        return {"status": "invalid_request", "errors": errors}

    return {
        "use_case": extracted.use_case,
        "quantity": extracted.quantity,
        "budget": extracted.budget,
        "delivery_weeks": extracted.delivery_weeks,
        "requested_discount": extracted.requested_discount,
        "status": "requirements_extracted",
    }


def find_candidate_products_node(state: FinalState) -> Dict[str, Any]:
    candidates = search_products(
        query=state.use_case or state.message or "",
        quantity=state.quantity,
        delivery_weeks=state.delivery_weeks,
    )
    if not candidates:
        return {
            "candidate_products": [],
            "status": "no_candidate_products",
            "errors": ["No products satisfy the quote requirements"],
        }

    return {
        "candidate_products": candidates,
        "status": "candidates_found",
    }


def select_products_node(state: FinalState) -> Dict[str, Any]:
    candidates = state.candidate_products or []
    selection = _select_with_llm(state, candidates)
    selected = selection.selected_products or []
    candidates_by_sku = {product["sku"]: product for product in candidates}

    valid_selections = []
    for item in selected:
        sku = item.get("sku")
        if sku in candidates_by_sku:
            product = dict(candidates_by_sku[sku])
            product["quantity"] = state.quantity
            product["reason"] = item.get("reason")
            valid_selections.append(product)
            break

    if not valid_selections:
        return {
            "selected_products": [],
            "status": "no_product_selected",
            "errors": ["No valid candidate product was selected"],
        }

    return {
        "selected_products": valid_selections,
        "status": "product_selected",
    }


def calculate_price_node(state: FinalState) -> Dict[str, Any]:
    product = (state.selected_products or [])[0]
    pricing = calculate_pricing(
        unit_price_usd=float(product["unit_price_usd"]),
        quantity=state.quantity or 0,
        requested_discount=state.requested_discount,
    )
    return {**pricing, "status": "pricing_calculated"}


def _build_quote(state: FinalState, provisional: bool) -> Dict[str, Any]:
    return {
        "products": state.selected_products,
        "subtotal_usd": state.subtotal_usd,
        "discount_percent": state.applied_discount_percent,
        "discount_amount_usd": state.discount_amount_usd,
        "total_usd": state.total_usd,
        "delivery_weeks": state.delivery_weeks,
        "provisional": provisional,
    }


def human_review_node(state: FinalState) -> Dict[str, Any]:
    return {
        "quote": _build_quote(state, provisional=True),
        "status": "human_review_required",
    }


def generate_quote_node(state: FinalState) -> Dict[str, Any]:
    return {
        "quote": _build_quote(state, provisional=False),
        "status": "quote_completed",
    }


def _continue_if_valid(state: FinalState) -> str:
    return "stop" if state.errors else "continue"


def _pricing_route(state: FinalState) -> str:
    return "human_review" if state.requires_human_approval else "final_quote"


def build_quote_graph():
    builder = StateGraph(FinalState)
    builder.add_node("extract_requirements", extract_requirements_node)
    builder.add_node("find_candidates", find_candidate_products_node)
    builder.add_node("select_product", select_products_node)
    builder.add_node("calculate_price", calculate_price_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("final_quote", generate_quote_node)

    builder.add_edge(START, "extract_requirements")
    builder.add_conditional_edges(
        "extract_requirements",
        _continue_if_valid,
        {"continue": "find_candidates", "stop": END},
    )
    builder.add_conditional_edges(
        "find_candidates",
        _continue_if_valid,
        {"continue": "select_product", "stop": END},
    )
    builder.add_conditional_edges(
        "select_product",
        _continue_if_valid,
        {"continue": "calculate_price", "stop": END},
    )
    builder.add_conditional_edges(
        "calculate_price",
        _pricing_route,
        {"human_review": "human_review", "final_quote": "final_quote"},
    )
    builder.add_edge("human_review", END)
    builder.add_edge("final_quote", END)
    return builder.compile()


quote_graph = build_quote_graph()
