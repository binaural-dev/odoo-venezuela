from odoo import fields, models


class AccountJournal(models.Model):
    """Dedicated sequence to number exchange difference Debit Notes --
    Odoo does not provide an equivalent native field for Debit Notes (as
    opposed to `refund_sequence_id`, which `od_journal_sequence` already
    offers for Credit Notes on any journal)."""
    _inherit = 'account.journal'

    l10n_ve_exchange_use_nd_nc = fields.Boolean(related='company_id.l10n_ve_exchange_use_nd_nc')

    l10n_ve_exchange_debit_note_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Exchange Difference Debit Note Sequence (Customer Invoices)',
        check_company=True,
        copy=False,
        help="Sequence used to number exchange difference Debit Notes. "
             "Configure the prefix, padding, and periodicity from the "
             "sequence record itself.",
    )
