from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, float_is_zero


import logging

_logger = logging.getLogger(__name__)
class ResCurrency(models.Model):
    _inherit = "res.currency"

    def _convert(self, from_amount, to_currency, company=None, date=None, round=True, custom_rate=0.0):
        """
        Versión Integrada: Soporta custom_rate y garantiza simetría de redondeo
        para evitar descuadres de 0.01 en Bolívares y otras monedas.
        """
        if date is None:
            date = fields.Date.today()
        if company is None:
            company = self.env.company
            
        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        assert to_currency, "convert amount to unknown currency"

        if self == to_currency:
            rate = 1.0
        elif custom_rate > 0:
            rate = custom_rate
        else:
            rate = self._get_conversion_rate(self, to_currency, company, date)

        if from_amount:
            to_amount = from_amount * rate
        else:
            return 0.0

        if round:
            rounded_res = to_currency.round(to_amount)
            
            # PRUEBA DE REVERSIBILIDAD: ¿El redondeo mantiene la paridad?
            # Dividimos el resultado redondeado entre la tasa para volver al origen
            back_to_foreign = rounded_res / rate if rate else 0.0
            diff_foreign = from_amount - back_to_foreign
            
            # Si hay una diferencia infinitesimal en la moneda origen (ruido de decimales)
            if not float_is_zero(diff_foreign, precision_rounding=self.rounding):
                # Calculamos el ajuste necesario en la moneda destino (Bolívares, Euros, etc.)
                adjustment = float_round(diff_foreign * rate, precision_rounding=to_currency.rounding)
                # Aplicamos el ajuste para que el asiento sea perfectamente reversible
                
                return rounded_res + adjustment
     
            return rounded_res
        
        return to_amount
    

