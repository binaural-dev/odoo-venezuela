from odoo import models, api, fields


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _prepare_account_move_line(self, move=False):
        """
        Override the account move line to use the price total instead of the price unit discounted.
        This fix ensures proper rounding to avoid precision residues (example, 0.0005) 
        that cause unbalanced move errors.
        """
        # Se comenta porq esto se solucion solventando la cantidad de digitos en la tasa inversa 
        # la cual estaba limitada y en ocaciones procia la diferenc
        
        # Simplemente llamamos al comportamiento original de Odoo y lo devolvemos
        return super()._prepare_account_move_line(move=move)