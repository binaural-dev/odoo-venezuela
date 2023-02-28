from odoo import api, models, fields, _
from datetime import datetime



class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Retention"
    _rec_name = "name"
    _check_company_auto = True

    def sequence_iva_retention(self):
        sequence = self.env["ir.sequence"].search([("code", "=", "retention.iva.control.number")])
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {"name": "Numero de control retenciones IVA", "code": "retention.iva.control.number", "padding": 5}
            )
        return sequence

    def sequence_islr_retention(self):
        sequence = self.env["ir.sequence"].search([("code", "=", "retention.islr.control.number")])
        if not sequence:
            sequence = self.env["ir.sequence"].create(
                {"name": "Numero de control retenciones ISLR", "code": "retention.islr.control.number", "padding": 5}
            )
        return sequence

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    name = fields.Char(
        "Description",
        size=64,
        states={"draft": [("readonly", False)]},
        help="Descripción del Comprobante",
    )
    code = fields.Char(
        size=32,
        states={"draft": [("readonly", False)]},
        help="Referencia del Comprobante",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("emitted", "Emitted"), ("cancel", "Cancel")],
        index=True,
        default="draft",
        help="Estatus del Comprobante",
    )
    type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
        ]
    )
    type = fields.Selection(
        [
            ("out_invoice", "Out invoice"),
            ("in_invoice", "In invoice"),
            ("out_refund", "Out refund"),
            ("in_refund", "In refund"),
            ("out_debit", "Out debit"),
            ("in_debit", "In debit"),
            ("out_contingence", "Out contingence"),
            ("in_contingence", "In contingence"),
        ],
        "Tipo de retención",
        help="Tipo del Comprobante",
        required=True,
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Social reason",
        required=True,
        states={"draft": [("readonly", False)]},
        help="Social reason",
    )
    number = fields.Char("Voucher Number")
    correlative = fields.Char(readonly=True)
    date = fields.Date(
        "Fecha Comprobante",
        states={"draft": [("readonly", False)]},
        help="Date of issuance of the withholding voucher by the external party.",
    )
    date_accounting = fields.Date(
        "Fecha Contable",
        states={"draft": [("readonly", False)]},
        help="Date of arrival of the document and date to be used to make the accounting record Keep blank to use current date.",
    )
    # amount_base_ret = fields.Float(
    #     compute=amount_ret_all,
    #     string="Base Imponible",
    #     help="Total de la base retenida",
    #     store=True,
    # )
    # amount_imp_ret = fields.Float(compute=amount_ret_all, store=True, string="Total IVA")
    # total_tax_ret = fields.Float(
    #     compute=amount_ret_all,
    #     store=True,
    #     string="IVA retenido",
    #     help="Total del impuesto Retenido",
    # )

    def action_draft(self):
        self.write({'state': 'draft'})
        return True

    def action_emitted(self):
        today = datetime.now()
        if not self.date_accounting:
            self.date_accounting = str(today)
        if not self.date:
            self.date = str(today)
        if self.type in ['in_invoice', 'in_refund', 'in_debit']:
            #REVISAR CUANDO TOQUE EL FLUJO
            self.make_accounting_entries(False)
        elif self.type in ['out_invoice', 'out_refund', 'out_debit']:
            if not self.number:
                raise exceptions.UserError("Introduce el número de comprobante")
            self.make_accounting_entries(False)
        return self.write({'state': 'emitted'})

    def action_cancel(self):
        for line in self.retention_line:
            if line.move_id and line.move_id.line_ids:
                line.move_id.line_ids.remove_move_reconcile()
            if line.move_id and line.move_id.state != 'draft':
                line.move_id.button_cancel()
            if line.retention_id.type_retention in ['iva']:
                line.invoice_id.write({'apply_retention_iva': False, 'iva_voucher_number': None})
            if line.retention_id.type_retention in ['islr']:
                line.invoice_id.write({'apply_retention_islr': False, 'islr_voucher_number': None})
            #line.move_id.unlink()
        self.write({'state': 'cancel'})
        return True
