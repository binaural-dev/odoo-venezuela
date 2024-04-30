from odoo import api, fields, models, _


class StockPickingDistribution(models.Model):
    _name = "stock.picking.distribution"
    _description = "Picking Distribution"
    _check_company_auto = True

    name = fields.Char(default="/")
    state = fields.Selection(selection=[("draft", "Draft"), ("done", "Done")], default="draft")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company.id)
    expected_date = fields.Date()
    vehicle_id = fields.Many2one("fleet.vehicle")
    driver_id = fields.Many2one("res.partner")
    warehouse_id = fields.Many2one("stock.warehouse")
    stock_picking_type_id = fields.Many2one("stock.picking.type")
    picking_ids = fields.One2many("stock.picking", "distribution_id")
    picking_move_ids = fields.Many2many("stock.move", compute="_compute_picking_move_ids")
    picking_move_line_ids = fields.Many2many("stock.move.line", compute="_compute_picking_move_ids")
    amount_total = fields.Float(compute="_compute_total_informations")
    package_qty_total = fields.Integer(compute="_compute_total_informations")
    partner_count = fields.Integer(compute="_compute_total_informations")

    @api.depends("picking_ids")
    def _compute_total_informations(self):
        for record in self:
            record.amount_total = sum(record.picking_ids.mapped("amount_invoiced"))
            record.package_qty_total = sum(record.picking_ids.mapped("package_qty"))
            record.partner_count = len(record.picking_ids.partner_id)

    @api.depends("picking_ids")
    def _compute_picking_move_ids(self) -> None:
        for record in self:
            record.picking_move_line_ids = record.picking_ids.move_line_ids
            record.picking_move_ids = record.picking_ids.move_ids

    def action_draft(self) -> bool:
        data = {"state": "draft"}
        self.write(data)
        return True

    @api.onchange("vehicle_id")
    def _onchange_vehicle(self):
        self.driver_id = self.vehicle_id.driver_id

    def action_confirm(self) -> bool:
        data = {
            "state": "done",
            "name": self.env["ir.sequence"].next_by_code("stock.picking.distribution"),
        }
        if not self.expected_date:
            data["expected_date"] = fields.Date.today()
        self.write(data)
        return True
