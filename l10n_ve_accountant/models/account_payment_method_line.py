from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountPaymentMethodLine(models.Model):
    _inherit = "account.payment.method.line"

    payment_account_id = fields.Many2one(default=lambda self: self._default_payment_account_id())

    def _default_payment_account_id(self):
        journal_id = self.env.context.get('default_journal_id')
        if not journal_id:
            return False
        journal = self.env['account.journal'].browse(journal_id)
        if journal.type == 'bank':
            return journal.default_account_id.id
        return False

    @api.model_create_multi
    def create(self, vals_list):
        """Fill payment_account_id from the journal's default_account_id
        BEFORE validation, for every path that creates a bank journal's
        payment method line without one: the native compute
        (account_journal.py's _compute_inbound/outbound_payment_method_line_ids,
        via Command.create with payment_account_id explicitly False),
        account.payment.method._auto_link_payment_methods, and
        payment_provider._ensure_payment_method_line (e.g. activating the
        "Transferencia bancaria" provider).

        Needed so _check_payment_account_id_required_for_bank below can be
        strict (no bypass beyond chart template loading) without breaking
        any of those flows -- confirmed via code review (PR #1344 / task
        81735) that relying on account_journal.py's post-super()
        _fill_payment_account_id_from_default alone is too late: these
        create() calls validate the line before that fill ever runs.
        """
        for vals in vals_list:
            if vals.get('payment_account_id') or not vals.get('journal_id'):
                continue
            journal = self.env['account.journal'].browse(vals['journal_id'])
            if journal.type == 'bank' and journal.default_account_id:
                vals['payment_account_id'] = journal.default_account_id.id
        return super().create(vals_list)

    @api.constrains('payment_account_id', 'journal_id')
    def _check_payment_account_id_required_for_bank(self):
        """Close the gap found in code review (PR #1344 / task 81735):
        account.journal's own _check_payment_method_line_accounts is a
        constrains on the o2m fields inbound/outbound_payment_method_line_ids,
        which Odoo only re-evaluates when that RELATION changes on the
        journal -- not when a line's own payment_account_id is written
        directly (API, data import). This constrains lives on the line
        itself so it can't be bypassed that way.

        In practice this only fires when someone writes payment_account_id
        to empty on purpose: create() above already fills it for every
        legitimate path that creates a bank journal's line without one.
        """
        if self.env.context.get('chart_template_load') or self.env.context.get('install_mode'):
            return
        for line in self:
            if line.journal_id.type == 'bank' and not line.payment_account_id:
                raise UserError(_(
                    "Payment method \"%(method)s\" on bank journal \"%(journal)s\" must have an assigned account.",
                    method=line.name,
                    journal=line.journal_id.display_name,
                ))
