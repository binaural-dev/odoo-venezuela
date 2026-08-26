from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_ve_exchange_diff_entry = fields.Boolean(
        string='Is Exchange Difference Note/Entry',
        default=False,
        copy=False,
    )
    l10n_ve_exchange_original_id = fields.Many2one(
        'account.move',
        string='Reversed Exchange Difference Debit Note',
        copy=False,
        check_company=True,
        help="Credit Note that reverses the original exchange difference "
             "Debit Note. Only set on automatically generated reversal "
             "entries.",
    )
    l10n_ve_exchange_is_credit_note = fields.Boolean(
        string='Is Direct Exchange Difference Credit Note',
        default=False,
        copy=False,
        help="Set when this note was created directly as a Credit Note "
             "(exchange gain), as opposed to being the reversal of a Debit "
             "Note (see `l10n_ve_exchange_original_id`).",
    )
    l10n_ve_exchange_invoice_id = fields.Many2one(
        'account.move',
        string='Source Customer Invoice (Exchange Difference)',
        copy=False,
        check_company=True,
        help="Original CUSTOMER invoice/note whose residual (in company "
             "currency) this exchange difference Debit/Credit Note "
             "settles.",
    )
    l10n_ve_exchange_payment_id = fields.Many2one(
        'account.move',
        string='Settled Payment (Exchange Difference)',
        copy=False,
        check_company=True,
        help="Payment entry whose reconciliation against the source "
             "invoice originated this exchange difference Debit/Credit "
             "Note. Used to tell apart the note from a SPECIFIC partial "
             "payment from a note already issued for the same invoice "
             "from an EARLIER partial payment -- an invoice paid in "
             "several installments can accrue a distinct exchange "
             "difference note per installment.",
    )

    def _is_exchange_debit_note(self):
        """True if this document is an exchange difference Debit Note
        issued by this module -- never a native Odoo generic entry tagged
        with `l10n_ve_exchange_diff_entry`."""
        return (
            self.move_type == 'out_invoice'
            and self.l10n_ve_exchange_diff_entry
            and not self.l10n_ve_exchange_original_id
            and not self.l10n_ve_exchange_is_credit_note
        )

    def _is_exchange_credit_note(self):
        """True if this document is an exchange difference Credit Note
        (issued directly, or as the reversal of our own Debit Note)."""
        return self.move_type == 'out_refund' and (
            bool(self.l10n_ve_exchange_original_id) or bool(self.l10n_ve_exchange_is_credit_note)
        )

    @api.depends(
        'posted_before', 'state', 'journal_id', 'date', 'move_type',
        'origin_payment_id', 'l10n_ve_exchange_diff_entry',
        'l10n_ve_exchange_original_id',
    )
    def _compute_name_by_sequence(self):
        """Numbers exchange difference Debit/Credit Notes with their own
        sequence (`l10n_ve_exchange_debit_note_sequence_id` for Debit
        Notes, native `refund_sequence_id` for Credit Notes) instead of
        the journal's normal sequence -- hooked here, not in
        `_compute_name`, because `od_journal_sequence` already replaced
        that native compute."""
        exchange_moves = self.filtered(
            lambda m: m._is_exchange_debit_note() or m._is_exchange_credit_note()
        )
        other_moves = self - exchange_moves
        if other_moves:
            super(AccountMove, other_moves)._compute_name_by_sequence()

        for move in exchange_moves:
            if move.state != 'posted':
                move.name = move.name or '/'
                continue
            if move.name and move.name != '/':
                continue

            sequence = (
                move.journal_id.l10n_ve_exchange_debit_note_sequence_id
                if move._is_exchange_debit_note()
                else move.journal_id.refund_sequence_id
            )

            if sequence and move.date:
                move.name = sequence.next_by_id()
            else:
                super(AccountMove, move)._compute_name_by_sequence()

    def _sequence_matches_date(self):
        """Exchange difference Debit/Credit Notes (and their reversals)
        use their own dedicated sequence, unrelated to the journal's --
        validating them against the native sequence's date makes no
        sense."""
        if self.l10n_ve_exchange_diff_entry or self.l10n_ve_exchange_original_id:
            return True
        return super()._sequence_matches_date()

    def js_remove_outstanding_partial(self, partial_id):
        """If breaking this reconciliation actually unreconciles the
        invoice-payment pair that generated an exchange difference
        Debit/Credit Note, reverses that note -- an already posted fiscal
        document cannot simply be cancelled. Also blocks breaking the
        note<->invoice/payment reconciliation directly (that should only
        be undone as a consequence of the above).

        `super()` is called FIRST, and the note is only reversed if
        `partial` no longer exists afterwards. A subclass earlier in the
        MRO (`l10n_ve_igtf`, for an advance-payment reconciliation) can
        return a wizard action instead of actually unreconciling -- if we
        reversed the note before calling `super()`, the note would end up
        reversed even though the user hasn't confirmed anything yet and
        the original reconciliation is still intact.
        """
        self.ensure_one()
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        related_moves = partial.debit_move_id.move_id | partial.credit_move_id.move_id

        if any(related_moves.mapped('l10n_ve_exchange_diff_entry')):
            raise UserError(_(
                "You cannot directly unreconcile an exchange difference "
                "Debit/Credit Note. To undo it, break the original "
                "reconciliation between the invoice and the payment -- the "
                "note will be reversed automatically."
            ))

        invoice = related_moves.filtered(
            lambda m: m.move_type in ('out_invoice', 'out_refund')
        )[:1]
        payment = related_moves - invoice

        result = super().js_remove_outstanding_partial(partial_id)

        if invoice and not partial.exists():
            # Buscada por (factura, pago) y no solo por factura: una misma
            # factura pagada en varias cuotas puede acumular una ND/NC
            # distinta por cada pago parcial (ver `l10n_ve_exchange_payment_id`)
            # -- al romper la conciliación de UN pago puntual, solo debe
            # revertirse la nota de ESE pago.
            note = self.env['account.move'].search([
                ('l10n_ve_exchange_invoice_id', '=', invoice.id),
                ('l10n_ve_exchange_payment_id', '=', payment.id),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if note:
                note._reverse_exchange_note()

        return result

    def _reverse_exchange_note(self):
        """Reverses this exchange difference Debit/Credit Note because the
        invoice/payment reconciliation that originated it is being broken
        -- an already posted fiscal document (with a real sequence number)
        gets reversed, never cancelled or deleted."""
        self.ensure_one()
        if self.state == 'draft':
            self.unlink()
            return
        if self.state != 'posted':
            return
        self.with_context(
            move_reverse_cancel=True,
            l10n_ve_skip_refund_origin_validation=True,
        )._reverse_moves(
            default_values_list=[{
                'ref': _('Reversal of: %s', self.name),
                'l10n_ve_exchange_diff_entry': True,
                'l10n_ve_exchange_invoice_id': self.l10n_ve_exchange_invoice_id.id,
            }],
            cancel=True,
        )

    def _reverse_moves(self, default_values_list=None, cancel=False):
        """When reversing any of this module's own exchange difference
        notes -- a Debit Note (ND) OR a Credit Note (NC, whether issued
        directly or itself already a reversal of a ND) -- links the
        reversal via `l10n_ve_exchange_original_id` instead of letting it
        be numbered with the normal sequence.

        Checked via `l10n_ve_exchange_diff_entry` (true for ANY of our
        own notes), not `_is_exchange_debit_note()` alone: reversing a
        NC produces an `out_invoice` reversal that, without
        `l10n_ve_exchange_original_id` set, would satisfy
        `_is_exchange_debit_note()` on its own merits (right
        `move_type`, `diff_entry` copied over, no `original_id`/
        `is_credit_note` set) -- misclassifying a mere reversal as a
        genuine new ND, consuming the (already scarce) dedicated ND
        sequence for a document that isn't actually one."""
        if default_values_list is None:
            default_values_list = [{} for _ in self]

        for move, default_values in zip(self, default_values_list):
            if (
                move.l10n_ve_exchange_diff_entry
                and move.move_type in ('out_invoice', 'out_refund')
                and move.company_id.l10n_ve_exchange_use_nd_nc
            ):
                default_values.update({
                    'l10n_ve_exchange_original_id': move.id,
                    'name': '/',
                })

        return super()._reverse_moves(default_values_list, cancel=cancel)
