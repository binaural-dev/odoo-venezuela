from odoo import api, fields, models, _
from odoo.tools import html2plaintext, is_html_empty
from odoo.tools.float_utils import float_compare
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    picker_id = fields.Many2one(
        "hr.employee", string="Picker", domain=[("role_picking", "!=", False)]
    )
    picking_time_ids = fields.One2many("stock.picking.time", "pick_id")
    cart_id = fields.Many2one("stock.picking.cart", string="Cart")

    supervisor_approve_for_incomplete_qty_id = fields.Many2one("hr.employee", readonly=False)

    pick_move_line_ids = fields.One2many(
        "stock.move.line", "picking_id", "Operations", compute="_compute_pick_move_line_ids"
    )

    operation_start_date = fields.Datetime(compute="_compute_time_elapsed")
    operation_pause_date = fields.Datetime(compute="_compute_time_elapsed")
    operation_end_date = fields.Datetime(compute="_compute_time_elapsed")
    operation_state = fields.Selection(
        selection=[
            ("paused", "Pause"),
            ("ready", "To start"),
            ("in_process", "In process"),
            ("finished", "Finished"),
            ("cancel", "Cancel"),
        ],
        compute="_compute_operation_state",
        default="ready",
        store=True,
        copy=False,
    )
    total_time_elapsed = fields.Float(string="Total time elapsed", compute="_compute_time_elapsed")
    total_lines = fields.Integer(compute="_compute_total_lines")

    def set_time_operation(self, operation_type, employee_id=False):
        if not employee_id:
            employee_id = self.picker_id
        values = self.env["stock.picking.time"]
        for record in self:
            if operation_type == "pause":
                record.assign_new_pick_to_employee()

            values = values.create(
                {"pick_id": record.id, "employee_id": employee_id.id, "type": operation_type}
            )
        return values

    @api.depends("move_line_ids_without_package")
    def _compute_total_lines(self):
        for picking_report in self:
            picking_report.total_lines = len(
                [line for line in picking_report.mapped("move_line_ids_without_package")]
            )

    def set_supervisor_for_incomplete_qty(self, supervisor_id):
        self.supervisor_approve_for_incomplete_qty_id = supervisor_id

    @api.depends("picking_time_ids")
    def _compute_time_elapsed(self):
        """
        This function calculate total time of operation with the lines of picking_time_ids
        """
        for record in self:
            start_time = False
            pause_time = False
            end_time = False
            for line in record.picking_time_ids:
                if line.type == "start":
                    start_time = line.create_date
                if line.type == "end":
                    end_time = line.create_date
                if line.type == "pause":
                    pause_time = line.create_date
                if line.type == "resume":
                    start_time = line.create_date
                    pause_time = False

            record.operation_start_date = start_time
            record.operation_pause_date = pause_time
            record.operation_end_date = end_time

            if record.operation_start_date and record.operation_end_date:
                record.total_time_elapsed = (
                    record.operation_end_date - record.operation_start_date
                ).total_seconds() / 60
            else:
                record.total_time_elapsed = False

    def assign_new_pick_to_employee(self):
        if self.picker_id.pick_ids.filtered(lambda x: x.operation_state in ["ready"]):
            return

        if (
            self.picker_id.user_id.property_warehouse_id.delivery_steps == "pick_ship"
            and self.picker_id.role_picking == "out"
        ):
            return

        if self.picker_id.available_picks_ids:
            self.picker_id.available_picks_ids[0].picker_id = self.picker_id

    def button_validate(self):
        res = super().button_validate()
        for record in self:
            if res == True:
                user = record.env["res.users"].browse(record._context.get("uid", 1))
                record.env["stock.picking.time"].create(
                    {"pick_id": record.id, "employee_id": user.employee_id.id, "type": "end"}
                )

                type_delivery_step = "pick"
                if record.location_id.warehouse_id.delivery_steps == "ship_only":
                    type_delivery_step = "out"

                if record.type_delivery_step == "out":
                    record.cart_id.pick_id = False
                    record.cart_id.out_id = False
                    record.cart_id.pack_id = False

                if record.type_delivery_step == type_delivery_step:
                    record.assign_new_pick_to_employee()

                if (
                    record.type_delivery_step == "out"
                    and self.env.company.create_invoice_after_validate_out
                ):
                    order = record.sale_id
                    wizard = self.env["sale.advance.payment.inv"].create(
                        {
                            "sale_order_ids": order.ids,
                            "advance_payment_method": "delivered",
                        }
                    )
                    wizard._create_invoices(wizard.sale_order_ids)
        return res

    @api.depends("operation_start_date", "operation_pause_date", "operation_end_date", "state")
    def _compute_operation_state(self):
        for picking in self:
            if picking.state == "done":
                picking.operation_state = "finished"
                continue
            if picking.state == "cancel":
                picking.operation_state = "cancel"
                continue
            if picking.operation_state in ["ready", "paused"] and picking.operation_start_date:
                picking.operation_state = "in_process"
                continue
            if picking.operation_state == "in_process" and picking.operation_pause_date:
                picking.operation_state = "paused"
                continue
            if picking.operation_state == "in_process" and (
                picking.operation_end_date or picking.state == "done"
            ):
                picking.operation_state = "finished"
                continue

    def action_confirm(self):
        res = super().action_confirm()
        for record in self:
            type_delivery_step = "pick"
            if record.location_id.warehouse_id.delivery_steps == "ship_only":
                type_delivery_step = "out"
            if record.type_delivery_step == type_delivery_step:
                record.picker_id = record.get_available_picker()
        return res

    def get_picker_operations(self):
        stock_picking_ids = self
        stock_picking_ids |= self._get_picks()
        stock_picking_ids |= self._get_outs()
        stock_picking_ids |= self._get_packs()
        employees = []
        for picking in stock_picking_ids:
            if picking.type_delivery_step == "pick":
                employees.append((_("Pick Operator"), picking.picker_id.name))
            if picking.type_delivery_step == "out":
                employees.append((_("Out Operator"), picking.picker_id.name))
            if picking.type_delivery_step == "pack":
                employees.append((_("Pack Operator"), picking.picker_id.name))

        return employees

    def get_available_picker(self):
        init_role_picking = "picker"
        if self.location_id.warehouse_id.delivery_steps == "ship_only":
            init_role_picking = "out"
        picker_ids = self.env["hr.employee"].search([("role_picking", "=", init_role_picking)])
        for picker in picker_ids:
            if picker.available_to_assing_picking():
                return picker.id
        return False

    @api.depends("origin")
    def _compute_pick_move_line_ids(self):
        for record in self:
            pick_id = record._get_picks()
            record.pick_move_line_ids = pick_id.move_line_ids

    def _get_fields_stock_barcode(self):
        res = super()._get_fields_stock_barcode()
        res.append("move_ids")
        res.append("pick_move_line_ids")
        res.append("picks_count")
        return res

    def _get_stock_barcode_data(self):
        """
        This function was overwritten to be able to add products that were not in stock.move.line
        but are in stock.move

        This function also adds the stock.move model to the list of records
        """

        # Avoid to get the products full name because code and name are separate in the barcode app.
        self = self.with_context(display_default_code=False)
        move_lines = self.move_line_ids
        lots = move_lines.lot_id
        owners = move_lines.owner_id
        # Fetch all implied products in `self` and adds last used products to avoid additional rpc.
        products = move_lines.product_id
        for move in self.move_ids:
            products |= move.product_id
        packagings = products.packaging_ids

        uoms = products.uom_id | move_lines.product_uom_id
        # If UoM setting is active, fetch all UoM's data.
        if self.env.user.has_group("uom.group_uom"):
            uoms |= self.env["uom.uom"].search([])

        # Fetch `stock.location`
        source_locations = self.env["stock.location"].search(
            [("id", "child_of", self.location_id.ids)]
        )
        destination_locations = self.env["stock.location"].search(
            [("id", "child_of", self.location_dest_id.ids)]
        )
        locations = (
            move_lines.location_id
            | move_lines.location_dest_id
            | source_locations
            | destination_locations
        )

        # Fetch `stock.quant.package` and `stock.package.type` if group_tracking_lot.
        packages = self.env["stock.quant.package"]
        package_types = self.env["stock.package.type"]
        if self.env.user.has_group("stock.group_tracking_lot"):
            packages |= move_lines.package_id | move_lines.result_package_id
            packages |= (
                self.env["stock.quant.package"]
                .with_context(pack_locs=destination_locations.ids)
                ._get_usable_packages()
            )
            package_types = package_types.search([])

        data = {
            "records": {
                "stock.picking": self.read(self._get_fields_stock_barcode(), load=False),
                "stock.picking.type": self.picking_type_id.read(
                    self.picking_type_id._get_fields_stock_barcode(), load=False
                ),
                "stock.move.line": move_lines.sorted(key=lambda x: x.priority_location).read(
                    move_lines._get_fields_stock_barcode(), load=False
                ),
                "stock.move": self.move_ids.sorted(key=lambda x: x.priority_location).read(
                    self.move_ids._get_fields_stock_barcode(), load=False
                ),
                # `self` can be a record set (e.g.: a picking batch), set only the first partner in the context.
                "product.product": products.with_context(partner_id=self[:1].partner_id.id).read(
                    products._get_fields_stock_barcode(), load=False
                ),
                "product.packaging": packagings.read(
                    packagings._get_fields_stock_barcode(), load=False
                ),
                "res.partner": owners.read(owners._get_fields_stock_barcode(), load=False),
                "stock.location": locations.read(locations._get_fields_stock_barcode(), load=False),
                "stock.package.type": package_types.read(
                    package_types._get_fields_stock_barcode(), False
                ),
                "stock.quant.package": packages.read(
                    packages._get_fields_stock_barcode(), load=False
                ),
                "stock.lot": lots.read(lots._get_fields_stock_barcode(), load=False),
                "uom.uom": uoms.read(uoms._get_fields_stock_barcode(), load=False),
            },
            "nomenclature_id": [self.env.company.nomenclature_id.id],
            "source_location_ids": source_locations.ids,
            "destination_locations_ids": destination_locations.ids,
        }
        # Extracts pickings' note if it's empty HTML.
        for picking in data["records"]["stock.picking"]:
            picking["note"] = (
                False if is_html_empty(picking["note"]) else html2plaintext(picking["note"])
            )

        data["config"] = self.picking_type_id._get_barcode_config()
        data["line_view_id"] = self.env.ref("stock_barcode.stock_move_line_product_selector").id
        data["form_view_id"] = self.env.ref("stock_barcode.stock_picking_barcode").id
        data["package_view_id"] = self.env.ref("stock_barcode.stock_quant_barcode_kanban").id
        return data

    def action_cancel(self):
        res = super().action_cancel()
        if res:
            for record in self:
                record.picker_id = False
                record.cart_id.clear_cart()
        return res

    def _check_incomplete(self):
        prec = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        backorder_pickings = self.browse()
        for picking in self:
            quantity_todo = {}
            quantity_done = {}
            for move in picking.move_ids.filtered(lambda m: m.state != "cancel"):
                quantity_todo.setdefault(move.product_id.id, 0)
                quantity_done.setdefault(move.product_id.id, 0)
                quantity_todo[move.product_id.id] += move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id, rounding_method="HALF-UP"
                )
                quantity_done[move.product_id.id] += move.product_uom._compute_quantity(
                    move.quantity_done, move.product_id.uom_id, rounding_method="HALF-UP"
                )
            # FIXME: the next block doesn't seem nor should be used.
            for ops in picking.mapped("move_line_ids").filtered(
                lambda x: x.package_id and not x.product_id and not x.move_id
            ):
                for quant in ops.package_id.quant_ids:
                    quantity_done.setdefault(quant.product_id.id, 0)
                    quantity_done[quant.product_id.id] += quant.qty
            for pack in picking.mapped("move_line_ids").filtered(
                lambda x: x.product_id and not x.move_id
            ):
                quantity_done.setdefault(pack.product_id.id, 0)
                quantity_done[pack.product_id.id] += pack.product_uom_id._compute_quantity(
                    pack.qty_done, pack.product_id.uom_id
                )
            if any(
                float_compare(
                    quantity_done[x],
                    quantity_todo.get(x, 0),
                    precision_digits=prec,
                )
                == -1
                for x in quantity_done
            ):
                backorder_pickings |= picking
        return backorder_pickings

    def _pre_action_done_hook(self):
        pickings_incomplete = self._check_incomplete()
        if (
            pickings_incomplete
            and pickings_incomplete.type_delivery_step in ["pick", "out", "pack"]
            and not self.env.context.get("skip_incomplete_qty")
        ):
            return pickings_incomplete._action_picking_incomplete_wizard()
        return super()._pre_action_done_hook()

    def _action_picking_incomplete_wizard(self):
        view = self.env.ref("binaural_stock_barcode.stock_picking_incomplete_form_wizard")
        return {
            "name": _("Validate Incomplete"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "stock.picking.incomplete",
            "views": [(view.id, "form")],
            "view_id": view.id,
            "target": "new",
            "context": dict(self.env.context, default_pick_id=self.id),
        }
