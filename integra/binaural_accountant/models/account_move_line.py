from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    foreign_currency_id = fields.Many2one(related="move_id.foreign_currency_id", store=True)
    foreign_rate = fields.Float(related="move_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(related="move_id.foreign_inverse_rate", store=True)

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Tasa",
        store=True,
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        currency_field="foreign_currency_id",
        store=True,
    )

    # Report fields
    foreign_debit = fields.Monetary(currency_field="foreign_currency_id")
    foreign_credit = fields.Monetary(currency_field="foreign_currency_id")
    foreign_balance = fields.Monetary(
        currency_field="foreign_currency_id", compute="_compute_foreign_balance", store=True
    )

    @api.depends("price_unit", "foreign_inverse_rate")
    def _compute_foreign_price(self):
        for line in self:
            line.foreign_price = line.price_unit * line.foreign_inverse_rate

    @api.depends("foreign_price", "quantity")
    def _compute_foreign_subtotal(self):
        for line in self:
            line.foreign_subtotal = line.foreign_price * line.quantity

    @api.depends("foreign_credit", "foreign_debit")
    def _compute_foreign_balance(self):
        for line in self:
            if line.move_id.is_invoice(include_receipts=True):
                # This may be needed to be changed in the future, when taking into account
                # moves that are not invoices.
                line.foreign_balance = 0.0
            line.foreign_balance = line.foreign_debit - line.foreign_credit
