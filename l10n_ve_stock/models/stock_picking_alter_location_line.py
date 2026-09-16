from odoo import _, api, fields, models


class StockPickingAlterLocationLine(models.Model):
    _name = "stock.picking.alter.location.line"
    _description = "Alternate Location Line"

    name = fields.Char(related="location_id.display_name")
    location_id = fields.Many2one("stock.location", string="Product Location")
    stock_alter_location_id = fields.Many2one("stock.picking.alter.location")
    available_qty = fields.Float("Available Quantities")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="stock_alter_location_id.company_id",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.stock_alter_location_id.message_post(
                body=_("New location '%(name)s' added with quantity: %(qty)s",
                        name=rec.name, qty=rec.available_qty)
            )
        return records

    def write(self, vals):
        old_values = {line.id: (line.available_qty, line.name) for line in self}
        res = super().write(vals)
        if "available_qty" in vals:
            post_qty = vals.get("available_qty")
            for line in self:
                pre_qty, pre_name = old_values.get(line.id, (0.0, line.name))
                line.stock_alter_location_id.message_post(
                    body=_("Quantity updated"),
                    tracking_value_ids=[
                        (
                            0,
                            0,
                            {
                                "field_info": {
                                    "desc": _("Quantity in %s", pre_name),
                                    "name": "available_qty",
                                    "type": "float",
                                },
                                "old_value_float": pre_qty,
                                "new_value_float": post_qty,
                            },
                        )
                    ],
                )
        return res