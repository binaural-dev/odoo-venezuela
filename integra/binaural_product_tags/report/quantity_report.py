import logging
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class QuantityReport(models.Model):
    _name = "report.binaural_product_tags.stock_picking_package_quantity"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["stock.picking"].browse(data["picking_id"])
        picking_data = self.get_picking_data(docs)

        return {
            "doc_ids": docids,
            "doc_model": "stock.picking",
            "docs": docs,
            "data": data,
            "stock_picking_data": picking_data,
        }

    def get_picking_data(self, picking):
        partner_address = self._parse_partner_address(picking.partner_id)
        return {
            "partner_name": picking.partner_id.name,
            "partner_shipping": partner_address,
            "shipping_city": picking.partner_id.city_id.name,
            "scheduled_date": picking.scheduled_date,
            "origin": picking.origin,
            "package_qty": picking.package_qty,
        }

    @api.model
    def _parse_partner_address(self, partner):
        street = partner.street or ""
        street2 = partner.street2 or ""
        city = partner.city_id.name or ""
        state = partner.state_id.name or ""

        return f"{street} - {street2} - {city} - {state}."
