from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_ve_exchange_allow_note = fields.Boolean(
        string='Allow Exchange Difference Note',
        company_dependent=True,
        default=False,
        help="When checked, this customer's invoices settle their exchange "
             "difference through a Debit/Credit Note. When unchecked, "
             "Odoo's generic exchange difference entry is used instead.",
    )
    l10n_ve_exchange_show_allow_note = fields.Boolean(
        string='Show Allow Exchange Difference Note',
        compute='_compute_l10n_ve_exchange_show_allow_note',
        help="Technical field: whether the current company has 'Validate "
             "Customer Allows Exchange Difference Note' enabled -- used "
             "purely to show/hide `l10n_ve_exchange_allow_note` on the "
             "contact form, never persisted or read anywhere else. Not "
             "company-dependent by record (a partner has no single fixed "
             "company): always reflects `env.company`, the same company "
             "whose settings the form the user is looking at belongs to.",
    )

    @api.depends_context('company')
    def _compute_l10n_ve_exchange_show_allow_note(self):
        show = self.env.company.l10n_ve_exchange_validate_partner_note
        for partner in self:
            partner.l10n_ve_exchange_show_allow_note = show
