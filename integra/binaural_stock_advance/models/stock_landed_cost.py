from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero
from collections import defaultdict

import logging

_logger = logging.getLogger(__name__)


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    def default_alternate_currency(self):
        """
        This method is used to get the foreign currency of the company and set it as the default
        value of the foreign currency field.

        Returns
        -------
        type = int
            The id of the foreign currency of the company
        """
        return self.env.company.currency_foreign_id.id or False

    def default_is_stock_advance(self):
        return self.env.company.check_advance_stock or False

    is_stock_advance = fields.Boolean(string="Is stock Advance", default=default_is_stock_advance)

    foreign_currency_id = fields.Many2one(
        "res.currency",
        default=default_alternate_currency,
    )

    foreign_rate = fields.Float(
        compute="_compute_rate",
        digits="Tasa",
        default=0.0,
        store=True,
        readonly=False,
    )
    foreign_inverse_rate = fields.Float(
        help="Rate that will be used as factor to multiply of the foreign currency for this move.",
        compute="_compute_rate",
        digits=(16, 15),
        default=0.0,
        store=True,
        readonly=False,
    )

    foreign_valuation_adjustment_lines = fields.One2many(
        "stock.valuation.adjustment.lines",
        "cost_id",
        "Valuation Adjustments",
        states={"done": [("readonly", True)]},
    )

    picking_ids = fields.Many2many(
        "stock.picking",
        string="Transfers",
        copy=False,
        states={"done": [("readonly", True)]},
        domain=[("picking_type_code", "=", "incoming"),("purchase_id", "!=", False)],
    )

    @api.depends("date")
    def _compute_rate(self):
        """
        Compute the rate of the invoice using the compute_rate method of the res.currency.rate model.
        """
        Rate = self.env["res.currency.rate"]
        for cost in self:
            rate_values = Rate.compute_rate(
                cost.foreign_currency_id.id, cost.date or fields.Date.today()
            )
            cost.update(rate_values)

    @api.onchange("cost_lines")
    def _onchange_split_method(self):
        if "by_percentage" in [line.split_method for line in self.cost_lines]:
            for line in self.cost_lines:
                if line.split_method != "by_percentage":
                    line.split_method = "by_percentage"


    @api.onchange("foreign_rate")
    def _onchange_foreign_rate(self):
        """
        Onchange the foreign rate and compute the foreign inverse rate
        """
        Rate = self.env["res.currency.rate"]
        for cost in self:
            if not bool(cost.foreign_rate):
                return
            cost.foreign_inverse_rate = Rate.compute_inverse_rate(cost.foreign_rate)

    def _assign_picking_percentage(self):
        """
        This method search the picking lines to calculate the percentage to assign
        """
        amount = 0
        for purchase in self.picking_ids.mapped("purchase_id"):
            amount += purchase.amount_untaxed
        return amount

    def compute_landed_cost(self):
        """This method compute all prices based on split method.

        This method is override because a new split method was added and that have new logic.
        (By percentage)
        """
        self._assign_picking_percentage()
        # OVERRIDE
        AdjustementLines = self.env["stock.valuation.adjustment.lines"]
        AdjustementLines.search([("cost_id", "in", self.ids)]).unlink()

        towrite_dict = {}
        for cost in self.filtered(lambda cost: cost._get_targeted_move_ids()):
            rounding = cost.currency_id.rounding
            total_qty = 0.0
            total_cost = 0.0
            total_weight = 0.0
            total_volume = 0.0
            total_line = 0.0
            all_val_line_values = cost.get_valuation_lines()
            for val_line_values in all_val_line_values:
                for cost_line in cost.cost_lines:
                    val_line_values.update({"cost_id": cost.id, "cost_line_id": cost_line.id})
                    self.env["stock.valuation.adjustment.lines"].create(val_line_values)
                total_qty += val_line_values.get("quantity", 0.0)
                total_weight += val_line_values.get("weight", 0.0)
                total_volume += val_line_values.get("volume", 0.0)
                former_cost = val_line_values.get("former_cost", 0.0)
                # round this because former_cost on the valuation lines is also rounded
                total_cost += cost.currency_id.round(former_cost)
                total_line += 1

            for line in cost.cost_lines:
                value_split = 0.0
                for valuation in cost.valuation_adjustment_lines:
                    value = 0.0
                    if valuation.cost_line_id and valuation.cost_line_id.id == line.id:
                        if line.split_method == "by_quantity" and total_qty:
                            per_unit = line.price_unit / total_qty
                            value = valuation.quantity * per_unit
                        elif line.split_method == "by_weight" and total_weight:
                            per_unit = line.price_unit / total_weight
                            value = valuation.weight * per_unit
                        elif line.split_method == "by_volume" and total_volume:
                            per_unit = line.price_unit / total_volume
                            value = valuation.volume * per_unit
                        elif line.split_method == "equal":
                            value = line.price_unit / total_line
                        elif line.split_method == "by_current_cost_price" and total_cost:
                            per_unit = line.price_unit / total_cost
                            value = valuation.former_cost * per_unit
                        # OVERRIDE
                        elif line.split_method == "by_percentage":

                            if self.env.company.check_calculate_taking_order_quantities:
                                per_unit = valuation.former_cost / self._assign_picking_percentage()
                                valuation.cost_percentage = per_unit * 100
                                valuation.total_amount_cost = (
                                    (valuation.cost_percentage) / 100
                                ) * line.price_unit

                                value_percentage = (
                                    line.price_unit * ((valuation.cost_percentage) / 100)
                                ) / valuation.quantity

                                value = value_percentage
                            if self.env.company.check_calculate_based_total_purchase_amount:
                                per_unit = line.price_unit  / self._assign_picking_percentage()
                                
                                valuation.cost_percentage = per_unit * 100
                                value_percentage = (
                                    valuation.former_cost * ((valuation.cost_percentage) / 100)
                                ) / valuation.quantity

                                valuation.cost_ddp = (
                                    valuation.former_cost * ((valuation.cost_percentage) / 100)
                                )


                                value = value_percentage                          

                        else:
                            value = line.price_unit / total_line

                        if rounding:
                            value = tools.float_round(
                                value, precision_rounding=rounding, rounding_method="UP"
                            )
                            fnc = min if line.price_unit > 0 else max
                            value = fnc(value, line.price_unit - value_split)
                            value_split += value

                        if valuation.id not in towrite_dict:
                            towrite_dict[valuation.id] = value

                        else:
                            towrite_dict[valuation.id] += value

        for (
            key,
            value,
        ) in towrite_dict.items():
            AdjustementLines.browse(key).write(
                {
                    "additional_landed_cost": value,
                }
            )
        return True

    def _get_lines_with_updatable_latest_standard_price(self):
        return self.mapped("valuation_adjustment_lines").filtered(
            lambda line: line.update_latest_standard_price
        )

    def button_validate(self):
        is_percentage = "by_percentage" in [line.split_method for line in self.cost_lines]
        all_percentage = all(line.split_method == "by_percentage" for line in self.cost_lines)

        if not is_percentage:
            res = super().button_validate()
        elif is_percentage and not self.company_id.use_same_account_stock_valuation_to_category:
            res = super().button_validate()
        elif (
            self.company_id.use_same_account_stock_valuation_to_category
            and all_percentage
        ):
            res = self._button_validate_move_cost()
        else:
            res = super().button_validate()

        for line in self._get_lines_with_updatable_latest_standard_price():
            product = line.product_id
            latest_standard_price = line.latest_standard_price
            latest_standard_price_updated = line.latest_standard_price_updated

            product.last_latest_standard_price = latest_standard_price
            product.latest_standard_price = latest_standard_price_updated

            variants_are_active = product.get_variants_are_active()
            if not variants_are_active:
                product.product_tmpl_id.last_latest_standard_price = latest_standard_price
                product.product_tmpl_id.latest_standard_price = latest_standard_price_updated
        return res

    def action_stock_valuation_landed(self):
        view = self.env.ref(
            "binaural_stock_advance.stock_valuation_adjustment_lines_tree_binaural_stock_advance"
        )
        valuation_landed_ids = self.env["stock.valuation.adjustment.lines"].search(
            [("cost_id", "=", self.id)]
        )

        return {
            "name": _("Cost"),
            "type": "ir.actions.act_window",
            "view_mode": "tree",
            "res_model": "stock.valuation.adjustment.lines",
            "views": [(view.id, "tree")],
            "view_id": view.id,
            "target": "new",
            "domain": [("id", "in", valuation_landed_ids.ids)],
            "context": {"default_cost_id": self.id, "group_by": "cost_line_id"},
        }

    @api.model_create_multi
    def create(self, vals_list):
        """
        Ensure that the foreign_rate and foreign_inverse_rate are computed and computes the foreign
        debit and foreign credit of the line_ids fields (journal entries) when the move is created.
        """
        moves = super().create(vals_list)
        moves._compute_rate()
        return moves

    def _check_sum(self):
        """Check if each cost line its valuation lines sum to the correct amount
        and if the overall total amount is correct also


        When split method is by percentage, return True
        """
        prec_digits = self.env.company.currency_id.decimal_places
        for landed_cost in self:
            for cost_line in landed_cost.cost_lines:
                # OVERRIDE
                if not cost_line.split_method == "by_percentage":
                    total_amount = sum(
                        landed_cost.valuation_adjustment_lines.mapped("additional_landed_cost")
                    )
                    if not tools.float_is_zero(
                        total_amount - landed_cost.amount_total, precision_digits=prec_digits
                    ):
                        return False

                    val_to_cost_lines = defaultdict(lambda: 0.0)
                    for val_line in landed_cost.valuation_adjustment_lines:
                        val_to_cost_lines[val_line.cost_line_id] += val_line.additional_landed_cost
                    if any(
                        not tools.float_is_zero(
                            cost_line.price_unit - val_amount, precision_digits=prec_digits
                        )
                        for cost_line, val_amount in val_to_cost_lines.items()
                    ):
                        return False
        return True

    def _button_validate_move_cost(self):
        self._check_can_validate()
        cost_without_adjusment_lines = self.filtered(lambda c: not c.valuation_adjustment_lines)
        if cost_without_adjusment_lines:
            cost_without_adjusment_lines.compute_landed_cost()
        if not self._check_sum():
            raise UserError(
                _(
                    "Cost and adjustments lines do not match. You should maybe recompute the landed costs."
                )
            )

        for cost in self:
            cost = cost.with_company(cost.company_id)
            move = self.env["account.move"]
            move_vals = {
                "journal_id": cost.account_journal_id.id,
                "date": cost.date,
                "ref": cost.name,
                "line_ids": [],
                "move_type": "entry",
            }
            valuation_layer_ids = []
            cost_to_add_byproduct = defaultdict(lambda: 0.0)
            for line in cost.valuation_adjustment_lines.filtered(lambda line: line.move_id):
                remaining_qty = sum(line.move_id.stock_valuation_layer_ids.mapped("remaining_qty"))
                linked_layer = line.move_id.stock_valuation_layer_ids[:1]

                # Prorate the value at what's still in stock
                cost_to_add = (
                    remaining_qty / line.move_id.product_qty
                ) * line.additional_landed_cost
                if not cost.company_id.currency_id.is_zero(cost_to_add):
                    valuation_layer = self.env["stock.valuation.layer"].create(
                        {
                            "value": cost_to_add,
                            "unit_cost": 0,
                            "quantity": 0,
                            "remaining_qty": 0,
                            "stock_valuation_layer_id": linked_layer.id,
                            "description": cost.name,
                            "stock_move_id": line.move_id.id,
                            "product_id": line.move_id.product_id.id,
                            "stock_landed_cost_id": cost.id,
                            "company_id": cost.company_id.id,
                        }
                    )
                    linked_layer.remaining_value += cost_to_add
                    valuation_layer_ids.append(valuation_layer.id)
                # Update the AVCO
                product = line.move_id.product_id
                if product.cost_method == "average":
                    cost_to_add_byproduct[product] += cost_to_add
                # Products with manual inventory valuation are ignored because they do not need to create journal entries.
                if product.valuation != "real_time":
                    continue
                # `remaining_qty` is negative if the move is out and delivered proudcts that were not
                # in stock.
                qty_out = 0
                if line.move_id._is_in():
                    qty_out = line.move_id.product_qty - remaining_qty
                elif line.move_id._is_out():
                    qty_out = line.move_id.product_qty
                move_vals["line_ids"] += line._create_accounting_entries(move, qty_out)

            # batch standard price computation avoid recompute quantity_svl at each iteration
            products = (
                self.env["product.product"]
                .browse(p.id for p in cost_to_add_byproduct.keys())
                .with_company(cost.company_id)
            )
            for product in products:  # iterate on recordset to prefetch efficiently quantity_svl
                if not float_is_zero(
                    product.quantity_svl, precision_rounding=product.uom_id.rounding
                ):
                    product.sudo().with_context(disable_auto_svl=True).standard_price += (
                        cost_to_add_byproduct[product] / product.quantity_svl
                    )

            # >>> Binaural
            category_account_id = products.categ_id.property_stock_valuation_account_id
            new_lines = []
            new_lines.append(
                [
                    0,
                    0,
                    {
                        "name": f"{self.name}",
                        "account_id": category_account_id.id,
                        "debit": self.amount_total,
                    },
                ]
            )

            for line in self.cost_lines:
                new_lines.append(
                    [
                        0,
                        0,
                        {
                            "name": f"{line.name} - {self.name}",
                            "account_id": line.account_id.id,
                            "credit": line.price_unit,
                        },
                    ]
                )

            move_vals["line_ids"] = new_lines
            # <<< Binaural
            move_vals["stock_valuation_layer_ids"] = [(6, None, valuation_layer_ids)]
            # We will only create the accounting entry when there are defined lines (the lines will be those linked to products of real_time valuation category).
            cost_vals = {"state": "done"}
            if move_vals.get("line_ids"):
                move = move.create(move_vals)
                cost_vals.update({"account_move_id": move.id})
            cost.write(cost_vals)
            if cost.account_move_id:
                move._post()
            cost.reconcile_landed_cost()
        return True
