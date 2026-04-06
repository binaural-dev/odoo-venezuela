from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _load_pos_data_domain(self, data, config):
        """
        Extend the domain for the search_read of res.currency
        This method ensures that additional fields required for the Venezuelan localization,
        such as foreign currency, are included in the data sent to the POS frontend.
        """
        domain = super()._load_pos_data_domain(data,config)
        company = self.env['res.company'].browse(int(config['company_id']))
        currency_ids = [company.currency_id.id, int(config['currency_id'])]
        if company.foreign_currency_id:
            currency_ids.append(company.foreign_currency_id.id)
        currency_ids = list(set(currency_ids))
        if len(currency_ids) > 1:
            return [('id', 'in', currency_ids)]
        return domain
    
