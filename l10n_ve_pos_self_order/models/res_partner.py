from odoo import api, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _load_pos_self_data_read(self, records, config):
        """El core del Kiosko lee solo ``id``/``name``/``write_date``/
        ``property_product_pricelist`` del partner. Añadimos ``vat`` y
        ``prefix_vat`` (la cédula/RIF con que el cliente se identifica al
        iniciar el Kiosko) para que las integraciones de pago que la necesitan
        —hoy Megasoft (``binaural_megasoft_self_order``)— puedan leerla del
        partner de la orden sin volver a pedirla.

        Se inyecta sobre lo que devolvió el core (mismo patrón que
        ``l10n_ve_pos``'s ``pos.order._load_pos_data_read``); no se toca el
        contrato de campos del core.
        """
        read_records = super()._load_pos_self_data_read(records, config)
        if not read_records:
            return read_records
        records_by_id = {r.id: r for r in records}
        for record in read_records:
            source = records_by_id.get(record["id"])
            if source is None:
                continue
            record["vat"] = source.vat
            record["prefix_vat"] = source.prefix_vat
        return read_records
