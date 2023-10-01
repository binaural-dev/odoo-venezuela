from odoo import models, fields, api,_
from odoo.exceptions import ValidationError


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

    def button_digital_invoice(self):
        return self.env.ref("invoice_zmart.action_digital_invoice").report_action(self)

    def button_free_form(self):
        if self.journal_id.fiscal:
            self.write({"printed": True})
            return self.env.ref("invoice_zmart.action_invoice_free_form_bs").report_action(self)
        raise ValidationError(_( 'Cannot print an invoice with a non-fiscal journal'))

    def button_free_form_usd(self):
        if self.journal_id.fiscal:
            self.write({"printed": True})
            return self.env.ref("invoice_zmart.action_invoice_free_form_usd").report_action(self)
        raise ValidationError(_( 'Cannot print an invoice with a non-fiscal journal'))

    def button_invoice_sale_note(self):
        if not self.journal_id.fiscal:
            return self.env.ref("invoice_zmart.action_invoice_sale_note_usd").report_action(self)
        raise ValidationError(_( 'Cannot print an sale note with a fiscal journal'))
    
    def button_invoice_sale_note_bs(self):
        if not self.journal_id.fiscal:
            return self.env.ref("invoice_zmart.action_invoice_sale_note_bs").report_action(self)
        raise ValidationError(_( 'Cannot print an sale note with a fiscal journal'))
    
    def action_post(self):
        res = super().action_post()
        if not self.journal_id.fiscal:
            self.state =  'draft'
            for line in self.invoice_line_ids:
                line.tax_ids = False
            self.state =  'posted'
        return res
    
    def get_total_amount_excluding_taxes(self):
        excluded_tax_ids = [1, 2]
        total_amount_local = 0.0
        total_amount_foreign = 0.0

        for invoice in self:
            products = invoice.invoice_line_ids.filtered(lambda line: not any(tax in line.tax_ids.ids for tax in excluded_tax_ids))
            total_amount_local += sum(products.mapped('price_subtotal'))
            total_amount_foreign += sum(products.mapped('foreign_subtotal'))

        return total_amount_local, total_amount_foreign
    
    def get_total_amount_including_taxes(self):
        included_tax_ids = [1, 2]
        total_amount_local = 0.0
        total_amount_foreign = 0.0

        for invoice in self:
            products = invoice.invoice_line_ids.filtered(lambda line: any(tax in line.tax_ids.ids for tax in included_tax_ids))
            total_amount_local += sum(products.mapped('price_subtotal'))
            total_amount_foreign += sum(products.mapped('foreign_subtotal'))
        return total_amount_local, total_amount_foreign
