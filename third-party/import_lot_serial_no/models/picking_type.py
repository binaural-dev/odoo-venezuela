# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from ast import literal_eval


class PickingTypeInherit(models.Model):
    _inherit = "stock.picking.type"

    def _get_action(self, action_xmlid):
        action = self.env.ref(action_xmlid).read()[0]
        if self:
            action['display_name'] = self.display_name
        context = {
            'search_default_picking_type_id': [self.id],
            'default_picking_type_id': self.id,
            'default_company_id': self.company_id.id,
        }
        action_context = literal_eval(action['context'])
        context = {**action_context, **context}
        action['context'] = context
        return action
