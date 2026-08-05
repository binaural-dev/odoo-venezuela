# -*- coding: utf-8 -*-

from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.foreign_currency_id.id or False,
    )

    foreign_rate = fields.Float(
        help="The rate that is gonna be always shown to the user.",
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this order.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
    )

    manually_set_rate = fields.Boolean(default=False)
    last_foreign_rate = fields.Float(copy=False)

    journal_invoice_id = fields.Many2one(
        "account.journal",
        domain="[('type', '=', 'purchase')]",
    )

    @api.onchange("name")
    def onchange_order_line(self):
        """
        Ensure the foreign_rate and foreign_inverse_rate are computed when the order is still not
        created.
        """
        self._compute_rate()

    @api.depends("date_order", "date_approve")
    def _compute_rate(self):
        """
        Compute the rate of the purchase order using the compute_rate method of the
        res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        ignore_rate_with_value = self.env.context.get("ignore_rate_with_value", False)

        for purchase in self:
            if ignore_rate_with_value and purchase.foreign_rate:
                continue

            if purchase.manually_set_rate:
                continue
            date_order = (
                purchase.date_approve.date()
                if purchase.date_approve
                else purchase.date_order.date()
            )
            rate_values = Rate.compute_rate(
                purchase.foreign_currency_id.id, date_order or fields.Date.today()
            )
            purchase.foreign_rate = rate_values.get("foreign_rate", 0)
            purchase.foreign_inverse_rate = rate_values.get("foreign_inverse_rate", 0)

    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        for purchase in self:
            base_usd_id = self.env["ir.model.data"]._xmlid_to_res_id(
                "base.USD", raise_if_not_found=False
            )
            if not bool(purchase.foreign_rate):
                return
            purchase.foreign_inverse_rate = (
                1 / purchase.foreign_rate
                if purchase.foreign_currency_id.id == base_usd_id
                else purchase.foreign_rate
            )
