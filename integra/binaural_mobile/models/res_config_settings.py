from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    product_type_consu = fields.Boolean(
        string="Product search by type Consumable for sellers",
        related="company_id.product_type_consu",
        readonly=False,
    )
    product_type_service = fields.Boolean(
        string="Product search by type Service for sellers",
        related="company_id.product_type_service",
        readonly=False,
    )
    product_type_product = fields.Boolean(
        string="Product search by type Product for sellers",
        related="company_id.product_type_product",
        readonly=False,
    )

    retentions_draft_or_published = fields.Selection(
        string="Generate customer retentions in status",
        related="company_id.retentions_draft_or_published",
        readonly=False,
    )

    order_payment = fields.Selection(
        string="Sort invoices by", related="company_id.order_payment", readonly=False
    )

    shop_catalog_view_mode = fields.Selection(
        string="Shop catalog view mode",
        related="company_id.shop_catalog_view_mode",
        readonly=False,
    )

    process_payments_invoices = fields.Selection(
        related="company_id.process_payments_invoices",
        readonly=False,
    )

    payment_methods_in_app = fields.Many2many(
        related="company_id.payment_methods_in_app", readonly=False
    )

    dairy_fiscal = fields.Many2one(related="company_id.dairy_fiscal", readonly=False)

    dairy_no_fiscal = fields.Many2one(related="company_id.dairy_no_fiscal", readonly=False)

    app_sales_diaries = fields.Many2many(related="company_id.app_sales_diaries", readonly=False)

    group_stock_packaging = fields.Boolean(
        "Product Packagings",
        implied_group="product.group_stock_packaging",
        related="company_id.group_stock_packaging",
        readonly=False,
    )

    allow_installment_payments = fields.Boolean()
    
    mobile_show_tax_type = fields.Selection(
        related="company_id.mobile_show_tax_type", readonly=False
    )

    mobile_tax_include = fields.Boolean(
        related="company_id.mobile_tax_include", 
        string="Include taxes in prices",
        readonly=False
    )
