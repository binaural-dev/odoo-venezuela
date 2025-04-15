from odoo import _, fields, models
from odoo.osv import expression
from odoo.tools.misc import format_datetime
import operator as py_operator

from odoo.tools.float_utils import float_round

import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

FIELDSPRODUCTS=[
    "id",
    "name",
    "qty_available",
    "free_qty",
    "virtual_available",
    "default_code",
    "standard_price",
]


class StockQuantityHistoryInh(models.TransientModel):
    _inherit = "stock.quantity.history"

    warehouse_search_id = fields.Many2one("stock.location")

    except_products_at_zero = fields.Boolean()

    def get_fields_products(self):
        return FIELDSPRODUCTS
    
    def open_at_date(self):

        res = super(StockQuantityHistoryInh, self.with_context(location=self.warehouse_search_id)).open_at_date()
        return res

    def open_at_date_test(self):
        self._compute_quantities_dict()

    def generate_report(self):
        company = self.env.company
        warehouse_search_id = self.warehouse_search_id
        inventory_datetime = self.inventory_datetime
        inventory_datetime_minus_one_day = inventory_datetime - timedelta(days=1)
        except_product = self.except_products_at_zero
        domain = [
            # ("qty_available", ">", 0),
            ("type", "=", "product"),
        ]
        
        qty_companies = len(self.env["res.company"].sudo().search([]))
        if qty_companies > 1:
            domain = expression.AND(
                [domain, [("company_id", "in", (company.id, False))]]
            )
        product_ids = self.env["product.product"].search(domain)
        product_ids_a = product_ids.with_context(location=warehouse_search_id.id)._compute_quantities_dict_for_report(
            lot_id=False, owner_id=False, package_id=False,  to_date=inventory_datetime
        )
        
        module_last_cost = self.env["ir.module.module"].search([('name', "ilike", "binaural_last_cost")])
        last_cost_installed = True if module_last_cost.state == "installed" else False
        if last_cost_installed:
            FIELDSPRODUCTS.append("latest_standard_price")
            FIELDSPRODUCTS.append("value_total_last_cost")
        product_ids = product_ids.with_context(location=warehouse_search_id.id).read(fields=FIELDSPRODUCTS)
        products_filter = []
        for prod in product_ids:
            prod["qty_available"] = product_ids_a[prod["id"]]["qty_available"]
            prod["virtual_available"] = product_ids_a[prod["id"]]["virtual_available"]
            if except_product:
                if prod["qty_available"] > 0:
                    products_filter.append(prod)
        data = {
            "warehouse_id": warehouse_search_id.display_name if warehouse_search_id else False,
            "company_id": company,
            "to_date": inventory_datetime.date(),
            "today": fields.Date.context_today(self),
            "product_ids": product_ids if not except_product else products_filter,
            "last_cost": last_cost_installed,
        }

        return self.env.ref("l10n_ve_stock.inventory_valuation_report").report_action(
            [], data=data
        )
