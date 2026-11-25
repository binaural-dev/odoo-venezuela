from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResCurrency(models.Model):
    _inherit = 'res.currency'

    @api.model
    def _load_pos_data_domain(self, data, config):
        """Odoo 19 loader contract: restrict the currencies to the active
        company currency, the PoS config currency, the company foreign
        currency and the tender currencies of its payment methods
        (``pos.payment.method.tender_currency_id``). Avoids loading extra
        currencies present in pricelists.
        """
        domain = super()._load_pos_data_domain(data, config)
        company = self.env['res.company'].browse(int(config['company_id']))
        currency_ids = [company.currency_id.id, int(config['currency_id'])]
        if company.foreign_currency_id:
            currency_ids.append(company.foreign_currency_id.id)
        currency_ids += config.payment_method_ids.tender_currency_id.ids
        currency_ids = list(set(currency_ids))
        if len(currency_ids) > 1:
            return [('id', 'in', currency_ids)]
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
    def _apply_pos_session_rates(self, read_records, records, config):
        """``rate`` (e ``inverse_rate``) del día de la sesión de la caja, no el
        del momento de la carga: el core pasa la lista de precios en divisa a la
        moneda de la caja con este ``rate``, y debe ser la misma tasa que cobra
        la caja (``pos.config.foreign_rate``), también después de medianoche.
        La usan la carga del PdV y la del kiosko (``l10n_ve_pos_self_order``)."""
        session = config.current_session_id
        if not session or not read_records:
            return read_records
        rates = session._get_pos_currency_rates(records)
        for entry in read_records:
            rate = rates.get(entry.get("id"))
            if rate:
                entry["rate"] = rate
                if "inverse_rate" in entry:
                    entry["inverse_rate"] = 1.0 / rate
        return read_records

    @api.model
    def _load_pos_data_read(self, records, config):
        """Odoo 19 loader contract: reorder the resulting currencies so the
        company currency comes first and the foreign currency comes second.
        """
        res = super()._load_pos_data_read(records, config) or []
        self._apply_pos_session_rates(res, records, config)
        company_currency_id = config.company_id.currency_id.id
        if res and res[0].get('id') != company_currency_id:
            company_entry = next(
                (entry for entry in res if entry.get('id') == company_currency_id),
                None,
            )
            if company_entry is not None:
                res = [company_entry] + [e for e in res if e is not company_entry]
        return res
