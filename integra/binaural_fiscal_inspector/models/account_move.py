from odoo import fields, models, _, api
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


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
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            self = self.sudo()
            return super()._post(soft)
        return super()._post(soft)

    def write(self, vals):
        fields_computes = [
            "needed_terms_dirty",
            "message_main_attachment_id",
            "invoice_has_outstanding",
        ]
        if not any(field in vals for field in fields_computes):
            if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate"):
                raise UserError(_("No tienes permiso para sobreescribir esta factura"))
        return super().write(vals)
