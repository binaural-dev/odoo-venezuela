from odoo import models, api, fields, Command
import logging

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    def _create_account_move(self):
        """ Create account move for specific location or analytic.
            This function is a override of the original function to add the donation logic.
        """
        aml_vals_list = []
        move_to_link = set()
        company_partner = self.env.company.partner_id
        
        is_donation = any(move.scrap_id and move.scrap_id.is_donation for move in self)
        
        if not is_donation:
            return super()._create_account_move()

        for move in self:
            if move._should_create_account_move():
                aml_vals = move._get_account_move_line_vals()
                if is_donation:
                    for val in aml_vals:
                        val["partner_id"] = company_partner.id
                aml_vals_list += aml_vals
                move_to_link.add(move.id)
                
        if not aml_vals_list:
            return self.env['account.move']
            
            journal = self[0].product_id.categ_id.property_stock_journal
            if not journal:
                journal = self.env['account.journal'].search([('company_id', '=', self.company_id.id), ('type', '=', 'general')], limit=1)
            
            move_vals = {
                "journal_id": journal.id,
            "line_ids": [Command.create(aml_vals) for aml_vals in aml_vals_list],
            "date": self.env.context.get("force_period_date") or fields.Date.context_today(self),
        }
        
        if is_donation:
            move_vals.update({
                "is_donation": True,
                "partner_id": company_partner.id,
                "ref": "Donación por Desecho"
            })
            
        account_move = self.env["account.move"].sudo().create(move_vals)
        self.env["stock.move"].browse(move_to_link).account_move_id = account_move.id
        account_move._post()
        return account_move
