from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Solo para controlar la visibilidad del campo de abajo en la vista
    # (invisible salvo que la compañía tenga activado el uso de ND/NC para
    # diferencial cambiario).
    l10n_ve_exchange_use_nd_nc = fields.Boolean(related='company_id.l10n_ve_exchange_use_nd_nc')

    # No hay campo equivalente nativo para notas de débito (a diferencia de
    # `refund_sequence_id`, que `od_journal_sequence` ya provee para notas
    # de crédito en cualquier diario) -- por eso este SÍ es necesario.
    l10n_ve_exchange_debit_note_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Exchange Debit Note Sequence',
        check_company=True,
        copy=False,
        help="Sequence used to number exchange rate difference Debit Notes "
             "(Nota de Débito). Configure the prefix, padding, and periodicity "
             "from the sequence record itself.",
    )
