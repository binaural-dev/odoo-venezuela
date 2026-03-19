from odoo import api,fields,models,_

import logging

_logger = logging.getLogger(__name__)

class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    is_donation = fields.Boolean(string='Is Donation', default=False)

    scrap_location_domain = fields.Char(
        string="Picking Type Domain",
        compute="_compute_scrap_location_domain",
    )
    scrap_location_id = fields.Many2one(
        "stock.location",
        domain=[],
    )
    
    @api.depends("is_donation")
    def _compute_scrap_location_domain(self):
        native_domain = "[('usage', '=', 'internal')]"
        for picking in self:
            if picking.is_donation:
                picking.scrap_location_domain = "[('is_donation_warehouse', '=', True)]"
            else:
                picking.scrap_location_domain = native_domain

    def do_scrap(self):
        self._check_company()
        for scrap in self:
            if scrap.is_donation:
                scrap.name = self.env['ir.sequence'].next_by_code('stock.donation') or _('New')
                move = self.env['stock.move'].create(scrap._prepare_move_values())
                move.with_context(is_scrap=True)._action_done()
                scrap.write({'state': 'done'})
                scrap.date_done = fields.Datetime.now()
                if scrap.should_replenish:
                    scrap.do_replenish()
                return True
            else:
                return super().do_scrap()
        
        