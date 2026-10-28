from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountRetention(models.Model):
    _inherit = "account.retention"

    exchange_difference_treatment = fields.Selection(
        selection_add=[("note", "Debit/Credit note")],
        ondelete={"note": "set default"},
    )

    def _get_default_exchange_difference_treatment(self):
        """The initial treatment comes from the configuration of the customer: a note when the
        company uses exchange difference notes and the contact accepts them, the entry otherwise."""
        self.ensure_one()
        company = self.company_id
        if (
            self.type == "out_invoice"
            and self.partner_id
            and company.l10n_ve_exchange_use_nd_nc
            and company._l10n_ve_exchange_note_allowed_for_partner(self.partner_id)
        ):
            return "note"
        return super()._get_default_exchange_difference_treatment()

    def _get_reconcile_extra_context(self, retention_line):
        context = super()._get_reconcile_extra_context(retention_line)
        context["l10n_ve_exchange_note_treatment"] = self.exchange_difference_treatment
        return context

    @api.constrains("exchange_difference_treatment")
    def _check_exchange_difference_treatment_note(self):
        for retention in self.filtered(lambda r: r.exchange_difference_treatment == "note"):
            if not retention.company_id.l10n_ve_exchange_use_nd_nc:
                raise ValidationError(
                    _("The company does not use debit/credit notes for the exchange difference.")
                )
