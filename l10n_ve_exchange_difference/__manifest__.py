{
    'name': 'Venezuela - Diferencial cambiario como Notas de Débito/Crédito',
    'version': '19.0.0.0.2',
    'category': 'Accounting/Localizations',
    'summary': 'Document exchange-rate differences on customer invoices as real fiscal Debit/Credit Notes',
    'description': """
Venezuelan localization module that documents the exchange difference of
customer invoices as real fiscal Debit/Credit Notes, instead of the generic,
internal accounting entry Odoo creates by default.

How it works:

- Odoo's native reconciliation runs untouched -- its own exchange
  difference computation (`_prepare_exchange_difference_move_vals`) is
  intercepted for qualifying CUSTOMER invoice/note lines, and the exact
  amount it determined is redirected to a real Debit Note (gain, dedicated
  journal) or Credit Note (loss, same sales journal as the invoice) instead
  of Odoo's generic internal entry.
- The note is created and closed synchronously, at the same point in the
  reconciliation transaction where Odoo creates its own generic entry --
  linked to the source invoice and reconciled immediately against the
  residual.
- If the invoice-payment reconciliation that originated the note is broken,
  the note (already posted, with a real sequence number) is reversed
  automatically -- never cancelled or deleted. Unreconciling the note
  directly is blocked.
- Only applies to CUSTOMER invoices/credit notes. Any other case (vendor
  bills, manual entries) follows Odoo's native behavior unmodified.

Configuration:

- Enabled per company (`Settings > Accounting`).
- Dedicated product (with an exempt tax) for the Debit/Credit Note line.
- Dedicated pricelist (in the company's own currency) for the Debit/Credit
  Note, required by `account_invoice_pricelist`.
- Dedicated sales journal, with its own sequence for Debit Notes.
    """,
    'author': 'Binaural',
    'depends': [
        'account', 'l10n_ve_accountant', 'od_journal_sequence', 'l10n_ve_invoice',
        'l10n_ve_igtf', 'account_invoice_pricelist',
    ],
    'data': [
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
