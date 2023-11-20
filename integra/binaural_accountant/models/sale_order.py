
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order.company_id.account_use_credit_limit and order.partner_id.use_partner_credit_limit_order:
                total_pay = order.partner_id.credit + order.amount_total
                if total_pay > order.partner_id.credit_limit:
                    raise ValidationError(_("La cuenta %s es de %s mas %s en presupuesto da un total de %s superando el limite de ventas de %s. Por favor cancele el presupuesto o comuníquese con el administrador para aumentar el limite de crédito del cliente.",
                                            order.partner_id.property_account_receivable_id.display_name, order.partner_id.credit_limit, order.amount_total, total_pay, order.partner_id.credit_limit)
                                        )
        return res