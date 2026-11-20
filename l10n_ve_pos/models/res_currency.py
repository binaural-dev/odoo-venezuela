from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _load_pos_data_domain(self, data):
        """Odoo 20 loader contract: restrict the currencies to the active
        company currency, the PoS config currency, the company foreign
        currency and the ones the payment methods of the PoS declare. Avoids
        loading extra currencies present in pricelists.
        """
        domain = super()._load_pos_data_domain(data)
        config = data['pos.config']
        company = config.company_id
        currencies = (
            company.currency_id
            | config.currency_id
            | company.foreign_currency_id
            | config.payment_method_ids.currency_ids
        )
        if len(currencies) > 1:
            return [('id', 'in', currencies.ids)]
        return domain

    @api.model
    def _load_pos_data_fields(self, config):
        """Odoo 19 loader contract: extend the read with ``inverse_rate``
        so the Venezuelan PoS UI can convert local ↔ foreign amounts.
        """
        res = super()._load_pos_data_fields(config)
        if 'inverse_rate' not in res:
            res.append('inverse_rate')
        return res

    @api.model
    def _load_pos_data_read(self, records, config):
        """Odoo 19 loader contract: reorder the resulting currencies so the
        company currency comes first and the foreign currency comes second.
        """
        res = super()._load_pos_data_read(records, config) or []
        company_currency_id = config.company_id.currency_id.id
        if res and res[0].get('id') != company_currency_id:
            company_entry = next(
                (entry for entry in res if entry.get('id') == company_currency_id),
                None,
            )
            if company_entry is not None:
                res = [company_entry] + [e for e in res if e is not company_entry]
        return res
