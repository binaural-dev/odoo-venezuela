from odoo import api, fields, models, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default value of the foreign currency field

        Returns
        -------
        type = int
            The id of the foreign currency of the company

        """
        alternate_currency = self.env.company.currency_foreign_id.id
        if alternate_currency:
            return alternate_currency
        return False

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    foreign_price = fields.Float(
        help="Foreign Price of the line",
        compute="_compute_foreign_price",
        digits="Tasa",
    )
    foreign_subtotal = fields.Monetary(
        help="Foreign Subtotal of the line",
        compute="_compute_foreign_subtotal",
        digits="Tasa",
        currency_field="foreign_currency_id",
    )

    @api.depends("price_unit", "quantity")
    def _compute_foreign_price(self):
        for rec in self:
            rec.foreign_price = rec.price_unit * rec.move_id.foreign_rate

    @api.depends("foreign_price", "quantity")
    def _compute_foreign_subtotal(self):
        for rec in self:
            rec.foreign_subtotal = rec.foreign_price * rec.quantity
