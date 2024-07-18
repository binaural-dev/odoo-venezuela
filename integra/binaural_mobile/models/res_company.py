from odoo import api, fields, models
from odoo.addons.theme_prime.controllers.main import ThemePrimePWA


class ResCompany(models.Model):
    _inherit = "res.company"

    product_type_consu = fields.Boolean(string="Consumable")
    product_type_service = fields.Boolean(string="Service")
    product_type_product = fields.Boolean(string="Storable", default=True)
    mobile_show_tax_type = fields.Selection(
        selection=[
            ("include_tax", "Tax Included in the price"),
            ("exclude_tax", "tax excluded from the price"),
        ],
        default="include_tax",
    )
    mobile_tax_include = fields.Boolean(string="Include taxes in prices")
    retentions_draft_or_published = fields.Selection(
        [
            ("0", "Draft"),
            ("1", "Emit"),
        ],
        default="1",
    )
    order_payment = fields.Selection(
        [
            ("0", "from the oldest invoice to the newest"),
            ("1", "from the one with the most residual amount to the one with the least"),
        ],
        default="0",
    )

    shop_catalog_view_mode = fields.Selection(
        string="Shop catalog view mode",
        selection=[("list", "List"), ("grid", "Grid")],
        default="list",
    )

    process_payments_invoices = fields.Selection(
        [("0", "Payment Total"), ("1", "Payment Partial")], default="0"
    )
    payment_methods_in_app = fields.Many2many("account.journal")
    dairy_fiscal = fields.Many2one("account.journal")
    dairy_no_fiscal = fields.Many2one("account.journal")
    app_sales_diaries = fields.Many2many("account.journal", relation="app_sales_diaries_rel")
    group_stock_packaging = fields.Boolean("Product Packagings")

    allow_installment_payments = fields.Boolean(
        help="Check this if you want to allow payments by installments on the app.", default=False
    )
