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
        the picking's real counterparty (the beneficiary, for an outgoing
        donation delivery), which is exactly what the donation certificate
        needs to show.

        Each LINE in `vals["line_ids"]`, however, must be forced to the
        company partner: `stock_account._generate_valuation_lines_data`
        stamps that same beneficiary on every line it generates, and
        `account_move._check_partner_donation()` (line-level validation,
        intentionally left intact) rejects any line whose partner is not the
        company. Without this, validating a donation delivery that has a
        recipient set fails for any real_time-valuated category: stock
        accounting posts the valuation move via `_post()`, not
        `action_post()`, so `action_post()`'s own line-forcing loop never
        runs for this path.

        `stock.scrap` has no real contact for its beneficiary/patient (see
        the header limitation documented on `_is_donation_delivery`/the
        certificate template), so the header stays unset for that flow as
        before -- only the line-level forcing below applies equally to both
        flows."""
        is_donation_scrap = bool(self.scrap_id and self.scrap_id.is_donation)
        is_donation_picking = bool(self.picking_id and self.picking_id._is_donation_delivery())

        if is_donation_scrap and self.scrap_id.donation_reason:
            description = f"{description} - {self.scrap_id.donation_reason}"
        elif is_donation_picking and self.picking_id.donation_reason:
            description = f"{description} - {self.picking_id.donation_reason}"

        vals = super()._prepare_account_move_vals(
            credit_account_id,
            debit_account_id,
            journal_id,
            qty,
            description,
            svl_id,
            cost,
        )

        if is_donation_scrap or is_donation_picking:
            company_partner = self.env.company.partner_id
            vals["line_ids"] = [
                (command[0], command[1], {**command[2], "partner_id": company_partner.id})
                if command[0] == 0 else command
                for command in vals.get("line_ids", [])
            ]
            reason = self.scrap_id.donation_reason if is_donation_scrap else self.picking_id.donation_reason
            vals.update(
                {
                    "is_donation": True,
                    "ref": reason or vals.get("ref"),
                }
            )
        return vals
