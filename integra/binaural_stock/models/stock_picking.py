import logging
from dateutil import parser

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_default_currency(self):
        return self.env.company.currency_foreign_id.id or False

    foreign_rate = fields.Float(
        compute="_compute_foreign_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
        help="The currency rate taken from the sale order.",
    )
    foreign_currency_id = fields.Many2one(
        "res.currency", default=_get_default_currency, help="The currency of the sale order."
    )
    analytic_account_id = fields.Many2one("account.analytic.account")

    @api.depends("sale_id", "purchase_id", "scheduled_date")
    def _compute_foreign_rate(self):
        rate = self.env["res.currency.rate"]

        for stock in self:
            origin_doc = stock.get_origin_document()
            foreign_vals = {"foreign_rate": 0.0}
            decimals = stock.foreign_currency_id.decimal_places

            if origin_doc and fields.Float.is_zero(origin_doc.foreign_rate, precision_digits=decimals):
                foreign_vals.update({"foreign_rate": origin_doc.foreign_rate})
            else:
                rate_date = parser.parse(
                    str(stock.scheduled_date)
                ).date() or fields.Date.context_today(self)
                foreign_vals = rate.compute_rate(stock.foreign_currency_id.id, rate_date)
                del foreign_vals["foreign_inverse_rate"]

            stock.update(foreign_vals)

    @api.model
    def get_origin_document(self):
        """
        Get the origin document of the stock picking.

        Returns
        -------
        sale.order or purchase.order or stock.picking 
        or False as the origin document of the stock picking.
        """

        self.ensure_one()
        if self.sale_id or self.purchase_id:
            return self.sale_id or self.purchase_id

        return self.mapped("move_ids.origin_returned_move_id.picking_id")