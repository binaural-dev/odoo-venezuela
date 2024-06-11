from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    check_advance_stock = fields.Boolean(related="company_id.check_advance_stock", readonly=False)
    use_fee_percentage = fields.Boolean(related="company_id.use_fee_percentage", readonly=False)
    apply_fob = fields.Boolean(related="company_id.apply_fob", readonly=False)
    apply_cif = fields.Boolean(related="company_id.apply_cif", readonly=False)
    service_products_ids = fields.Many2many(
        related="company_id.service_products_ids", readonly=False
    )
    check_calculate_taking_order_quantities = fields.Boolean(
        related="company_id.check_calculate_taking_order_quantities",
        string="Calculate taking into account the order quantities",
        readonly=False
    )
    check_calculate_based_total_purchase_amount = fields.Boolean(
        related="company_id.check_calculate_based_total_purchase_amount",
        string="Calculate based on the total purchase amount",
        readonly=False
    )
    
    use_same_account_stock_valuation_to_category = fields.Boolean(
        related="company_id.use_same_account_stock_valuation_to_category", readonly=False
    )

    category_cost_account_id = fields.Many2one(
        related="company_id.category_cost_account_id", readonly=False
    )

    @api.onchange("use_same_account_stock_valuation_to_category")
    def _onchange_use_same_account_stock_valuation_to_category(self):
        if not self.use_same_account_stock_valuation_to_category:
            self.category_cost_account_id = False
