from odoo import _, fields, models
from odoo.fields import Domain
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


class StockInventoryValuationWizard(models.TransientModel):
    """Inventory valuation report of the localization, at a date and for a location.

    Odoo 19 extended the core wizard "Inventory at Date" (``stock.quantity.history``), which Odoo 20
    removed: the stock report now takes the date in its search panel. This wizard keeps the fields
    and the download of Odoo 19, opens from the stock report and starts at the date chosen there.
    """

    _name = "stock.inventory.valuation.wizard"
    _description = "Inventory valuation report"

    inventory_datetime = fields.Datetime(
        "Inventory at Date",
        help="Choose a date to get the inventory at that date",
        default=lambda self: fields.Datetime.to_datetime(self.env.context.get("to_date")) or fields.Datetime.now(),
        required=True,
    )
    warehouse_search_id = fields.Many2one("stock.location")
    except_products_at_zero = fields.Boolean()

    def get_fields_products(self):
        return FIELDSPRODUCTS

    def open_at_date(self):
        """Open the stock report at the date and location of the wizard."""
        action = self.env["ir.actions.act_window"]._for_xml_id("stock.action_product_stock_view")
        context = dict(self.env.context, to_date=fields.Datetime.to_string(self.inventory_datetime))
        if self.warehouse_search_id:
            context["location"] = self.warehouse_search_id.id
        action["context"] = context
        return action

    def generate_report(self):
        company = self.env.company
        warehouse_search_id = self.warehouse_search_id
        inventory_datetime = self.inventory_datetime
        inventory_datetime_minus_one_day = inventory_datetime - timedelta(days=1)
        except_product = self.except_products_at_zero
        domain = [
            # ("qty_available", ">", 0),
            ("is_storable", "=", True),
        ]
        
        qty_companies = len(self.env["res.company"].sudo().search([]))
        if qty_companies > 1:
            domain = Domain.AND(
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
