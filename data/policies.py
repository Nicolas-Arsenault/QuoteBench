def calculate_discount(requirement):
    # Check larger quantities first so 500+ takes precedence over 100+.
    quantity = requirement.get("quantity", 0)

    if quantity >= 500:
        requirement["discount"] = 10
    elif quantity >= 100:
        requirement["discount"] = 5
    else:
        requirement["discount"] = 0

    return requirement


def requires_human_approval(requirement):
    # Safe lookup with .get() in case 'discount' key doesn't exist yet
    discount = requirement.get("discount", 0)

    if discount > 10:
        return True
    return False
