from odoo import fields, models, api


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
        last_z_order = self.env["pos.order"].search(
            [("fiscal_machine", "=", serial), ("mf_reportz", "!=", False)],
            order="mf_reportz desc",
            limit=1,
        )
        pos_order_ids = self.env["pos.order"].search(
            [("fiscal_machine", "=", serial), ("mf_reportz", "=", False)]
        )
        if last_z_order:
            # Ver comentario en account_move.py (l10n_ve_iot_mf) report_z():
            # se acota por mf_invoice_number, no por create_date ni invoice_date.
            last_number = self._parse_mf_invoice_number(last_z_order)
            if last_number is not None:
                pos_order_ids = pos_order_ids.filtered(
                    lambda o: self._mf_invoice_number_after(o, last_number)
                )

        for order in pos_order_ids:
            order.write({"mf_reportz": int(res)})

        return res

    def _parse_mf_invoice_number(self, order):
        try:
            return int(order.mf_invoice_number)
        except (TypeError, ValueError):
            return None

    def _mf_invoice_number_after(self, order, last_number):
        number = self._parse_mf_invoice_number(order)
        if number is None:
            return True
        return number > last_number
