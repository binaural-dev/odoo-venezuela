from odoo import api, fields, models


class OperationSupervisor(models.TransientModel):
    _name = "stock.operation.supervisor"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company.id)

    def default_stock_picking_type_ids(self):
        type_ids = self.env["stock.picking.type"]
        stock_picking_type_ids = type_ids.search([])
        filter_delivery = []
        for warehouse in self.env["stock.warehouse"].search([]):
            if warehouse.delivery_steps == "ship_only":
                filter_delivery = ["out"]
            if warehouse.delivery_steps == "pick_ship":
                filter_delivery = ["pick", "out"]
            if warehouse.delivery_steps == "pick_pack_ship":
                filter_delivery = ["pick", "pack", "out"]

            for stock_picking_type_id in stock_picking_type_ids:
                if stock_picking_type_id._get_type_steps() in filter_delivery:
                    type_ids += stock_picking_type_id
        return type_ids.ids

    stock_picking_type_ids = fields.Many2many(
        "stock.picking.type",
        default=default_stock_picking_type_ids,
    )

    def action_confirm(self):
        """
        Use to save data
        """
        pass
