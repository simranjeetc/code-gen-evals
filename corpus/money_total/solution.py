from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_TWO_PLACES = Decimal("0.01")


def total(amounts):
    running = Decimal(0)
    for amount in amounts:
        if not isinstance(amount, str):
            raise ValueError("amount must be a string: %r" % (amount,))
        text = amount.strip()
        if not text:
            raise ValueError("empty amount")
        try:
            running += Decimal(text)
        except InvalidOperation:
            raise ValueError("invalid amount: %r" % (amount,)) from None
    return str(running.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))
