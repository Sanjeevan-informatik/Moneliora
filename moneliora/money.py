"""Exact conversion at the boundary of the EUR paper-portfolio snapshot API."""
from decimal import Decimal, InvalidOperation
import json


def exact_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate snapshot field.')
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError('Non-finite snapshot amount.')
    return json.loads(text, parse_float=Decimal, parse_constant=invalid_constant, object_pairs_hook=pairs)


def euro_cents(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError('Use a finite EUR amount with at most two decimal places.')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < Decimal('-10000000') or amount > Decimal('10000000'):
            raise ValueError('EUR amount outside the supported range.')
        if amount != amount.quantize(Decimal('0.01')):
            raise ValueError('EUR amounts must have at most two decimal places.')
        return int(amount * 100)
    except InvalidOperation as error:
        raise ValueError('Invalid EUR amount.') from error


def migrate_amount(data, old, new):
    result = dict(data)
    if old in result:
        if new in result:
            raise ValueError('Supply either legacy EUR or integer cents, not both.')
        result[new] = euro_cents(result.pop(old))
    return result
