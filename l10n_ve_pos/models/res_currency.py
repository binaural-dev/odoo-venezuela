from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _load_pos_data_domain(self, data, config):
        domain = super()._load_pos_data_domain(data,config)
        company = self.env['res.company'].browse(int(config['company_id']))
        currency_ids = [company.currency_id.id, int(config['currency_id'])]
        if company.foreign_currency_id:
            currency_ids.append(company.foreign_currency_id.id)
        currency_ids = list(set(currency_ids))
        if len(currency_ids) > 1:
            return [('id', 'in', currency_ids)]
        return domain
    
