import logging
import re
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from collections import defaultdict

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    physical_locations_ids = fields.Many2many(
        'stock.location', 
        string='Physical Locations', 
        domain="[('location_id', '!=', False), ('child_ids', '=', False)]"
    )

    show_physical_locations = fields.Boolean(
        compute="_compute_show_physical_locations",
    )

    quantity = fields.Float(
        compute="_compute_available_quantity",
        help="The Availability of the product to sell.",
        digits="Product Unit of Measure",
        store=True,
    )

    free_qty = fields.Float(
        'Free To Use Quantity', 
        compute='_compute_free_qty', 
        search='_search_free_qty', 
        compute_sudo=False, 
        digits='Product Unit of Measure'
    )

    alternate_code = fields.Char(
        string="Alternate Code",
        help="Alternate code for the product",
    )

    physical_location_id = fields.Many2one(
        "stock.location",
        string="Physical Location",
        default=lambda self: self.env.company.main_warehouse_id.lot_stock_id.id,
        domain=[("usage", "=", "internal")],
        tracking=True,
    )

    priority_location = fields.Integer(
        string="Priority", related="physical_location_id.priority", store=True
    )

    def _compute_show_physical_locations(self):
        for product in self:
            product.show_physical_locations = self.env.company.use_alternate_locations

    price_with_tax = fields.Float(compute="_compute_prices_with_tax")
    price_without_tax = fields.Float(compute="_compute_prices_with_tax")

    liters_per_unit = fields.Float(digits="Stock Weight")

    company_id = fields.Many2one(tracking=True)

    can_edit_company_id = fields.Boolean(
        string="Puede editar la compañía",
        compute="_compute_can_edit_company_id",
        help="Indica si el usuario actual puede modificar la compañía del producto.",
    )

    def button_dummy(self):
        # TDE FIXME: this button is very interesting
        # Maldito Raiver e.e
        return True

    @api.constrains("list_price")
    def _check_list_price(self):

        if self.env.context.get('install_mode'):
            return

        for product in self:
            if product.list_price <= 0:
                raise ValidationError(_("Price cannot be negative or zero."))

    def write(self, vals):
        if (
            "company_id" in vals
            and not self.env.su
            and not self.env.user.has_group("l10n_ve_stock.group_edit_product_company")
        ):
            raise AccessError(
                _("No tienes permiso para cambiar la compañía de este producto.")
            )

        old_physical_locations_ids = {
            tmpl.id: tmpl.physical_locations_ids for tmpl in self
        }

        res = super().write(vals)
        if "taxes_id" in vals:
            self._validate_single_sale_tax()

        if not self.env.company.use_alternate_locations:
            return res

        if "physical_locations_ids" in vals:
            for tmpl in self:
                old_locations = old_physical_locations_ids.get(tmpl.id, self.env["stock.location"])
                new_locations = tmpl.physical_locations_ids
                removed_locations = old_locations - new_locations
                added_locations = new_locations - old_locations
                if removed_locations:
                    tmpl._remove_putaway_rules(removed_locations)
                if added_locations:
                    tmpl._create_putaway_rules(added_locations)
            self._sync_alter_locations_from_physical_locations()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Always validate after creation because default taxes can come from multiple sources
        records._validate_single_sale_tax()

        if not self.env.company.use_alternate_locations:
            return records

        for tmpl, vals in zip(records, vals_list):
            if vals.get("physical_locations_ids"):
                tmpl._create_putaway_rules(tmpl.physical_locations_ids)

        records._sync_alter_locations_from_physical_locations()
        return records

    def _validate_single_sale_tax(self):
        for product in self:
            taxes_by_company = defaultdict(int)
            for tax in product.taxes_id.sudo():
                taxes_by_company[tax.company_id] += 1
                if taxes_by_company[tax.company_id] > 1:
                    raise ValidationError(_("This product must have only one tax."))   

    @api.depends("list_price")
    def _compute_prices_with_tax(self):
        for product in self:
            if not product.taxes_id:
                product.price_with_tax = product.list_price
                product.price_without_tax = product.list_price
                continue
            taxes = product.taxes_id.compute_all(
                product.list_price, product.currency_id, 1, product=product
            )
            product.price_with_tax = taxes["total_included"]
            product.price_without_tax = taxes["total_excluded"]

    @api.depends("qty_available","free_qty")
    def _compute_available_quantity(self):
        for product in self:
            current_company = self.env.company
            if not current_company.use_free_qty_odoo:
                stock_quant = self.env["stock.quant"].search(
                    [
                        ("product_tmpl_id", "=", product.id),
                        ("on_hand", "=", True),
                        ("product_tmpl_id.type", "!=", "service"),
                    ]
                )
                quantity_available = 0.0
                for quant in stock_quant:
                    if (
                        quant.warehouse_id.lot_stock_id == quant.location_id
                        or quant.warehouse_id.lot_stock_id == quant.location_id.location_id
                    ):
                        quantity_available += quant.available_quantity
                product.quantity = quantity_available if quantity_available >= 0 else 0
                continue
            product.quantity = product.free_qty

    @api.depends('product_variant_ids.free_qty')
    def _compute_free_qty(self):
        for template in self:
            free_qty = 0
            for p in template.product_variant_ids:
                free_qty += p.free_qty
            template.free_qty = free_qty

    def _search_free_qty(self, operator, value):
        domain = [('free_qty', operator, value)]
        product_variant_query = self.env['product.product'].sudo()._search(domain)
        return [('product_variant_ids', 'in', product_variant_query)]

    @api.depends_context("uid")
    def _compute_can_edit_company_id(self):
        can_edit = self.env.user.has_group("l10n_ve_stock.group_edit_product_company")
        for product in self:
            product.can_edit_company_id = can_edit

    #PHYSICAL LOCATIONS

    def _create_or_update_alter_location(self, old_location=None):
        self.ensure_one()
        alter_location_model = self.env["stock.picking.alter.location"]

        new_location = self.physical_location_id
        if not new_location:
            return

        product_variant = self.product_variant_id
        if not product_variant:
            return

        new_warehouse = self._find_warehouse_from_location(new_location)
        if not new_warehouse:
            return

        existing = alter_location_model.search(
            [
                ("product_id", "=", product_variant.id),
                ("warehouse_id", "=", new_warehouse.id),
            ],
            limit=1,
        )

        if not existing:
            alter_lines = self._get_quants_for_alter_lines(
                new_location, warehouse=new_warehouse
            )
            alter_location_model.sudo().create(
                {
                    "product_id": product_variant.id,
                    "pick_location": new_location.id,
                    "warehouse_id": new_warehouse.id,
                    "stock_alter_location_lines": alter_lines,
                }
            )
            return

        existing.pick_location = new_location

    def _sync_alter_locations_from_physical_locations(self):
        alter_location_model = self.env["stock.picking.alter.location"]

        for template in self:
            product_variant = template.product_variant_id
            if not product_variant:
                continue

            physical_locations = template.physical_locations_ids
            active_warehouses = set()

            if physical_locations:
                warehouse_groups = {}
                for location in physical_locations:
                    warehouse = template._find_warehouse_from_location(location)
                    if not warehouse:
                        continue
                    warehouse_groups.setdefault(warehouse, []).append(location)
                    active_warehouses.add(warehouse.id)

                for warehouse, locations in warehouse_groups.items():
                    pick_location = locations[0]

                    existing = alter_location_model.search(
                        [
                            ("product_id", "=", product_variant.id),
                            ("warehouse_id", "=", warehouse.id),
                        ],
                        limit=1,
                    )
                    if not existing:
                        archived = alter_location_model.with_context(active_test=False).search(
                            [
                                ("product_id", "=", product_variant.id),
                                ("warehouse_id", "=", warehouse.id),
                                ("active", "=", False),
                            ],
                            limit=1,
                        )
                        if archived:
                            archived.write(
                                {
                                    "active": True,
                                    "pick_location": pick_location.id,
                                }
                            )
                        else:
                            alter_lines = template._get_quants_for_alter_lines(
                                pick_location, warehouse=warehouse
                            )
                            alter_location_model.sudo().create(
                                {
                                    "product_id": product_variant.id,
                                    "pick_location": pick_location.id,
                                    "warehouse_id": warehouse.id,
                                    "stock_alter_location_lines": alter_lines,
                                }
                            )
                    elif existing.pick_location.id != pick_location.id:
                        existing.pick_location = pick_location.id

            inactive_alters = alter_location_model.with_context(active_test=False).search(
                [
                    ("product_id", "=", product_variant.id),
                    ("active", "=", True),
                ]
            )
            for alter in inactive_alters:
                if alter.warehouse_id.id not in active_warehouses:
                    alter.write({"active": False})

    def _get_quants_for_alter_lines(self, pick_location, warehouse=None):
        self.ensure_one()
        alter_lines_list = []
        if warehouse is None:
            warehouse = self._find_warehouse_from_location(pick_location)
        if not warehouse:
            return alter_lines_list

        quants = self.env["stock.quant"].search(
            [
                ("product_tmpl_id", "=", self.id),
                ("location_id", "in", warehouse.view_location_id.child_internal_location_ids.ids),
            ]
        )

        for quant in quants:
            if quant.available_quantity > 0:
                alter_lines_list.append(
                    (
                        0,
                        0,
                        {
                            "location_id": quant.location_id.id,
                            "available_qty": quant.available_quantity,
                        },
                    )
                )

        return alter_lines_list

    def _find_warehouse_from_location(self, location):
        warehouse_model = self.env["stock.warehouse"]
        loc = location
        while loc:
            wh = warehouse_model.search(
                [("view_location_id", "=", loc.id)], limit=1
            )
            if wh:
                return wh
            loc = loc.location_id
        return warehouse_model.browse()

    def _create_putaway_rules(self, locations):
        """Creates or updates storage (Putaway Rules) for the given locations.

        If a rule already exists for the product and incoming location (parent),
        updates its destination location. Otherwise, creates it.
        """
        putaway_obj = self.env['stock.putaway.rule']
        
        for template in self:
            for location in locations:
                parent_location = location.location_id

                if not parent_location:
                    continue
                
                for variant in template.product_variant_ids:
                    existing_rule = putaway_obj.search([
                        ('product_id', '=', variant.id),
                        ('location_in_id', '=', parent_location.id),
                    ], limit=1)
                    
                    if existing_rule:
                        existing_rule.write({'location_out_id': location.id})
                    else:
                        putaway_obj.create({
                            'product_id': variant.id,
                            'location_in_id': parent_location.id,
                            'location_out_id': location.id,
                            'company_id': template.company_id.id or self.env.company.id,
                        })

    def _remove_putaway_rules(self, locations):
        """Removes the storage rules associated with the removed locations."""
        putaway_obj = self.env['stock.putaway.rule']
        
        for template in self:
            for location in locations:
                for variant in template.product_variant_ids:
                    rules = putaway_obj.search([
                        ('product_id', '=', variant.id),
                        ('location_out_id', '=', location.id),
                    ])
                    rules.unlink()
