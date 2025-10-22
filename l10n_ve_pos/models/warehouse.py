# -*- coding: utf-8 -*-

from odoo import models, _


class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    def _get_picking_type_create_values(self, max_sequence):
        picking_type_create_values, max_sequence = super(
            Warehouse, self
        )._get_picking_type_create_values(max_sequence)

        if (
            self.env["ir.module.module"]
            .sudo()
            .search_count([("name", "=", "point_of_sale"), ("state", "=", "installed")])
        ):
            picking_type_create_values.update(
                {
                    "pos_type_id": {
                        "name": _("PoS Orders"),
                        "code": "outgoing",
                        "default_location_src_id": self.lot_stock_id.id,
                        "default_location_dest_id": self.env.ref(
                            "stock.stock_location_customers"
                        ).id,
                        "sequence": max_sequence + 1,
                        "sequence_code": "POS",
                        "company_id": self.company_id.id,
                    }
                }
            )
            max_sequence += 1

        return picking_type_create_values, max_sequence
