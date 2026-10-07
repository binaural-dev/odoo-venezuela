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

        The picking branch only applies to donation deliveries created from
        the Donations menu: `is_donation and not sale_id and outgoing`.
        Deliveries that come from a donation sale order are excluded on
        purpose, their accounting must not change.

        `vals["is_donation"]` is always written explicitly (also False), so
        that no `default_is_donation` coming from the context can mark a
        valuation entry that is not a donation.

        The donation through `stock.scrap` keeps working: its branch is still
        active (only the scrap view and menu are disabled in the manifest)."""
        is_donation_scrap = bool(self.scrap_id and self.scrap_id.is_donation)
        is_donation_picking = bool(
            self.picking_id
            and self.picking_id.is_donation
            and not self.picking_id.sale_id
            and self.picking_id.picking_type_code == "outgoing"
        )

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

        is_donation = is_donation_scrap or is_donation_picking
        vals["is_donation"] = is_donation
        if is_donation:
            company_partner = self.env.company.partner_id
            vals["line_ids"] = [
                (command[0], command[1], {**command[2], "partner_id": company_partner.id})
                if command[0] == 0 else command
                for command in vals.get("line_ids", [])
            ]
            reason = self.scrap_id.donation_reason if is_donation_scrap else self.picking_id.donation_reason
            vals["ref"] = reason or vals.get("ref")
        return vals
