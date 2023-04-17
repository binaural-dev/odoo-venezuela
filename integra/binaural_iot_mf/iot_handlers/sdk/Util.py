class Util:
    def DoValueDouble(self, value):
        list_items_count = len(value)
        integer_value = int(value[0:-2])
        floating_value = value[(list_items_count - 2) :]
        decimals = float(floating_value) / 100
        total_amount = integer_value + decimals
        return total_amount
