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
        """Override to propagate donation info to the generated account move."""
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
            company_partner = self.env.company.partner_id
            vals.update(
                {
                    "is_donation": True,
                    "partner_id": company_partner.id,
                    "ref": self.scrap_id.donation_reason,
                }
            )
        return vals
