from odoo.fields import Monetary
from odoo.tools import float_repr
from odoo import tools
import logging

_logger = logging.getLogger(__name__)

def new_convert_to_column(self, value, record, values=None, validate=True):
    
    currency_field_name = self.get_currency_field(record)
    currency_field = record._fields[currency_field_name]
    
    if values and currency_field_name in values:
        dummy = record.new({currency_field_name: values[currency_field_name]})
        currency = dummy[currency_field_name]
    elif values and currency_field.related and currency_field.related.split('.')[0] in values:
        related_field_name = currency_field.related.split('.')[0]
        dummy = record.new({related_field_name: values[related_field_name]})
        currency = dummy[currency_field_name]
    else:
        currency = record[:1].with_context(prefetch_fields=False)[currency_field_name]
        currency = currency.with_env(record.env)

    value = float(value or 0.0)
    
    if currency:
     
        return float_repr(value, 10)
        
    return value


def new_convert_to_cache(self, value, record, validate=True):
    value = float(value or 0.0)
    if value and validate:
        currency_field = self.get_currency_field(record)
        currency = record.sudo().with_context(prefetch_fields=False)[currency_field]
        if len(currency) > 1:
            raise ValueError("Got multiple currencies while assigning values of monetary field %s" % str(self))
        elif currency:
            value = value
    return value


Monetary.convert_to_cache = new_convert_to_cache

Monetary.convert_to_column = new_convert_to_column
