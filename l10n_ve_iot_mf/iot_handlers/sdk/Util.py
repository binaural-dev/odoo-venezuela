import logging

_logger = logging.getLogger(__name__)


class Util:
    def DoValueDouble(self, value):
        if not value or len(value) < 3:
            _logger.warning("DoValueDouble: invalid value '%s'", value)
            return 0.0
        list_items_count = len(value)
        try:
            integer_value = int(value[0:-2])
        except ValueError:
            _logger.warning("DoValueDouble: non-numeric value '%s'", value)
            return 0.0
        floating_value = value[(list_items_count - 2) :]
        decimals = float(floating_value) / 100
        total_amount = integer_value + decimals
        return total_amount
