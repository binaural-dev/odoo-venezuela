from odoo import models, fields, api, _


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    mf_serial = fields.Char(
        string="Serial de maquina de fiscal", default=False, copy=False, tracking=True
    )
    mf_invoice_number = fields.Char(
        string="Número de secuencia", default=False, copy=False, tracking=True
    )
    mf_reportz = fields.Char(
        string="Reporte Z", default=False, copy=False, tracking=True
    )

    @api.model
    def _select(self):
        res = super()._select()
        res += """,move.mf_serial as mf_serial,move.mf_invoice_number as mf_invoice_number,move.mf_reportz as mf_reportz"""
        return res
