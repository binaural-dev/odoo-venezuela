from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _is_donation_move(self):
        """The valuation entry of the move is the one of a donation: the move
        belongs to a picking created from the Donations menu (`is_donation`,
        no sale order) that is a delivery or a reception. The deliveries that
        come from a donation sale order are excluded on purpose, their
        accounting must not change. A reception only counts when the company
        has received donations accounts: without them it is a regular
        reception and its entry is left as it was."""
        self.ensure_one()
        picking = self.picking_id
        if not (picking and picking.is_donation and not picking.sale_id):
            return False
        code = picking.picking_type_code
        return code == "outgoing" or (
            code == "incoming" and bool(self.company_id.donation_income_account_ids)
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
        company. The lines of a reception keep the donor: they are the ones
        of a donation received."""
        vals_list = super()._get_account_move_line_vals()
        if not (self._is_donation_move() and self.picking_id.picking_type_code == "outgoing"):
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
        the donation pickings are valued apart from the rest: only their
        entry is marked `is_donation` and takes the donation reason as its
        reference. The mark is written explicitly (no `default_is_donation`
        in the context), so that no valuation entry that is not a donation
        can inherit it. The mark of a reception is the one that makes its
        entry a donation received, so that it is not reversed or reset to
        draft by whoever is not a Donation Manager."""
        donation_moves = self.filtered(lambda move: move._is_donation_move())
        # A `default_is_donation` leaked into the context (e.g. by an action
        # of another module) must not mark the entries that are not donations.
        account_moves = super(
            StockMove, (self - donation_moves).with_context(default_is_donation=False)
        )._create_account_move()
        if not donation_moves:
            return account_moves
        # Deliveries and receptions are valued apart too: the core creates one
        # entry for the whole recordset and a mixed one would be a donation
        # received.
        donation_entries = self.env["account.move"]
        for code in ("outgoing", "incoming"):
            moves = donation_moves.filtered(lambda move: move.picking_id.picking_type_code == code)
            if not moves:
                continue
            entries = super(StockMove, moves)._create_account_move()
            for entry in entries:
                reasons = moves.filtered(
                    lambda move: move.account_move_id == entry
                ).picking_id.mapped("donation_reason")
                vals = {"is_donation": True}
                reason = " - ".join(dict.fromkeys(filter(None, reasons)))
                if reason:
                    vals["ref"] = reason
                entry.write(vals)
            donation_entries |= entries
        return account_moves | donation_entries
