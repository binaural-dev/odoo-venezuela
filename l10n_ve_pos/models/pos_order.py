from odoo import models, fields, api, _
import logging
from pprint import pformat
_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError

class PosOrder(models.Model):
    _inherit = "pos.order"

    foreign_currency_id = fields.Many2one("res.currency", related="company_id.foreign_currency_id")
    foreign_amount_total = fields.Float(string="Foreign Total", readonly=True, required=True)
    foreign_currency_rate = fields.Float(readonly=True, required=False)
    
    def _process_order(self, order, existing_order):
        try:
            order["foreign_amount_total"] = float(order.get("foreign_amount_total", 0.0) or 0.0)
        except (TypeError, ValueError):
            order["foreign_amount_total"] = 0.0

        try:
            order["foreign_currency_rate"] = float(order.get("foreign_currency_rate", 0.0) or 0.0)
        except (TypeError, ValueError):
            order["foreign_currency_rate"] = 0.0

        return super()._process_order(order, existing_order)
       

    def _payment_fields(self, order, ui_paymentline):
        res = super()._payment_fields(order, ui_paymentline)

        # Be tolerant with payload variants sent by custom POS frontends.
        foreign_amount = ui_paymentline.get("foreign_amount", ui_paymentline.get("foreignAmount", 0.0))
        foreign_rate = ui_paymentline.get("foreign_rate", ui_paymentline.get("foreignRate", 0.0))
        foreign_inverse_rate = ui_paymentline.get(
            "foreign_inverse_rate",
            ui_paymentline.get("foreignInverseRate", 0.0),
        )
        amount = ui_paymentline.get("amount", 0.0)

        try:
            foreign_amount = float(foreign_amount or 0.0)
        except (TypeError, ValueError):
            foreign_amount = 0.0

        try:
            foreign_rate = float(foreign_rate or 0.0)
        except (TypeError, ValueError):
            foreign_rate = 0.0

        try:
            foreign_inverse_rate = float(foreign_inverse_rate or 0.0)
        except (TypeError, ValueError):
            foreign_inverse_rate = 0.0

        try:
            amount = float(amount or 0.0)
        except (TypeError, ValueError):
            amount = 0.0

        if not foreign_inverse_rate and foreign_rate:
            foreign_inverse_rate = 1 / foreign_rate if foreign_rate > 1 else foreign_rate

        if not foreign_rate and foreign_inverse_rate:
            foreign_rate = 1 / foreign_inverse_rate if foreign_inverse_rate else 0.0

        if not foreign_amount:
            if foreign_inverse_rate:
                foreign_amount = amount * foreign_inverse_rate
            elif foreign_rate:
                foreign_amount = amount / foreign_rate if foreign_rate > 1 else amount * foreign_rate

        res["foreign_amount"] = foreign_amount
        res["foreign_rate"] = foreign_rate
        res["foreign_inverse_rate"] = foreign_inverse_rate
        return res

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        res.update(
            {
                "foreign_rate": self.foreign_currency_rate or self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                "manually_set_rate": True,
            }
        )
        return res 
    
    @api.model
    def convert_amount(self, amount):
        """Convert a company-currency amount to foreign currency without requiring order line records."""
        company = self.env.company
        try:
            numeric_amount = float(amount or 0.0)
        except (TypeError, ValueError):
            numeric_amount = 0.0
        
        if not company.foreign_currency_id:
            return numeric_amount
        return company.currency_id._convert(
            numeric_amount,
            company.foreign_currency_id,
            company,
            fields.Date.today()
        )

class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    foreign_currency_rate = fields.Float(related="order_id.foreign_currency_rate")
    foreign_price = fields.Float(readonly=True)

    def _prepare_refund_data(self, refund_order, PosOrderLineLot):
        res = super()._prepare_refund_data(refund_order, PosOrderLineLot)
        res.update({"foreign_price": self.foreign_price})
        return res 

    def _export_for_ui(self, orderline):
        res = super()._export_for_ui(orderline)
        res["foreign_price"] = orderline.foreign_price
        res["foreign_currency_rate"] = orderline.foreign_currency_rate
        return res
    
    @api.model
    def convert_amount(self, amount):
        """Convert a company-currency amount to foreign currency without requiring order line records."""
        company = self.env.company

        try:
            numeric_amount = float(amount or 0.0)
        except (TypeError, ValueError):
            numeric_amount = 0.0
        
        if not company.foreign_currency_id:
            return numeric_amount
        return company.currency_id._convert(
            numeric_amount,
            company.foreign_currency_id,
            company,
            fields.Date.today()
        )

