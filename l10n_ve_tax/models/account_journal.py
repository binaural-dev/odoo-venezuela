from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError ,ValidationError
from datetime import date, timedelta
import traceback

import logging

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_purchase_international = fields.Boolean(string="International purchase",default=False)

    @api.constrains('is_purchase_international')
    def _check_single_international_purchase_journal(self):
        
        for record in self:
            if record.is_purchase_international:
                domain = [
                    ('is_purchase_international', '=', True),
                    ('id', '!=', record.id),
                ]
                
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _("An International Purchase Journal is already enabled. Only one is allowed.")
                    )