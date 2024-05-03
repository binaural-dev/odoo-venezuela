from odoo import fields, models, _, api


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_has_outstanding = fields.Boolean(
        groups="account.group_account_invoice,account.group_account_readonly,binaural_fiscal_inspector.group_fiscal_inspectorate,binaural_fiscal_inspector.group_fiscal_inspectorate_editable",
    )
    invoice_outstanding_credits_debits_widget = fields.Binary(
        groups="account.group_account_invoice,account.group_account_readonly,binaural_fiscal_inspector.group_fiscal_inspectorate,binaural_fiscal_inspector.group_fiscal_inspectorate_editable",
    )
    invoice_payments_widget = fields.Binary(
        groups="account.group_account_invoice,account.group_account_readonly,binaural_fiscal_inspector.group_fiscal_inspectorate,binaural_fiscal_inspector.group_fiscal_inspectorate_editable",
    )

    def _post(self, soft=True):
        if self.env.user.has_group('binaural_fiscal_inspector.group_fiscal_inspectorate_editable'):
            self = self.sudo()
            return super()._post(soft)
        return super()._post(soft)
    
    def write(self, vals):
        if self.env.user.has_group('binaural_fiscal_inspector.group_fiscal_inspectorate'):
            raise UserError(_("No tienes permiso para sobreescribir esta factura"))
        return super().write(vals)