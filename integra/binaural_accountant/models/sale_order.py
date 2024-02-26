
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
                    raise ValidationError(_("No se ha confirmado el presupuesto. Límite de crédito excedido. La cuenta por cobrar del cliente es de %s más %s en presupuesto da un total de %s superando el límite de ventas de %s. Por favor cancele el presupuesto o comuníquese con el administrador para aumentar el límite de crédito del cliente.",
                                            round(order.partner_id.credit, order.currency_id.decimal_places), round(order.amount_total, order.currency_id.decimal_places), total_pay, round(order.partner_id.credit_limit, order.currency_id.decimal_places))
                                        )
        return res