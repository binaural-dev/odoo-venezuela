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
    mf_serial = fields.Char(
        string="Fiscal machine serial", default=False, copy=False, tracking=True
    )
    mf_invoice_number = fields.Char(
        string="Sequence number", default=False, copy=False, tracking=True
    )
    mf_reportz = fields.Char(
        string="Report number Z", default=False, copy=False, tracking=True
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
        parent = super()
        if hasattr(parent, "report_z"):
            # l10n_ve_iot_mf (u otro módulo fiscal) está instalado y define la base
            res = parent.report_z(serial, response)
        else:
            # Fallback standalone: POS con Web Serial sin módulo de facturación fiscal
            res = self._report_z_base(serial, response)

        data = response.get("data", False)
        serial = data.get("_registeredMachineNumber")
        pos_order_ids = self.env["pos.order"].search(
            ["&", ("fiscal_machine", "=", serial), ("mf_reportz", "=", False)]
        )
        _logger.info(pos_order_ids)

        for order in pos_order_ids:
            order.write({"mf_reportz": int(res) + 1})

        return res

    def _report_z_base(self, serial, response):
        """Réplica de la lógica base de report_z (l10n_ve_iot_mf) para que el POS
        funcione aunque el módulo de facturación fiscal no esté instalado."""
        from odoo.exceptions import ValidationError

        data = response.get("data", False)

        if not response.get("valid", False):
            raise ValidationError(response.get("message", "No se pudo imprimir el reporte Z"))

        serial = data.get("_registeredMachineNumber")

        account_moves = self.env["account.move"].search(
            ["&", ("mf_serial", "=", serial), ("mf_reportz", "=", False)]
        )

        number_of_last_z = data.get("_dailyClosureCounter", False)
        if False in [data, number_of_last_z]:
            last_move = self.env["account.move"].search(
                ["&", ("mf_serial", "=", serial), ("mf_reportz", "!=", False)],
                order="mf_reportz desc",
                limit=1,
            )
            number_of_last_z = last_move.mf_reportz if last_move else 0

        for invoice in account_moves:
            invoice.write({"mf_reportz": int(number_of_last_z) + 1})
        return number_of_last_z
