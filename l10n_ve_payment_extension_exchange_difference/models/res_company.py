from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _l10n_ve_exchange_note_allowed_for_partner(self, partner):
        """The treatment chosen on the retention voucher overrides the configuration of the contact
        for the reconciliation of its payment: `note` forces the note, `entry` the exchange entry."""
        treatment = self.env.context.get("l10n_ve_exchange_note_treatment")
        if treatment == "note":
            return True
        if treatment == "entry":
            return False
        return super()._l10n_ve_exchange_note_allowed_for_partner(partner)
