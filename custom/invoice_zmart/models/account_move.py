from odoo import models, fields, api


class AccountInvoice(models.Model):
    _inherit = "account.move"

    printed = fields.Boolean(default=False)
    invoice_type = fields.Char(compute="_compute_invoice_type", store=True, read0nly=True)

    @api.depends("journal_id", "fiscal")
    def _compute_invoice_type(self):
        for move in self:
            if move.journal_id.type == "sale" and move.journal_id.fiscal:
                move.invoice_type = "Factura"
            elif move.journal_id.type == "sale" and not move.journal_id.fiscal:
                move.invoice_type = "Nota de Entrega"
            else:
                move.invoice_type = ""

    def button_free_form(self):
        self.write({"printed": True})
        return self.env.ref("invoice_zmart.action_invoice_free_form_bs").report_action(self)

    def button_free_form_usd(self):
        self.write({"printed": True})
        return self.env.ref("invoice_zmart.action_invoice_free_form_usd").report_action(self)

    def button_invoice_sale_note(self):
        return self.env.ref("invoice_zmart.action_invoice_sale_note_usd").report_action(self)

    def button_invoice_sale_note_bs(self):
        return self.env.ref("invoice_zmart.action_invoice_sale_note_bs").report_action(self)
