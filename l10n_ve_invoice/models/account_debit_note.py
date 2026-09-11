from odoo import api, models, fields


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    filter_enabled = fields.Boolean(string='Filter Enabled', compute='_compute_filter_enabled')

    l10n_ve_out_of_fiscal_period_warning = fields.Boolean(
        string='Out of Fiscal Period',
        compute='_compute_l10n_ve_out_of_fiscal_period_warning',
        help="True when this Debit Note's own date (`date`) falls in a "
             "different month/year than `invoice_date_display` (the "
             "vendor bill's own declared fiscal date -- `date`/accounting "
             "date is only DERIVED from it, and can lag behind when the "
             "bill is posted later than issued) of the vendor bill it "
             "debits. Warning only -- never blocks creating the note.",
    )

    @api.depends('journal_type')
    def _compute_filter_enabled(self):
        move = self.env['account.move'].browse(self.env.context.get('active_id'))
        config = move.company_id.auto_select_debit_note_journal
        for record in self:
            record.filter_enabled = config

    @api.depends('date', 'move_ids', 'move_ids.invoice_date_display')
    def _compute_l10n_ve_out_of_fiscal_period_warning(self):
        for record in self:
            moves = record.move_ids.filtered(lambda m: m.move_type == 'in_invoice')
            record.l10n_ve_out_of_fiscal_period_warning = bool(
                record.date
                and moves
                and any(
                    m.invoice_date_display
                    and (record.date.year, record.date.month) != (m.invoice_date_display.year, m.invoice_date_display.month)
                    for m in moves
                )
            )

    def _prepare_default_values(self, move):
        """Corrects core's own date assignment (`account_debit_note`,
        `_prepare_default_values`), which sets BOTH `invoice_date_display`
        (left untouched -- so `copy()` just carries over `move`'s own
        value) and `invoice_date` to `self.date or move.date` -- i.e. the
        NOTE's own date, not the ORIGIN's.

        In this codebase `invoice_date` is repurposed as the "Rate Date"
        (`l10n_ve_accountant`/`l10n_ve_invoice`, used ONLY for exchange
        rate lookups -- `invoice_date_display` is what actually drives the
        accounting `date` via `_get_accounting_date_source`). Collapsing
        `invoice_date` to the Debit Note's own date makes it price at a
        DIFFERENT rate than the invoice it's meant to correct/complement,
        manufacturing a spurious exchange difference between the two
        documents that shouldn't exist -- they're the same underlying
        transaction. Overriding it back to `move.invoice_date` keeps the
        SAME rate as the origin.

        `invoice_date_display` is the Note's own declared fiscal date
        (what the "Out of Fiscal Period" warning above and the wizard's
        own `date` field are about) -- so it must be `self.date`
        (or `move.date`, same fallback core uses), not silently inherited
        from the origin via `copy()`.
        """
        default_values = super()._prepare_default_values(move)
        if move.is_invoice(include_receipts=True):
            default_values['invoice_date_display'] = self.date or move.date
            default_values['invoice_date'] = move.invoice_date
        return default_values