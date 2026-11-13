from odoo import _, models, api, fields, Command
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    is_donation = fields.Boolean(string="Is Donation", default=False)
    scrap_location_domain = fields.Char(
        string="Picking Type Domain",
        compute="_compute_scrap_location_domain",
    )

    @api.depends("is_donation")
    def _compute_scrap_location_domain(self):
        native_domain = "[('usage', '=', 'inventory')]"
        for move in self:
            if move.is_donation:
                move.scrap_location_domain = "[('is_donation_warehouse', '=', True)]"
            else:
                move.scrap_location_domain = native_domain

    @api.depends("picking_id.location_dest_id", "is_scrap", "is_donation")
    def _compute_location_dest_id(self):
        """A donation is a scrap that goes to the donation warehouse, not to the scrap location.

        In Odoo 20 a scrap is a stock move (``stock.scrap`` is gone) and its destination is the scrap
        location of the company unless an inventory location was chosen.
        """
        super()._compute_location_dest_id()
        for move in self.filtered(lambda move: move.is_scrap and move.is_donation):
            if move.location_dest_id.is_donation_warehouse:
                continue
            location = self.env["stock.location"].search(
                [("is_donation_warehouse", "=", True), ("company_id", "=", move.company_id.id)],
                limit=1,
            )
            if location:
                move.location_dest_id = location

    def _prepare_scrap_move_vals(self):
        vals = super()._prepare_scrap_move_vals()
        if self.is_donation:
            vals["reference"] = self.env["ir.sequence"].next_by_code("stock.donation") or _("New")
        return vals

    def _action_scrap(self):
        self.filtered("is_donation").should_replenish_scrapped = False
        return super()._action_scrap()

    def _create_account_move(self):
        """ Create account move for specific location or analytic.
            This function is a override of the original function to add the donation logic.
        """
        donation_moves = self.filtered(lambda move: move.is_scrap and move.is_donation)
        regular_moves = self - donation_moves
        account_moves = self.env["account.move"]

        if regular_moves:
            account_moves |= super(StockMove, regular_moves)._create_account_move()

        if not donation_moves:
            return account_moves

        aml_vals_list = []
        move_to_link = set()
        company_partner = self.env.company.partner_id

        for move in donation_moves:
            if move._should_create_account_move():
                aml_vals = move._get_account_move_line_vals()
                for val in aml_vals:
                    val["partner_id"] = company_partner.id
                aml_vals_list += aml_vals
                move_to_link.add(move.id)

        if not aml_vals_list:
            return account_moves

        move_vals = {
            "journal_id": donation_moves.company_id.account_stock_journal_id.id,
            "line_ids": [Command.create(aml_vals) for aml_vals in aml_vals_list],
            "date": self.env.context.get("force_period_date") or fields.Date.context_today(self),
        }

        reasons = [', '.join(m.scrap_reason_tag_ids.mapped('name'))
                   for m in donation_moves if m.scrap_reason_tag_ids]
        ref = ' - '.join(filter(None, reasons))

        move_vals.update({
            "is_donation": True,
            "partner_id": company_partner.id,
            "ref": ref
        })

        account_move = self.env["account.move"].sudo().create(move_vals)
        self.env["stock.move"].browse(move_to_link).account_move_id = account_move.id
        account_move._post()
        account_moves |= account_move
        return account_moves
