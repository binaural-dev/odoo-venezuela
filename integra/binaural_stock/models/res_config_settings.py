from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    group_product_available_quantity_on_sale = fields.Boolean(
        related="company_id.group_sales_invoicing_series",
        readonly=False,
        implied_group="binaural_stock.group_product_available_quantity_on_sale",
    )
    use_main_warehouse = fields.Boolean(string="Usar almacén principal")
    main_warehouse_id = fields.Many2one("stock.warehouse", string="Almacén principal")

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        config_param = self.env["ir.config_parameter"].sudo()

        config_param.set_param("use_main_warehouse", self.use_main_warehouse)
        config_param.set_param("main_warehouse_id", self.main_warehouse_id.id)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        config_param = self.env["ir.config_parameter"].sudo()

        res["use_main_warehouse"] = config_param.get_param("use_main_warehouse")
        res["main_warehouse_id"] = int(config_param.get_param("main_warehouse_id"))

        return res
