from odoo import api, models, fields


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'
    filter_enabled = fields.Boolean(string='Filter Enabled', compute='_compute_filter_enabled')

    l10n_ve_out_of_fiscal_period_warning = fields.Boolean(
        string='Out of Fiscal Period',
        compute='_compute_l10n_ve_out_of_fiscal_period_warning',
        help="True when this Debit Note's own date (`date`) falls in a "
             "different tax period than `invoice_date_display` (the "
             "vendor bill's own declared fiscal date -- `date`/accounting "
             "date is only DERIVED from it, and can lag behind when the "
             "bill is posted later than issued) of the vendor bill it "
             "debits. Period boundaries follow `account.move."
             "_get_period_limit` (the same rule `_compute_entry_in_period` "
             "uses), so a `special` taxpayer's two halves of a month "
             "count as different periods. Warning only -- never blocks "
             "creating the note.",
    )

    @api.depends('journal_type')
    def _compute_filter_enabled(self):
        move = self.env['account.move'].browse(self.env.context.get('active_id'))
        config = move.company_id.auto_select_debit_note_journal
        for record in self:
            record.filter_enabled = config

    @api.depends('date', 'move_ids', 'move_ids.invoice_date_display', 'move_ids.company_id.taxpayer_type')
    def _compute_l10n_ve_out_of_fiscal_period_warning(self):
        AccountMove = self.env['account.move']
        for record in self:
            moves = record.move_ids.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund'))
            record.l10n_ve_out_of_fiscal_period_warning = bool(
                record.date
                and moves
                and any(
                    m.invoice_date_display
                    and not AccountMove._same_fiscal_period(
                        record.date, m.invoice_date_display, m.company_id.taxpayer_type
                    )
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
        DIFFERENT rate than the bill it's meant to correct/complement,
        manufacturing a spurious exchange difference between the two
        documents that shouldn't exist -- they're the same underlying
        transaction. Overriding it back to `move.invoice_date` keeps the
        SAME rate as the origin.

        Applies to BOTH purchase and sale documents -- a Debit Note is the
        same underlying transaction as its origin regardless of direction,
        so its Rate Date must not depend on which side of the ledger it's
        on. `l10n_ve_accountant._onchange_invoice_date_display` used to
        re-derive `invoice_date` from `invoice_date_display` for every
        sale document, which would silently undo this override the moment
        someone opened the note and touched the form -- that onchange is
        now itself scoped to skip documents with an origin
        (`debit_origin_id`/`reversed_entry_id`), so both code paths agree.

        DELIBERATELY not scoped to purchases only (an earlier iteration
        of this fix was): scoping it to purchases would have LEFT that
        exact inconsistency in place for sale documents instead of
        closing it -- see PR #1283 discussion (tarea 81554) for the
        explicit decision to apply this to both directions and fix the
        onchange at its root instead.

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