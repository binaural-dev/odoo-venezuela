from odoo import fields, models

import logging
import json
_logger = logging.getLogger(__name__)


class IrActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    def read(self, fields=None, load='_classic_read'):
        values = super().read(fields=fields, load=load)
        for result in values:
            if result.get('id') == self.env.ref("account.action_move_out_refund_type").id:
                if not self.env.user.has_group("l10n_ve_invoice.create_out_refund"):
                    context = "{'default_move_type': 'out_refund', 'default_filter_partner': 'customer', 'create': 0}"
                    result["context"] = context
                    continue
                context = "{'default_move_type': 'out_refund', 'default_filter_partner': 'customer', 'create': 1}"
                result["context"] = context
        return values

