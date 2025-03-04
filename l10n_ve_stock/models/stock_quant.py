from odoo import _, api, fields, models
from odoo.tools.float_utils import float_compare, float_is_zero
import traceback

import logging

_logger = logging.getLogger(__name__)


class StockQuan(models.Model):
    _inherit = "stock.quant"

    product_alter_location_ids = fields.Many2many(
        "stock.quant", 
        compute="_compute_product_alter_location_ids"
    )
    is_physical_location = fields.Boolean(compute="_compute_is_physical_location", store=True)

    @api.depends("location_id", "product_id.physical_location_id")
    def _compute_is_physical_location(self):
        for record in self:
            record.is_physical_location = (
                record.location_id.id == record.product_id.physical_location_id.id
            )

    @api.depends("product_id")
    def _compute_product_alter_location_ids(self):
        self = self.sudo()
        for record in self:

            record.product_alter_location_ids = record.search(
                [
                    ("product_id", "=", record.product_id.id),
                    ("location_id.usage", "=", "internal"),
                    ("id", "!=", record.id),
                ]
            )

    @api.model
    def _update_reserved_quantity(
        self,
        product_id,
        location_id,
        quantity,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=False,
    ):
        if not self.env.company.use_physical_location or self._context.get(
            "skip_physical_location", False
        ):
            return super()._update_reserved_quantity(
                product_id, location_id, quantity, lot_id, package_id, owner_id, strict
            )

        self = self.sudo()
        rounding = product_id.uom_id.rounding

        quants = self._gather(
            product_id,
            location_id,
            lot_id=lot_id,
            package_id=package_id,
            owner_id=owner_id,
            strict=strict,
        )
        reserved_quants = []

        if float_compare(quantity, 0, precision_rounding=rounding) > 0:
            # if we want to reserve
            available_quantity = sum(
                quants.filtered(
                    lambda q: float_compare(q.quantity, 0, precision_rounding=rounding) > 0
                ).mapped("quantity")
            ) - sum(quants.mapped("reserved_quantity"))

            # >>> BINAURAL
            # if float_compare(quantity, available_quantity, precision_rounding=rounding) > 0:
            #     raise UserError(_('It is not possible to reserve more products of %s than you have in stock.', product_id.display_name))
            # <<< BINAURAL
        elif float_compare(quantity, 0, precision_rounding=rounding) < 0:
            # if we want to unreserve
            available_quantity = sum(quants.mapped("reserved_quantity"))

            # >>> BINAURAL
            # if float_compare(abs(quantity), available_quantity, precision_rounding=rounding) > 0:
            #     raise UserError(_('It is not possible to unreserve more products of %s than you have in stock.', product_id.display_name))
            # <<< BINAURAL
        else:
            return reserved_quants

        if (
            not product_id.physical_location_id
            or not product_id.physical_location_id in quants.location_id
        ):
            return super()._update_reserved_quantity(
                product_id,
                location_id,
                quantity,
                lot_id=lot_id,
                package_id=package_id,
                owner_id=owner_id,
                strict=strict,
            )

        # >>> BINAURAL
        quants = quants.filtered(
            lambda quant: quant.location_id.id == product_id.physical_location_id.id
        )
        # <<< BINAURAL

        for quant in quants:
            if float_compare(quantity, 0, precision_rounding=rounding) > 0:
                # >>> BINAURAL
                max_quantity_on_quant = quantity
                # <<< BINAURAL
                if float_compare(max_quantity_on_quant, 0, precision_rounding=rounding) <= 0:
                    continue
                max_quantity_on_quant = min(max_quantity_on_quant, quantity)
                quant.reserved_quantity += max_quantity_on_quant
                reserved_quants.append((quant, max_quantity_on_quant))
                quantity -= max_quantity_on_quant
                available_quantity -= max_quantity_on_quant
            else:
                max_quantity_on_quant = min(quant.reserved_quantity, abs(quantity))
                quant.reserved_quantity -= max_quantity_on_quant
                reserved_quants.append((quant, -max_quantity_on_quant))
                quantity += max_quantity_on_quant
                available_quantity += max_quantity_on_quant

            if float_is_zero(quantity, precision_rounding=rounding) or float_is_zero(
                available_quantity, precision_rounding=rounding
            ):
                break
        return reserved_quants
