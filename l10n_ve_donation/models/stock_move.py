from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _is_donation_delivery_move(self):
        """The valuation entry is marked as a donation only for deliveries
        created from the Donations menu: `is_donation and not sale_id and
        outgoing`. Deliveries that come from a donation sale order are
        excluded on purpose, their accounting must not change."""
        self.ensure_one()
        picking = self.picking_id
        return bool(
            picking
            and picking.is_donation
            and not picking.sale_id
            and picking.picking_type_code == "outgoing"
        )

    def _get_account_move_line_vals(self):
        """Force the company partner on each line of the valuation entry of
        a donation delivery.

        The header partner is left untouched: the core
        (`_get_partner_id_for_valuation_lines`) already resolves it to the
        picking's real counterparty (the beneficiary), which is exactly what
        the donation certificate needs to show. The lines, however, get
        their partner computed from that header, and
        `account.move._check_partner_donation()` (line-level validation,
        intentionally left intact) rejects any line whose partner is not the
        company."""
        vals_list = super()._get_account_move_line_vals()
        if not self._is_donation_delivery_move():
            return vals_list
        company_partner = self.company_id.partner_id
        reason = self.picking_id.donation_reason
        for vals in vals_list:
            vals["partner_id"] = company_partner.id
            if reason:
                vals["name"] = f"{vals['name']} - {reason}"
        return vals_list

    def _create_account_move(self):
        """The core creates ONE journal entry for the whole recordset, so
        the donation deliveries are valued apart from the rest: only their
        entry is marked `is_donation` and takes the donation reason as its
        reference. The mark is written explicitly (no `default_is_donation`
        in the context), so that no valuation entry that is not a donation
        can inherit it."""
        donation_moves = self.filtered(lambda move: move._is_donation_delivery_move())
        # A `default_is_donation` leaked into the context (e.g. by an action
        # of another module) must not mark the entries that are not donations.
        account_moves = super(
            StockMove, (self - donation_moves).with_context(default_is_donation=False)
        )._create_account_move()
        if not donation_moves:
            return account_moves
        donation_entries = super(StockMove, donation_moves)._create_account_move()
        for entry in donation_entries:
            reasons = donation_moves.filtered(
                lambda move: move.account_move_id == entry
            ).picking_id.mapped("donation_reason")
            vals = {"is_donation": True}
            reason = " - ".join(dict.fromkeys(filter(None, reasons)))
            if reason:
                vals["ref"] = reason
            entry.write(vals)
        return account_moves | donation_entries
