from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = "account.move"

    is_purchase_international = fields.Boolean(
        related="journal_id.is_purchase_international",
        string="Is International Purchase",
    )

    @api.onchange("journal_id")
    def _onchange_journal_id_reset_international_exempt(self):
        """
        Reset the international purchase exempt product field to False
        when the journal is not an international purchase journal
        """
        for move in self:
            if not move.journal_id.is_purchase_international:
                move.invoice_line_ids.update(
                    {"international_purchase_exempt_product": False}
                )
