from collections import defaultdict

from odoo import _, api, models, fields
from odoo.exceptions import ValidationError, UserError
from odoo.tools.float_utils import float_round
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def button_dummy(self):
        # TDE FIXME: this button is very interesting
        # Variante del maldito Raiver e.e
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group(
            "l10n_ve_stock.group_block_type_inventory_transfers_expeditions"
        ):
            raise UserError(_("You can't create products"))
        return super().create(vals_list)

    @api.constrains("barcode")
    def _check_barcode_uniqueness(self):
        """
        This function was overwritten to add the multicompany filter

        --- Original --
        With GS1 nomenclature, products and packagings use the same pattern. Therefore, we need
        to ensure the uniqueness between products' barcodes and packagings' ones"""
        all_barcode = [b for b in self.mapped("barcode") if b]
        domain = [("barcode", "in", all_barcode), ("company_id", "=", self.company_id.id)]
        matched_products = self.sudo().search(domain, order="id")

        if len(matched_products) > len(all_barcode):
            products_by_barcode = defaultdict(list)
            for product in matched_products:
                products_by_barcode[product.barcode].append(product)

            duplicates_as_str = "\n".join(
                _(
                    '- Barcode "%s" already assigned to product(s): %s',
                    barcode,
                    ", ".join(p.display_name for p in products),
                )
                for barcode, products in products_by_barcode.items()
                if len(products) > 1
            )
            raise ValidationError(_("Barcode(s) already assigned:\n\n%s", duplicates_as_str))

        if self.env["product.packaging"].search(domain, order="id", limit=1):
            raise ValidationError(_("A packaging already uses the barcode"))

    def _compute_quantities_dict(
        self, lot_id, owner_id, package_id, from_date=False, to_date=False, location=False
    ):
        if not location:
            return super(ProductProduct, self)._compute_quantities_dict(
                lot_id, owner_id, package_id, from_date, to_date
            )
        domain_quant_loc, domain_move_in_loc, domain_move_out_loc = self._get_domain_locations()
        domain_quant = [("product_id", "in", self.ids)] + domain_quant_loc
        dates_in_the_past = False
        # only to_date as to_date will correspond to qty_available
        to_date = fields.Datetime.to_datetime(to_date)
        if to_date and to_date < fields.Datetime.now():
            dates_in_the_past = True

        domain_move_in = [("product_id", "in", self.ids)] + domain_move_in_loc
        domain_move_out = [("product_id", "in", self.ids)] + domain_move_out_loc
        if lot_id is not None:
            domain_quant += [("lot_id", "=", lot_id)]
        if owner_id is not None:
            domain_quant += [("owner_id", "=", owner_id)]
            domain_move_in += [("restrict_partner_id", "=", owner_id)]
            domain_move_out += [("restrict_partner_id", "=", owner_id)]
        if package_id is not None:
            domain_quant += [("package_id", "=", package_id)]
        if dates_in_the_past:
            domain_move_in_done = list(domain_move_in)
            domain_move_out_done = list(domain_move_out)
        if from_date:
            date_date_expected_domain_from = [("date", ">=", from_date)]
            domain_move_in += date_date_expected_domain_from
            domain_move_out += date_date_expected_domain_from
        if to_date:
            date_date_expected_domain_to = [("date", "<=", to_date)]
            domain_move_in += date_date_expected_domain_to
            domain_move_out += date_date_expected_domain_to

        if location:
            domain_quant = expression.AND([domain_quant, [("location_id", "=", location.id)]])

        Move = self.env["stock.move"].with_context(active_test=False)
        Quant = self.env["stock.quant"].with_context(active_test=False)
        domain_move_in_todo = [
            ("state", "in", ("waiting", "confirmed", "assigned", "partially_available"))
        ] + domain_move_in
        domain_move_out_todo = [
            ("state", "in", ("waiting", "confirmed", "assigned", "partially_available"))
        ] + domain_move_out
        moves_in_res = dict(
            (item["product_id"][0], item["product_qty"])
            for item in Move._read_group(
                domain_move_in_todo, ["product_id", "product_qty"], ["product_id"], orderby="id"
            )
        )
        moves_out_res = dict(
            (item["product_id"][0], item["product_qty"])
            for item in Move._read_group(
                domain_move_out_todo, ["product_id", "product_qty"], ["product_id"], orderby="id"
            )
        )
        quants_res = dict(
            (item["product_id"][0], (item["quantity"], item["reserved_quantity"]))
            for item in Quant._read_group(
                domain_quant,
                ["product_id", "quantity", "reserved_quantity"],
                ["product_id"],
                orderby="id",
            )
        )
        if dates_in_the_past:
            # Calculate the moves that were done before now to calculate back in time (as most questions will be recent ones)
            if location:
                copy_domain_move_in_done = domain_move_in_done
                copy_domain_move_out_done = domain_move_out_done
                domain_move_in_done = expression.AND(
                    [copy_domain_move_in_done, [("location_dest_id", "=", location.id)]]
                )
                domain_move_in_done = expression.OR(
                    [copy_domain_move_in_done, [("location_id", "=", location.id)]]
                )
                domain_move_out_done = expression.AND(
                    [copy_domain_move_out_done, [("location_dest_id", "=", location.id)]]
                )
                domain_move_out_done = expression.OR(
                    [copy_domain_move_out_done, [("location_id", "=", location.id)]]
                )
            domain_move_in_done = [
                ("state", "=", "done"),
                ("date", ">", to_date),
            ] + domain_move_in_done
            domain_move_out_done = [
                ("state", "=", "done"),
                ("date", ">", to_date),
            ] + domain_move_out_done
            moves_in_res_past = dict(
                (item["product_id"][0], item["product_qty"])
                for item in Move._read_group(
                    domain_move_in_done, ["product_id", "product_qty"], ["product_id"], orderby="id"
                )
            )
            moves_out_res_past = dict(
                (item["product_id"][0], item["product_qty"])
                for item in Move._read_group(
                    domain_move_out_done,
                    ["product_id", "product_qty"],
                    ["product_id"],
                    orderby="id",
                )
            )

        res = dict()
        for product in self.with_context(prefetch_fields=False):
            origin_product_id = product._origin.id
            product_id = product.id
            if not origin_product_id:
                res[product_id] = dict.fromkeys(
                    [
                        "qty_available",
                        "free_qty",
                        "incoming_qty",
                        "outgoing_qty",
                        "virtual_available",
                    ],
                    0.0,
                )
                continue
            rounding = product.uom_id.rounding
            res[product_id] = {}
            if dates_in_the_past:
                qty_available = (
                    quants_res.get(origin_product_id, [0.0])[0]
                    - moves_in_res_past.get(origin_product_id, 0.0)
                    + moves_out_res_past.get(origin_product_id, 0.0)
                )
            else:
                qty_available = quants_res.get(origin_product_id, [0.0])[0]
            reserved_quantity = quants_res.get(origin_product_id, [False, 0.0])[1]
            res[product_id]["qty_available"] = float_round(
                qty_available, precision_rounding=rounding
            )
            res[product_id]["free_qty"] = float_round(
                qty_available - reserved_quantity, precision_rounding=rounding
            )
            res[product_id]["incoming_qty"] = float_round(
                moves_in_res.get(origin_product_id, 0.0), precision_rounding=rounding
            )
            res[product_id]["outgoing_qty"] = float_round(
                moves_out_res.get(origin_product_id, 0.0), precision_rounding=rounding
            )
            res[product_id]["virtual_available"] = float_round(
                qty_available + res[product_id]["incoming_qty"] - res[product_id]["outgoing_qty"],
                precision_rounding=rounding,
            )

        return res
