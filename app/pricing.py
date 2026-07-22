from typing import Dict, Optional, Union

from data.policies import calculate_discount as apply_discount_policy
from data.policies import requires_human_approval as policy_requires_approval


Number = Union[int, float]


def volume_discount_percent(quantity: int) -> float:
    policy_result = apply_discount_policy({"quantity": quantity})
    return float(policy_result["discount"])


def calculate_pricing(
    unit_price_usd: Number,
    quantity: int,
    requested_discount: Optional[Number] = None,
) -> Dict[str, Union[float, bool, str, None]]:
    volume_discount = volume_discount_percent(quantity)
    requested = max(float(requested_discount or 0), 0.0)
    applied_discount = max(volume_discount, requested)

    subtotal = round(float(unit_price_usd) * quantity, 2)
    discount_amount = round(subtotal * applied_discount / 100, 2)
    total = round(subtotal - discount_amount, 2)
    requires_approval = policy_requires_approval({"discount": applied_discount})

    return {
        "subtotal_usd": subtotal,
        "volume_discount_percent": volume_discount,
        "applied_discount_percent": applied_discount,
        "discount_amount_usd": discount_amount,
        "total_usd": total,
        "requires_human_approval": requires_approval,
        "human_review_reason": (
            "Discounts above 10% require manager approval"
            if requires_approval
            else None
        ),
    }


def calculate_discount(requirement):
    """Backward-compatible wrapper around the volume discount policy."""

    requirement["discount"] = volume_discount_percent(requirement.get("quantity", 0))
    return requirement


def requires_human_approval(requirement):
    discount = requirement.get(
        "applied_discount_percent", requirement.get("discount", 0)
    )
    return discount > 10
