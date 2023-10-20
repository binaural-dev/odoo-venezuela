from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero
import logging

_logger = logging.getLogger(__name__)


class StockValuationAdjustmentLines(models.Model):
    _inherit = "stock.valuation.adjustment.lines"

    def default_is_stock_advance(self):
        return self.env.company.check_advance_stock or False

    additional_landed_cost = fields.Monetary("Additional Landed Cost Und")

    former_cost = fields.Monetary("Subtotal")

    foreign_currency_id = fields.Many2one(related="cost_id.foreign_currency_id", store=True)
    foreign_rate = fields.Float(related="cost_id.foreign_rate", store=True)
    foreign_inverse_rate = fields.Float(related="cost_id.foreign_inverse_rate", store=True)

    foreign_former_cost = fields.Monetary(
        "Foreign former cost",
        digits="Tasa",
        compute="_compute_foreign_former_cost",
        currency_field="foreign_currency_id",
        store=True,
    )

    foreign_final_cost = fields.Monetary(
        "Foreign Final Cost",
        digits="Tasa",
        compute="_compute_foreign_final_cost",
        currency_field="foreign_currency_id",
        store=True,
    )

    foreign_split_value = fields.Monetary(
        digits="Tasa", currency_field="foreign_currency_id", compute="_compute_foreign_split_value"
    )

    foreign_additional_landed_cost = fields.Monetary(
        "Foreign Additional landed cost",
        digits="Tasa",
        compute="_compute_foreign_additional_landed_cost",
        currency_field="foreign_currency_id",
        store=True,
    )

    foreign_last_cost = fields.Monetary(
        "Foreign Last Cost",
        digits="Tasa",
        currency_field="foreign_currency_id",
        compute="_compute_foreign_last_cost",
    )

    foreign_unit_cost = fields.Monetary(
        "Foreign Unit Cost",
        digits="Tasa",
        currency_field="foreign_currency_id",
        compute="_compute_foreign_unit_cost",
    )

    unit_cost = fields.Monetary("Unit cost", compute="_compute_unit_cost")
    total_amount_cost = fields.Monetary("Total amount cost")
    last_cost = fields.Monetary("Last cost", compute="_compute_last_cost", store=True)
    is_stock_advance = fields.Boolean(string="Is stock Advance", default=default_is_stock_advance)
    cost_percentage = fields.Float("Cost percentage %", default=0)
    price_unit = fields.Monetary("Cost Total With Tax", default=0)
    latest_standard_price = fields.Monetary(compute="_compute_latest_standard_price", store=True)
    update_latest_standard_price = fields.Boolean(
        related="product_id.product_tmpl_id.update_last_cost", readonly=False
    )

    split_value = fields.Monetary(compute="_compute_split_value", store=True)

    latest_standard_price_updated = fields.Monetary(
        compute="_compute_update_latest_standard_price", store=True
    )

    cost_cif = fields.Float("Cost CIF", compute="_compute_cost_cif")

    percentage_tariff_code = fields.Float("Percentage Tariff", compute="_compute_percentage_tariff")

    tariff_value = fields.Float("Tariff Value", default=0)

    @api.depends("former_cost", "additional_landed_cost")
    def _compute_final_cost(self):
        for line in self:
            if not line.cost_line_id.split_method == "by_percentage":
                line.final_cost = line.former_cost + line.additional_landed_cost
            line.final_cost = (line.additional_landed_cost * line.quantity) + line.former_cost

    @api.depends("former_cost", "quantity")
    def _compute_unit_cost(self):
        for line in self:
            line.unit_cost = line.former_cost / line.quantity


    @api.depends("product_id")
    def _compute_percentage_tariff(self):
        for line in self:
            line.percentage_tariff_code = line.product_id.percentage_tariff_code

    @api.depends("unit_cost", "cost_line_id", "additional_landed_cost")
    def _compute_cost_cif(self):
        for line in self:
            last_cost = 0
            original_value = line.unit_cost
            if line.cost_line_id.product_id:
                apply_cif_cost = self.env.company.service_products_ids
                for product in apply_cif_cost:
                    if line.cost_line_id.product_id == product:
                        additional_values = line.search(
                            [("product_id", "=", line.product_id.id), ("cost_id", "=", line.cost_id.id)]
                        )
                        for cost in additional_values:
                            original_value = cost.unit_cost
                        last_cost = sum(split.additional_landed_cost for split in additional_values)
                line.cost_cif = original_value + last_cost 
    

    # FOREIGN FIELDS

    @api.depends("unit_cost")
    def _compute_foreign_unit_cost(self):
        for line in self:
            line.foreign_unit_cost = line.unit_cost * line.foreign_inverse_rate

    @api.depends("foreign_inverse_rate")
    def _compute_foreign_former_cost(self):
        for line in self:
            line.foreign_former_cost = line.former_cost * line.foreign_inverse_rate

    @api.depends("final_cost", "foreign_inverse_rate")
    def _compute_foreign_final_cost(self):
        for line in self:
            line.foreign_final_cost = line.final_cost * line.foreign_inverse_rate

    @api.depends("split_value", "foreign_inverse_rate")
    def _compute_foreign_split_value(self):
        for line in self:
            line.foreign_split_value = line.split_value * line.foreign_inverse_rate

    @api.depends("additional_landed_cost", "foreign_inverse_rate")
    def _compute_foreign_additional_landed_cost(self):
        for line in self:
            line.foreign_additional_landed_cost = (
                line.additional_landed_cost * line.foreign_inverse_rate
            )

    @api.depends("last_cost", "foreign_inverse_rate")
    def _compute_foreign_last_cost(self):
        for line in self:
            line.foreign_last_cost = line.last_cost * line.foreign_inverse_rate

    @api.depends("final_cost", "additional_landed_cost")
    def _compute_split_value(self):
        for line in self:
            line.split_value = line.final_cost / line.quantity

    @api.depends("product_id", "split_value")
    def _compute_last_cost(self):
        for line in self:
            last_cost = 0
            original_value = 0
            if line.product_id:
                additional_values = line.search(
                    [("product_id", "=", line.product_id.id), ("cost_id", "=", line.cost_id.id)]
                )
                for cost in additional_values:
                    original_value = cost.unit_cost
                last_cost = sum(split.additional_landed_cost for split in additional_values)
                
            line.last_cost =  original_value + last_cost 

    @api.depends("product_id")
    def _compute_latest_standard_price(self):
        for line in self:
            latest_standard_price = line.product_id.latest_standard_price
            line.latest_standard_price = latest_standard_price

    @api.depends("update_latest_standard_price", "last_cost")
    def _compute_update_latest_standard_price(self):
        for line in self:
            line.latest_standard_price_updated = line.last_cost
