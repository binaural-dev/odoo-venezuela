from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ve_exchange_use_nd_nc = fields.Boolean(
        string='Use Debit/Credit Notes for Customer Invoice Exchange Difference',
        default=False,
        help="Applies only to CUSTOMER invoices and credit notes. When "
             "enabled, the exchange difference left open when reconciling "
             "a foreign-currency customer invoice is NOT absorbed by "
             "Odoo's automatic entry -- instead, it is documented with a "
             "real Debit Note (gain) or Credit Note (loss), issued "
             "against the original invoice and reconciled against the "
             "remaining residual.",
    )

    l10n_ve_exchange_note_product_id = fields.Many2one(
        'product.product',
        string='Customer Invoice Exchange Difference Note Product',
        domain=[('type', '=', 'service')],
        help="Product used as the line of exchange difference Debit/Credit "
             "Notes for CUSTOMER invoices. Must be a service, its income "
             "and expense accounts must be the company's exchange "
             "gain/loss accounts, and its sale tax must be the default "
             "sale Exempt tax (l10n_ve_accountant: exent_aliquot_sale) -- "
             "the exchange difference is not a VAT base, but "
             "l10n_ve_accountant requires a tax on every line.",
    )

    l10n_ve_exchange_note_pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Customer Invoice Exchange Difference Note Pricelist',
        help="Pricelist used on exchange difference Debit/Credit Notes for "
             "CUSTOMER invoices (`account_invoice_pricelist` requires "
             "every invoice/note to have one whose currency matches the "
             "document's own currency). Must be in the company's own "
             "currency -- these notes are always issued in company "
             "currency, never in the partner's foreign pricelist.",
    )

    @api.constrains('l10n_ve_exchange_use_nd_nc', 'l10n_ve_exchange_note_product_id', 'l10n_ve_exchange_note_pricelist_id')
    def _check_l10n_ve_exchange_use_nd_nc_requires_config(self):
        """With the ND/NC toggle enabled, both the note product and the
        note pricelist are mandatory -- catches an inconsistent
        configuration at SAVE time (this constraint), regardless of how
        it was written (settings screen, direct ORM write, API), instead
        of only surfacing as a `UserError` the next time a customer
        foreign-currency invoice gets paid (`_create_exchange_difference_note`),
        which would fail mid-reconciliation instead of at configuration
        time."""
        for company in self:
            if not company.l10n_ve_exchange_use_nd_nc:
                continue
            missing = []
            if not company.l10n_ve_exchange_note_product_id:
                missing.append(_("Exchange Difference Note Product"))
            if not company.l10n_ve_exchange_note_pricelist_id:
                missing.append(_("Exchange Difference Note Pricelist"))
            if missing:
                raise ValidationError(_(
                    "With 'Use Debit/Credit Notes for Customer Invoice Exchange "
                    "Difference' enabled, the following must also be configured: "
                    "%(missing)s.",
                    missing=", ".join(missing),
                ))

    @api.constrains('l10n_ve_exchange_note_pricelist_id')
    def _check_l10n_ve_exchange_note_pricelist_id(self):
        """The exchange difference note pricelist must be denominated in
        the company's own currency -- exchange difference Debit/Credit
        Notes are always created in company currency
        (`_create_exchange_difference_note`), so a pricelist in any other
        currency would violate `account_invoice_pricelist`'s own
        constraint (`pricelist_id.currency_id == move.currency_id`) the
        moment a note tried to use it."""
        for company in self:
            pricelist = company.l10n_ve_exchange_note_pricelist_id
            if not pricelist:
                continue
            if pricelist.currency_id != company.currency_id:
                raise ValidationError(_(
                    "The Customer Invoice Exchange Difference Note "
                    "Pricelist ('%(pricelist)s') must be in the company's "
                    "own currency (%(currency)s) -- these notes are always "
                    "issued in company currency.",
                    pricelist=pricelist.display_name,
                    currency=company.currency_id.name,
                ))

    @api.constrains(
        'l10n_ve_exchange_note_product_id',
        'income_currency_exchange_account_id',
        'expense_currency_exchange_account_id',
        'exent_aliquot_sale',
    )
    def _check_l10n_ve_exchange_note_product_id(self):
        """The exchange difference note product must be a service whose
        income AND expense accounts are the company's own exchange
        gain/loss accounts, and whose sale tax is the default sale Exempt
        tax -- this is what lets its Debit/Credit Note lines land on the
        same accounts Odoo natively uses for currency exchange
        differences, regardless of which account a given posting ends up
        using."""
        for company in self:
            product = company.l10n_ve_exchange_note_product_id
            if not product:
                continue

            if product.type != 'service':
                raise ValidationError(_(
                    "The Customer Invoice Exchange Difference Note Product "
                    "('%(product)s') must be a service.",
                    product=product.display_name,
                ))

            accounts = product.with_company(company)._get_product_accounts()
            if accounts.get('income') != company.income_currency_exchange_account_id:
                raise ValidationError(_(
                    "The Customer Invoice Exchange Difference Note Product "
                    "('%(product)s') must have the company's exchange gain "
                    "account as its income account.",
                    product=product.display_name,
                ))
            if accounts.get('expense') != company.expense_currency_exchange_account_id:
                raise ValidationError(_(
                    "The Customer Invoice Exchange Difference Note Product "
                    "('%(product)s') must have the company's exchange loss "
                    "account as its expense account.",
                    product=product.display_name,
                ))

            if not company.exent_aliquot_sale or product.taxes_id != company.exent_aliquot_sale:
                raise ValidationError(_(
                    "The Customer Invoice Exchange Difference Note Product "
                    "('%(product)s') must have the default sale Exempt tax "
                    "assigned (Settings > Binaural Settings > Exempt "
                    "Aliquot).",
                    product=product.display_name,
                ))
