from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    digital_invoice = fields.Boolean(tracking=True)

    digital_invoice_lock = fields.Boolean(
        compute="_compute_digital_invoice_lock",
        string="Digital invoice lock",
    )

    payment_method_code = fields.Many2one(
        "payment.method.tfhka",
        help="This code identifies the payment method. It is used to digitize and link the corresponding payment method.",
    )

    def _compute_digital_invoice_lock(self):
        """Compute if the journal has digital invoices and lock the field with readonly attr."""
        move_obj = self.env["account.move"]
        for journal in self:
            has_moves = journal.digital_invoice_lock = bool(
                move_obj.search_count(
                    [
                        ("journal_id", "=", journal.id),
                        ("is_digitalized", "=", True),
                    ]
                )
            )

            if has_moves:
                journal.digital_invoice = True

    def write(self, vals):
        """Prevent disabling digital_invoice if there are existing digital invoices."""
        if "digital_invoice" in vals and not vals.get("digital_invoice"):
            move_obj = self.env["account.move"]
            for journal in self:
                has_moves = move_obj.search_count(
                    [
                        ("journal_id", "=", journal.id),
                        ("is_digitalized", "=", True),
                    ]
                )
                if has_moves:
                    raise ValidationError(
                        _(
                            "Cannot disable digital billing on a journal with existing digital invoices."
                        )
                    )
        return super().write(vals)
