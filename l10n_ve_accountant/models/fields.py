from odoo.fields import Monetary
from odoo.tools import float_repr
from odoo import tools
import logging

_logger = logging.getLogger(__name__)

def new_convert_to_column_insert(self, value, record, values=None, validate=True):
    # Recuperar la moneda desde los valores o el registro
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
        # Nota: evitamos prefetch para no pisar el caché
        currency = record[:1].sudo().with_context(prefetch_fields=False)[currency_field_name]
        currency = currency.with_env(record.env)

    value = float(value or 0.0)
    
    if currency:
        # Quitamos currency.round(value) y forzamos 10 decimales como en tu código anterior
        return float_repr(value, 10)
        
    return value


def new_convert_to_cache(self, value, record, validate=True):
    # Formato de caché: float
    value = float(value or 0.0)
    if value and validate:
        currency_field = self.get_currency_field(record)
        currency = record.sudo().with_context(prefetch_fields=False)[currency_field]
        
        if len(currency) > 1:
            raise ValueError("Got multiple currencies while assigning values of monetary field %s" % str(self))
        elif currency:
            # ELIMINADO: value = currency.with_env(record.env).round(value)
            # Simplemente retornamos el valor flotante sin redondear por la moneda
            value = value
    return value

# Aplicamos el parche a los métodos de Odoo 19
Monetary.convert_to_column_insert = new_convert_to_column_insert
Monetary.convert_to_cache = new_convert_to_cache