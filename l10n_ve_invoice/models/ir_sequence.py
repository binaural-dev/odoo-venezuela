from odoo import _, api, models
from odoo.exceptions import ValidationError

INVOICE_CORRELATIVE_CODE = "invoice.correlative"


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    @api.constrains("code", "company_id", "active")
    def check_sequence_exists(self):
        """Allow only one active invoice correlative sequence per company.

        ``account.move.get_sequence`` searches the sequence by code and company
        and calls ``next_by_id`` on the result, so two active sequences make it
        fail with "Expected singleton" and the company cannot post invoices.
        """
        sequences = self.filtered(
            lambda seq: seq.code == INVOICE_CORRELATIVE_CODE and seq.active
        )
        for sequence in sequences:
            duplicated = self.sudo().with_context(active_test=True).search_count(
                [
                    ("code", "=", INVOICE_CORRELATIVE_CODE),
                    ("company_id", "=", sequence.company_id.id),
                    ("active", "=", True),
                ]
            )
            if duplicated > 1:
                raise ValidationError(
                    _(
                        "There is already an active invoice correlative sequence "
                        "for the company %s. Only one is allowed.",
                        sequence.company_id.display_name or _("(no company)"),
                    )
                )
