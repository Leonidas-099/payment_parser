from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")


def normalize_amount(amount: Decimal) -> Decimal:
    return amount.quantize(_CENTS, rounding=ROUND_HALF_UP)


def format_amount(amount: Decimal) -> str:
    return format(normalize_amount(amount), "f")
