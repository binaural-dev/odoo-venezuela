from odoo import fields, models, _, api
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

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
            if len(vals) < 0:
                if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate"):
                    raise UserError(_("No tienes permiso para sobreescribir esta factura"))
        return super().write(vals)

    @api.depends("company_id", "invoice_filter_type_domain")
    def _compute_suitable_journal_ids(self):
        res = super()._compute_suitable_journal_ids()
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            for m in self:
                m.suitable_journal_ids = m.suitable_journal_ids.filtered_domain(
                    [("fiscal", "=", True)]
                )
        return res

    def _search_default_journal(self):
        res = super()._search_default_journal()
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            journal_types = self._get_valid_journal_types()
            company_id = (self.company_id or self.env.company).id
            domain = [
                ("company_id", "=", company_id),
                ("type", "in", journal_types),
                ("fiscal", "=", True),
            ]
            journal = self.env["account.journal"].search(domain, limit=1)
            res = journal
        return res

    def js_remove_outstanding_partial(self, partial_id):
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate"):
            raise ValidationError(_("Your user is not allowed to break reconciliation."))
        return super().js_remove_outstanding_partial(partial_id)