import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    max_product_invoice = fields.Integer(related="company_id.max_product_invoice", readonly=False)
    group_sales_invoicing_series = fields.Boolean(
        related="company_id.group_sales_invoicing_series",
        readonly=False,
        implied_group="l10n_ve_invoice.group_sales_invoicing_series",
    )
    show_total_on_usd_invoice = fields.Boolean(
        related="company_id.show_total_on_usd_invoice", readonly=False
    )
    show_tag_on_usd_invoice = fields.Boolean(
        related="company_id.show_tag_on_usd_invoice", readonly=False
    )

    @api.onchange("group_sales_invoicing_series")
    def onchange_group_sales_invoicing_series(self):
        ir_sequence = self.env["ir.sequence"].sudo()

        series_sequence = ir_sequence.search(
            ["|", ("code", "=", "series.invoice.correlative"), ("active", "=", False)]
        )
        series_sequence.active = self.group_sales_invoicing_series
