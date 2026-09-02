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
        data = response.get("data") or {}
        serial = data.get("_registeredMachineNumber") or serial
        last_z_number = self._get_last_z_order_number(serial)
        pos_order_ids = self.env["pos.order"].search(
            [("fiscal_machine", "=", serial), ("mf_reportz", "=", False)]
        )
        if last_z_number is not None:
            last_number = self._max_mf_invoice_number_for_order_z(serial, last_z_number)
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
            return False
        return number > last_number

    def _get_last_z_order_number(self, serial):
        self.env.cr.execute(
            """
            SELECT MAX(
                CASE WHEN mf_reportz ~ '^[0-9]+$'
                     THEN mf_reportz::integer
                     ELSE NULL
                END
            )
            FROM pos_order
            WHERE fiscal_machine = %s
            """,
            (serial,),
        )
        return self.env.cr.fetchone()[0]

    def _max_mf_invoice_number_for_order_z(self, serial, z_number):
        orders = self.env["pos.order"].search(
            [("fiscal_machine", "=", serial), ("mf_reportz", "=", str(z_number))]
        )
        numbers = [n for n in (self._parse_mf_invoice_number(o) for o in orders) if n is not None]
        return max(numbers) if numbers else None
