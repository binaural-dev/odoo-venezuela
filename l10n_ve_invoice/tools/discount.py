import math

from odoo.tools import float_round

EPS = 1e-9


def spread_amount(amount, gross, rounding):
    """Spreads `amount` over the keys of `gross` ({key: gross subtotal}).

    The shares are proportional to the gross, in units of `rounding` (the
    currency rounding), with the lost units given back by largest remainder
    and no key reaching its own gross, so a fixed discount never takes a whole
    line. The shares add up exactly to `amount` (when the gross allows it).

    Shared by every module that spreads a document amount over its lines (the
    global discount, the deductible).

    :return: {key: share}
    """
    total = sum(gross.values())
    ideal = {key: amount * value / total / rounding for key, value in gross.items()}
    cap = {key: max(math.ceil(value / rounding - EPS) - 1, 0) for key, value in gross.items()}
    units = {key: min(math.floor(ideal[key] + EPS), cap[key]) for key in gross}
    leftover = round(amount / rounding) - sum(units.values())
    by_remainder = sorted(gross, key=lambda key: units[key] - ideal[key])
    while leftover > 0:
        room = [key for key in by_remainder if units[key] < cap[key]][:leftover]
        if not room:
            break
        for key in room:
            units[key] += 1
        leftover -= len(room)
    return {key: float_round(count * rounding, precision_rounding=rounding) for key, count in units.items()}
