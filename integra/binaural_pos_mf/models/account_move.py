from odoo import fields, models, api

import logging

_logger = logging.getLogger(__name__)


class AccountMoveInh(models.Model):
    _inherit = "account.move"

    cashbox_id = fields.Many2one("pos.config", string="Cashbox invoiced", copy=False)
    sales_book_type = fields.Selection(
        [("01-REG", "01-REG"), ("02-REG", "02-REG"), ("03-REG", "03-ANU")],
        compute="_compute_sales_book_type",
        default="01-REG",
    )

    @api.depends("sales_book_type")
    def _compute_sales_book_type(self):
        for record in self:
            if record.move_type in ["out_refund", "out_debit"] and record.state in "posted":
                record.sales_book_type = "02-REG"
            elif (
                record.move_type in ["out_invoice", "out_refund", "out_debit"]
                and record.state == "cancel"
            ):
                record.sales_book_type = "03-ANU"
            else:
                record.sales_book_type = "01-REG"

    def report_z(self, serial, response):
        res = super().report_z(serial, response)
        data = response.get("data", False)
        serial = data.get("_registeredMachineNumber")
        pos_order_ids = self.env["pos.order"].search(
            ["&", ("fiscal_machine", "=", serial), ("mf_reportz", "=", False)]
        )
        _logger.info(pos_order_ids)

        for order in pos_order_ids:
            order.write({"mf_reportz": int(res) + 1})

        return res
