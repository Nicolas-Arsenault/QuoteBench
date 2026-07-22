from app.pricing import calculate_pricing, volume_discount_percent


def test_volume_discount_boundaries():
    assert volume_discount_percent(99) == 0
    assert volume_discount_percent(100) == 5
    assert volume_discount_percent(499) == 5
    assert volume_discount_percent(500) == 10


def test_requested_discount_above_policy_requires_human_approval():
    pricing = calculate_pricing(
        unit_price_usd=10,
        quantity=500,
        requested_discount=15,
    )

    assert pricing["subtotal_usd"] == 5000
    assert pricing["applied_discount_percent"] == 15
    assert pricing["total_usd"] == 4250
    assert pricing["requires_human_approval"] is True


def test_volume_discount_is_used_when_it_beats_requested_discount():
    pricing = calculate_pricing(
        unit_price_usd=10,
        quantity=500,
        requested_discount=5,
    )

    assert pricing["applied_discount_percent"] == 10
    assert pricing["total_usd"] == 4500
    assert pricing["requires_human_approval"] is False
