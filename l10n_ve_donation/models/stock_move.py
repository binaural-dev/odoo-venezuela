from odoo import models, api, fields, Command
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    def _prepare_account_move_vals(
        self,
        credit_account_id,
        debit_account_id,
        journal_id,
        qty,
        description,
        svl_id,
        cost,
    ):
        """Override to propagate donation info to the generated account move.

        The header (`vals["partner_id"]`) is left untouched here -- Odoo
        core (`_get_partner_id_for_valuation_lines`) already resolves it to
        the real counterparty, which is exactly what the donation
        certificate needs to show (see account_move.py/sale_order.py).
        `stock.scrap` has no real contact for its beneficiary/patient, so
        the header simply stays unset for that flow instead of duplicating
        the company as both donor and beneficiary."""
        if self.scrap_id and self.scrap_id.is_donation and self.scrap_id.donation_reason:
            description = f"{description} - {self.scrap_id.donation_reason}"

        vals = super()._prepare_account_move_vals(
            credit_account_id,
            debit_account_id,
            journal_id,
            qty,
            description,
            svl_id,
            cost,
        )

        if self.scrap_id and self.scrap_id.is_donation:
            vals.update(
                {
                    "is_donation": True,
                    "ref": self.scrap_id.donation_reason or vals.get("ref"),
                }
            )
        return vals
