from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError ,ValidationError
from datetime import date, timedelta
import traceback

import logging

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    is_sale_international = fields.Boolean(string="International sale",default=False)

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
                
    @api.constrains('is_sale_international')
    def _check_single_international_sale_journal(self):
        
        for record in self:
            if record.is_sale_international:
                domain = [
                    ('company_id','=',self.env.company.id),
                    ('is_sale_international', '=', True),
                    ('id', '!=', record.id),
                ]
                
                if self.search_count(domain) > 0:
                    raise ValidationError(
                        _("An International Sale Journal is already enabled. Only one is allowed.")
                    )