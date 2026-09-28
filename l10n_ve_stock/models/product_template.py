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

    show_physical_relocation_reserved_warning = fields.Boolean(
        compute="_compute_show_physical_relocation_reserved_warning",
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

    @api.depends("physical_locations_ids")
    def _compute_show_physical_relocation_reserved_warning(self):
        for product in self:
            product.show_physical_relocation_reserved_warning = (
                product._has_reserved_stock_in_replaced_locations()
            )

    def _has_reserved_stock_in_replaced_locations(self):
        """Whether the location(s) being replaced hold reserved stock.

        Used to warn, while editing, that the automatic relocation transfer
        (_relocate_physical_stock) only moves freely available quantity: it
        never drags along stock already reserved for an order.
        """
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.physical_relocation_transfer:
            return False
        removed_locations = self._origin.physical_locations_ids - self.physical_locations_ids
        if not removed_locations:
            return False
        quants = self.env["stock.quant"].sudo().search(
            [
                ("product_id", "in", self.product_variant_ids.ids),
                ("location_id", "in", removed_locations.ids),
                ("reserved_quantity", ">", 0),
            ],
            limit=1,
        )
        return bool(quants)

    price_with_tax = fields.Float(compute="_compute_prices_with_tax")
    price_without_tax = fields.Float(compute="_compute_prices_with_tax")

    liters_per_unit = fields.Float(digits="Stock Weight")

    company_id = fields.Many2one(tracking=True)

    can_edit_company_id = fields.Boolean(
        string="Can edit company",
        compute="_compute_can_edit_company_id",
        help="Whether the current user can modify the product's company.",
    )

    lock_internal_reference_on_moves = fields.Boolean(
        string="Bloquear referencia interna con movimientos",
        compute="_compute_lock_internal_reference_on_moves",
        inverse="_set_lock_internal_reference_on_moves",
        store=True,
        help=(
            "Si está activo, la referencia interna (código) no podrá "
            "modificarse una vez que el producto (siendo almacenable) tenga "
            "movimientos de inventario ya validados (estado 'Hecho'). Un "
            "pedido de compra o venta confirmado, sin la transferencia "
            "asociada validada todavía, no cuenta como movimiento."
        ),
    )

    def button_dummy(self):
        # TDE FIXME: this button is very interesting
        # Maldito Raiver e.e
        return True

    @api.constrains("list_price", "sale_ok")
    def _check_list_price(self):

        if self.env.context.get('install_mode'):
            return

        for product in self:
            if product.sale_ok and product.list_price <= 0:
                raise ValidationError(_("Price cannot be negative or zero."))

    def _check_company_id_edit_allowed(self, vals):
        if "company_id" not in vals:
            return
        if self.env.user.has_group("l10n_ve_stock.group_edit_product_company"):
            return

        new_company = vals["company_id"]
        if not self:
            # create(): no existing record to compare against. copy_data()
            # always sends company_id (field has no copy=False), so
            # duplicating a product must not be treated as an edit as long
            # as the copy lands in the user's own active company - only a
            # value that actually differs from that is a real attempt to
            # set the company. False (no company / "Visible for all
            # companies") is the least privileged state, not a change of
            # company - env.company.id is never False, so comparing
            # against it unconditionally made every explicit
            # company_id=False create() fail for every non-privileged
            # user (shared products, imports, other modules' create()).
            # Only a truthy, different company is a real attempt to
            # assign the product somewhere specific.
            if new_company and new_company != self.env.company.id:
                raise AccessError(
                    _("You don't have permission to change this product's company.")
                )
            return

        # write() can run on several products at once with a single vals
        # dict, so "did it change" has to be checked per product: a value
        # identical to one product's own company_id is a no-op for that
        # product even if it differs for another one in the same call.
        # False is the same least-privileged state as in create() above, so
        # clearing a product's company is allowed without the group too -
        # only assigning a specific, different company is restricted.
        for product in self:
            if new_company and new_company != product.company_id.id:
                raise AccessError(
                    _("You don't have permission to change this product's company.")
                )

    def write(self, vals):
        self._check_company_id_edit_allowed(vals)

        old_physical_locations_ids = {
            tmpl.id: tmpl.physical_locations_ids for tmpl in self
        }
        # default_code and lock_internal_reference_on_moves are both stored
        # fields with their own inverse (_set_default_code on the core side,
        # _set_lock_internal_reference_on_moves here), so Odoo runs them as
        # separate write() calls on the variant, in vals key order. In the
        # resolved form arch, default_code renders before the toggle, so it
        # always arrives first in vals - meaning product.product.write()'s
        # own same-write guard (which reads
        # vals.get("lock_internal_reference_on_moves", ...)) never sees the
        # new toggle value, only the variant's still-locked stored one.
        # Propagate the toggle to the variants directly, before super()
        # triggers any inverse, so unlocking and fixing default_code in the
        # same save always sees the intended state regardless of key order.
        if "lock_internal_reference_on_moves" in vals and "default_code" in vals:
            self.product_variant_ids.write(
                {"lock_internal_reference_on_moves": vals["lock_internal_reference_on_moves"]}
            )

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
                tmpl._relocate_physical_stock(old_locations, new_locations)
            self._sync_alter_locations_from_physical_locations()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._check_company_id_edit_allowed(vals)
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
        # Combo products carry no taxes of their own (their taxes come from
        # the component products), so the single-tax rule does not apply to
        # them - same exemption as l10n_ve_accountant (#14405).
        for product in self.filtered(lambda p: p.type != "combo"):
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

    # AUTOMATIC RELOCATION WHEN A PHYSICAL LOCATION IS REPLACED

    def _relocate_physical_stock(self, locations_before, locations_after):
        """Entry point. Returns the generated transfers.

        If l10n_ve_stock_account is installed, the transfer is issued with
        the standard reason "Transfer between warehouses"
        (l10n_ve_stock_account.transfer_reason_transfer_between_warehouses).
        By that module's own existing design, this reason keeps the
        operation from being marked as a dispatch guide, from consuming a
        fiscal sequence number (guide_number), and from staying in the
        invoicing queue (button_validate sets state_guide_dispatch to
        "emited" for that exact combination): no need to duplicate that
        logic here. If the fiscal module is not installed, transfer_reason_id
        simply does not exist and is never written.
        """
        self.ensure_one()
        Picking = self.env["stock.picking"]
        company = self.company_id or self.env.company
        # The automatic relocation is optional and toggled in Settings ->
        # Binaural, and only makes sense if alternate locations tracking is
        # already active (use_alternate_locations).
        if not company.use_alternate_locations:
            return Picking
        if not company.physical_relocation_transfer:
            return Picking
        # Only the inventory manager triggers the relocation.
        if not self.env.user.has_group("stock.group_stock_manager"):
            return Picking
        # From here on this runs as superuser: the transfer touches
        # localization models (stock.picking.alter.location) that require
        # their own groups, and the inventory manager is not expected to
        # have them. The user's permission was already checked above.
        self = self.sudo()
        transfers = self.env["stock.picking"]
        for source, destination in self._pair_relocations(
            locations_before, locations_after
        ):
            # First the new location is registered at zero, then the stock
            # is moved: that way the line is born at zero as requested, and
            # the transfer itself (_sync_relocation_ledger, not an automatic
            # hook) leaves it at the real quantity moved.
            self._register_location_in_alter_location(destination)
            transfers |= self._transfer_between_locations(source, destination)
        return transfers

    @api.model
    def _pair_relocations(self, before, after):
        """Decides which old location empties into which new one.

        - If locations were only added or only removed, there is no
          relocation: that is an addition or removal, not a substitution.
        - If the same number were removed and added, they are paired in id
          order.
        - If the counts do not match, everything leaving the old locations
          goes to the first new one.
        """
        removed = (before - after).sorted("id")
        added = (after - before).sorted("id")
        if not removed or not added:
            return []
        if len(removed) == len(added):
            return list(zip(removed, added))
        destination = added[0]
        return [(source, destination) for source in removed]

    @api.model
    def _free_quantity(self, variant, location):
        """Movable stock: physical quantity minus what is already reserved.

        What is reserved is deliberately left where it is: it belongs to an
        order that will be shipped from that location, and dragging it
        along would break that reservation.
        """
        quants = (
            self.env["stock.quant"]
            .sudo()
            .search(
                [
                    ("product_id", "=", variant.id),
                    ("location_id", "=", location.id),
                ]
            )
        )
        return sum(quant.quantity - quant.reserved_quantity for quant in quants)

    @api.model
    def _internal_operation_type(self, source, destination):
        warehouse = destination.warehouse_id or source.warehouse_id
        if warehouse and warehouse.int_type_id:
            return warehouse.int_type_id
        return (
            self.env["stock.picking.type"]
            .sudo()
            .search(
                [
                    ("code", "=", "internal"),
                    ("company_id", "in", self.env.companies.ids),
                ],
                limit=1,
            )
        )

    def _transfer_between_locations(self, source, destination):
        """Creates and validates the internal transfer source -> destination."""
        self.ensure_one()
        Picking = self.env["stock.picking"].sudo()
        if not source or not destination or source == destination:
            return Picking
        quantities = {}
        for variant in self.product_variant_ids:
            free_qty = self._free_quantity(variant, source)
            if free_qty > 0:
                quantities[variant] = free_qty
        if not quantities:
            # Nothing to move: the new location was still registered.
            return Picking
        picking_type = self._internal_operation_type(source, destination)
        if not picking_type:
            return Picking
        values = {
            "is_physical_relocation": True,
            "picking_type_id": picking_type.id,
            "location_id": source.id,
            "location_dest_id": destination.id,
            "origin": _("Physical location relocation"),
            "company_id": picking_type.company_id.id or self.env.company.id,
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": variant.id,
                        "product_uom": variant.uom_id.id,
                        "product_uom_qty": quantity,
                        "location_id": source.id,
                        "location_dest_id": destination.id,
                    },
                )
                for variant, quantity in quantities.items()
            ],
        }
        if "transfer_reason_id" in Picking._fields:
            reason = self.env.ref(
                "l10n_ve_stock_account.transfer_reason_transfer_between_warehouses",
                raise_if_not_found=False,
            )
            if reason:
                values["transfer_reason_id"] = reason.id
        picking = Picking.create(values)
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = quantities.get(move.product_id, 0.0)
            move.picked = True
        result = picking.button_validate()
        if isinstance(result, dict) and result.get("res_model"):
            # button_validate can return a wizard (backorder or immediate
            # transfer). It is processed without asking.
            wizard = (
                self.env[result["res_model"]]
                .sudo()
                .with_context(**(result.get("context") or {}))
                .create({})
            )
            if hasattr(wizard, "process"):
                wizard.process()
        self._sync_relocation_ledger(source, destination, quantities)
        picking.message_post(
            body=_(
                "Automatic transfer for physical location relocation: from %(source)s to %(destination)s.",
                source=source.complete_name,
                destination=destination.complete_name,
            )
        )
        return picking

    def _sync_relocation_ledger(self, source, destination, quantities):
        """Reflects the real transfer in the alternate locations ledger.

        The automatic sync hook (stock_move.py,
        StockMove._update_alter_location_on_move_done) only updates the
        ledger for moves to/from the Output location: a direct transfer
        between any two physical locations, like this one, does not touch
        it. Without this manual adjustment the destination line would stay
        at zero forever even though the real transfer did move the stock.

        Only applies when source and destination are in the same warehouse:
        the ledger is a record per product+warehouse, there is no single
        line that spans two different warehouses. A transfer between
        warehouses is left for the existing manual reconciliation
        ("Synchronize Quantities with Real Quants").
        """
        if not source.warehouse_id or source.warehouse_id != destination.warehouse_id:
            return
        alter_location_model = self.env["stock.picking.alter.location"]
        for variant, quantity in quantities.items():
            alter = alter_location_model.search(
                [
                    ("product_id", "=", variant.id),
                    ("warehouse_id", "=", source.warehouse_id.id),
                ],
                limit=1,
            )
            if not alter:
                continue
            source_line = alter.stock_alter_location_lines.filtered(
                lambda line, s=source: line.location_id == s
            )
            destination_line = alter.stock_alter_location_lines.filtered(
                lambda line, d=destination: line.location_id == d
            )
            if source_line:
                source_line.available_qty = max(source_line.available_qty - quantity, 0.0)
            if destination_line:
                destination_line.available_qty += quantity

    def _register_location_in_alter_location(self, destination):
        """Adds the new location at zero to Other Product Locations."""
        self.ensure_one()
        Alter = self.env["stock.picking.alter.location"].sudo()
        Line = self.env["stock.picking.alter.location.line"].sudo()
        warehouse = destination.warehouse_id
        for variant in self.product_variant_ids:
            domain = [("product_id", "=", variant.id)]
            if warehouse:
                domain.append(("warehouse_id", "=", warehouse.id))
            record = Alter.search(domain, limit=1)
            if not record:
                continue
            already_exists = record.stock_alter_location_lines.filtered(
                lambda line, d=destination: line.location_id == d
            )
            if already_exists:
                continue
            Line.create(
                {
                    "stock_alter_location_id": record.id,
                    "location_id": destination.id,
                    "available_qty": 0.0,
                }
            )

    @api.depends_context("uid")
    def _compute_can_edit_company_id(self):
        can_edit = self.env.user.has_group("l10n_ve_stock.group_edit_product_company")
        for product in self:
            product.can_edit_company_id = can_edit

    @api.depends("product_variant_ids.lock_internal_reference_on_moves")
    def _compute_lock_internal_reference_on_moves(self):
        self._compute_template_field_from_variant_field(
            "lock_internal_reference_on_moves", default=True
        )

    def _set_lock_internal_reference_on_moves(self):
        self._set_product_variant_field("lock_internal_reference_on_moves")
