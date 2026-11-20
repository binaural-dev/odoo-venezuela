from odoo import fields, models


class L10nVeReconcileAssistantItem(models.TransientModel):
    _name = "l10n_ve.reconcile.assistant.item"
    _description = "Reconciliation assistant line"
    _order = "sequence, id"

    wizard_id = fields.Many2one("l10n_ve.reconcile.assistant", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    origin_line_id = fields.Many2one("account.move.line", readonly=True)
    origin_move_id = fields.Many2one(related="origin_line_id.move_id")
    origin_currency_id = fields.Many2one(related="origin_line_id.currency_id")
    invoice_id = fields.Many2one("account.move", readonly=True)
    currency_id = fields.Many2one(related="invoice_id.currency_id")
    origin_conditions = fields.Char(readonly=True)
    conversion_date = fields.Date(readonly=True)
    rate = fields.Float(digits=(16, 6), readonly=True)
    widget_amount = fields.Monetary(readonly=True)
    apply_amount = fields.Monetary(readonly=True)
    igtf_amount = fields.Monetary(readonly=True)
    pending_after = fields.Monetary(readonly=True)
    origin_before = fields.Monetary(
        currency_field="origin_currency_id", readonly=True,
        help="What the payment or advance has before this row. Each invoice converts only what is left of "
             "it, with its own date and rate rule, so the amount offered changes with the order.")
    origin_applied = fields.Monetary(
        currency_field="origin_currency_id", readonly=True,
        help="What this row takes from the payment or advance, in its own currency and including the IGTF "
             "of the cross entry.")
    origin_remaining = fields.Monetary(
        currency_field="origin_currency_id", readonly=True,
        help="What is left of the payment or advance after this row.")
