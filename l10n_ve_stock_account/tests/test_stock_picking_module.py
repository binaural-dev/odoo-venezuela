from unittest.mock import patch
from odoo import fields, _
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

class _ToggleDict(dict):
    """Dictionary-like helper that controls `in` checks order."""

    def __init__(self, quantity):
        super().__init__(quantity=quantity)
        self._calls = 0

    def __contains__(self, key):
        self._calls += 1
        if self._calls == 1:
            return False
        if self._calls == 2:
            return True
        if self._calls == 3:
            return False
        return True


@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestStockPicking(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.StockPicking = cls.env["stock.picking"]
        cls.ProcurementGroup = cls.env["procurement.group"]
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.out_type = cls.env.ref("stock.picking_type_out")
        cls.in_type = cls.env.ref("stock.picking_type_in")
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.category_all = cls.env.ref("product.product_category_all")
        
        tmpl = cls.env["product.template"].create({
            "name": "Producto de Prueba",
            "type": "consu",
            "uom_id": cls.uom_unit.id,
            "uom_po_id": cls.uom_unit.id,
            "categ_id": cls.category_all.id,
        })
        cls.product = tmpl.product_variant_id
        cls.stock_location = cls.env['stock.location'].create({
            'name': 'Main Stock',
            'usage': 'internal',
            'company_id': cls.env.company.id,
        })
        # Crear ubicación de salida (clientes)
        cls.output_location = cls.env['stock.location'].create({
            'name': 'Output',
            'usage': 'customer',
            'company_id': cls.env.company.id,
        })
        cls.qc_location = cls.env['stock.location'].create({
            'name': 'Quality Control',
            'usage': 'internal',
            'company_id': cls.env.company.id,
        })
        # Crear el almacén usando las ubicaciones creadas
        cls.warehouse = cls.env['stock.warehouse'].create({
            'name': 'Test Warehouse',
            'code': 'TWH',
            'company_id': cls.env.company.id,
            'lot_stock_id': cls.stock_location.id,
            'wh_output_stock_loc_id': cls.output_location.id,
            'reception_steps': 'one_step',
            'delivery_steps': 'ship_only',
            'qc_type_id': {
                'name': _('Quality Control'),
                'code': 'quality',
                'default_location_src_id': cls.qc_location.id,
                'default_location_dest_id': cls.qc_location.id,
                'sequence': 30,
                'sequence_code': 'QC',
                'company_id': cls.env.company.id,
            }
        })

    def _create_picking(self, picking_type_id=None, **extra):
        picking_type = self.env["stock.picking.type"].browse(picking_type_id) if picking_type_id else self.out_type
        vals = {
            "name": "Test Picking",
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
        }
        vals.update(extra)
        return self.StockPicking.create(vals)

    def _create_out_picking_with_move(self):
        picking = self._create_picking(
            move_ids_without_package=[
                (
                    0,
                    0,
                    {
                        "name": "Test move",
                        "product_id": self.product.id,
                        "product_uom_qty": 2.0,
                        "product_uom": self.product.uom_id.id,
                        "location_id": self.out_type.default_location_src_id.id,
                        "location_dest_id": self.out_type.default_location_dest_id.id,
                    },
                )
            ]
        )
        return picking, picking.move_ids_without_package

    def _add_blocking_group(self):
        group = self.env.ref(
            "l10n_ve_stock.group_block_type_inventory_transfers_expeditions"
        )
        self.env.user.write({"groups_id": [(4, group.id)]})
        return group

    def test_action_get_outs_with_multiple_matches_sets_domain(self):
        group = self.ProcurementGroup.create({"name": "Group domain"})
        picking_main = self._create_picking(group_id=group.id)
        other_one = self._create_picking(group_id=group.id)
        other_two = self._create_picking(group_id=group.id)

        action = picking_main.action_get_outs()

        self.assertEqual(action["domain"], [("id", "in", (other_one | other_two).ids)])
        self.assertEqual(action["context"]["default_origin"], picking_main.name)
        self.assertEqual(action["context"]["default_group_id"], group.id)

    def test_action_get_packs_single_match_opens_form_view(self):
        group = self.ProcurementGroup.create({"name": "Group form"})
        pack_type = self.warehouse.pack_type_id
        pack_main = self._create_picking(picking_type_id=pack_type.id, group_id=group.id)
        other_pack = self._create_picking(picking_type_id=pack_type.id, group_id=group.id)

        action = pack_main.action_get_packs()

        self.assertEqual(action["res_id"], other_pack.id)
        self.assertEqual(action["views"][0][1], "form")
        self.assertEqual(action["context"]["default_picking_type_id"], pack_type.id)

    def test_action_get_picks_without_results_raises_error(self):
        picking = self._create_picking()
        with self.assertRaises(UserError):
            picking.action_get_picks()

    def test_getters_respect_assignment_and_group(self):
        group = self.ProcurementGroup.create({"name": "Group getters"})
        pick_type = self.warehouse.pick_type_id
        pick_picking = self._create_picking(picking_type_id=pick_type.id, group_id=group.id)
        self.assertEqual(pick_picking.type_delivery_step, "pick")
        self.assertEqual(pick_picking._get_picks(assigned=True), pick_picking)

        pack_type = self.warehouse.pack_type_id
        pack_picking = self._create_picking(picking_type_id=pack_type.id, group_id=group.id)
        self.assertEqual(pack_picking.type_delivery_step, "pack")
        self.assertEqual(pack_picking._get_packs(assigned=True), pack_picking)

        out_picking = self._create_picking(group_id=group.id)
        self.assertFalse(out_picking._get_picks())
        self.assertFalse(out_picking._get_packs())
        outs = out_picking._get_outs()
        self.assertTrue(all(p.group_id == group for p in outs))
        # assigned=True branch should trigger a limited search without raising
        self.assertTrue(hasattr(out_picking._get_picks(assigned=True), "ids"))
        self.assertTrue(hasattr(out_picking._get_outs(assigned=True), "ids"))

    def test_compute_helpers_count_related_pickings(self):
        group = self.ProcurementGroup.create({"name": "Group counts"})
        main = self._create_picking(group_id=group.id)
        self._create_picking(group_id=group.id)
        self._create_picking(group_id=group.id, picking_type_id=self.warehouse.pick_type_id.id)
        self._create_picking(group_id=group.id, picking_type_id=self.warehouse.pack_type_id.id)

        main._compute_stock_pickings_by_origin()

        self.assertEqual(main.outs_count, 1)
        self.assertEqual(main.picks_count, 1)
        self.assertEqual(main.packs_count, 1)

    def test_compute_type_delivery_step_uses_picking_type(self):
        pick_type = self.warehouse.pick_type_id
        pick = self._create_picking(picking_type_id=pick_type.id)
        self.assertEqual(pick.type_delivery_step, "pick")
        pick._compute_type_delivery_step()
        self.assertEqual(pick.type_delivery_step, "pick")

    def test_create_allows_outgoing_without_group(self):
        picking = self._create_picking()
        self.assertEqual(picking.type_delivery_step, "out")

    def test_create_blocked_for_outgoing_with_blocking_group(self):
        self._add_blocking_group()
        with self.assertRaises(UserError):
            self._create_picking()

    def test_validate_block_transfer_allows_non_outgoing(self):
        self._add_blocking_group()
        self.StockPicking.validate_block_transfers_expedition(
            self.env["stock.picking"], vals={"picking_type_id": self.in_type.id}
        )

    def test_validate_block_transfer_restrictions(self):
        picking, moves = self._create_out_picking_with_move()
        move = moves[0]
        self._add_blocking_group()

        with self.assertRaises(UserError):
            picking.validate_block_transfers_expedition(
                write={"move_ids_without_package": [(0, "new", {})]},
                matched_key="move_ids_without_package",
            )
        with self.assertRaises(UserError):
            picking.validate_block_transfers_expedition(
                write={"move_ids_without_package": [(1, move.id, False)]},
                matched_key="move_ids_without_package",
            )
        with self.assertRaises(UserError):
            picking.validate_block_transfers_expedition(
                write={
                    "move_ids_without_package": [
                        (1, move.id, {"quantity": move.product_uom_qty + 1})
                    ]
                },
                matched_key="move_ids_without_package",
            )
        move_line = self.env["stock.move.line"].create(
            {
                "picking_id": picking.id,
                "move_id": move.id,
                "company_id": self.env.company.id,
                "product_id": self.product.id,
                "product_uom_id": self.product.uom_id.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.customer_location.id,
                "product_uom_qty": 1,
                "reserved_uom_qty": 0,
                "qty_done": 0,
                "date": fields.Datetime.now(),
            }
        )
        with self.assertRaises(UserError):
            picking.validate_block_transfers_expedition(
                write={
                    "move_line_ids_without_package": [
                        (1, move_line.id, _ToggleDict(1))
                    ]
                },
                matched_key="move_line_ids_without_package",
            )

    def test_validate_block_transfer_accepts_safe_quantity(self):
        picking, moves = self._create_out_picking_with_move()
        move = moves[0]
        self._add_blocking_group()

        picking.validate_block_transfers_expedition(
            write={"move_ids_without_package": [(1, move.id, {"quantity": 1})]},
            matched_key="move_ids_without_package",
        )

    def test_write_triggers_validation_hook_for_tracked_keys(self):
        picking, moves = self._create_out_picking_with_move()
        move = moves[0]
        with patch.object(
            type(picking),
            "validate_block_transfers_expedition",
            wraps=picking.validate_block_transfers_expedition,
        ) as mocked_validator:
            picking.write({"move_ids_without_package": [(1, move.id, {})]})
        mocked_validator.assert_called_once()

    def test_action_assign_context_management(self):
        pack = self._create_picking(picking_type_id=self.warehouse.pack_type_id.id)
        with patch(
            "odoo.addons.stock.models.stock_picking.StockPicking.action_assign", autospec=True
        ) as mock_super_assign:
            mock_super_assign.return_value = "done"
            result = pack.action_assign()
        self.assertEqual(result, "done")
        called_self = mock_super_assign.call_args[0][1]
        self.assertIn("skip_physical_location", called_self.env.context)

    def test_action_assign_does_not_alter_pick_context(self):
        pick = self._create_picking(picking_type_id=self.warehouse.pick_type_id.id)
        with patch(
            "odoo.addons.stock.models.stock_picking.StockPicking.action_assign", autospec=True
        ) as mock_super_assign:
            mock_super_assign.return_value = "done"
            result = pick.action_assign()
        self.assertEqual(result, "done")
        called_self = mock_super_assign.call_args[0][1]
        self.assertNotIn("skip_physical_location", called_self.env.context)

    def test_get_sequence_guide_num(self):
        self.env['ir.sequence'].search([
            ('code', '=', 'guide.number'),
            ('company_id', '=', self.company.id)
        ]).unlink()
        first = self.picking.get_sequence_guide_num()
        second = self.picking.get_sequence_guide_num()
        self.assertNotEqual(first, second)

    def test_validate_one_invoice_posted(self):
        journal = self.env['account.journal'].create({
            'name': 'Sales Journal',
            'type': 'sale',
            'code': 'SAL',
            'company_id': self.company.id,
        })
        income_account = self.env['account.account'].search([
            ('user_type_id.type', '=', 'other'),
            ('company_id', '=', self.company.id)
        ], limit=1)
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'journal_id': journal.id,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Line',
                    'account_id': income_account.id,
                    'price_unit': 100,
                    'quantity': 1,
                })
            ],
            'picking_ids': [Command.link(self.picking.id)],
        })
        move.action_post()
        with self.assertRaises(UserError):
            self.picking._validate_one_invoice_posted()

    def test_get_invoice_lines_for_invoice_sale_line_price(self):
        tax = self.env['account.tax'].search([
            ('type_tax_use', '=', 'sale')
        ], limit=1)
        self.company.account_sale_tax_id = tax.id
        product = self.env['product.product'].create({
            'name': 'Prod',
            'type': 'product',
            'list_price': 100,
        })
        sale = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        sale_line = self.env['sale.order.line'].create({
            'order_id': sale.id,
            'product_id': product.id,
            'price_unit': 150,
            'product_uom_qty': 1,
            'name': product.name,
        })
        move = self.env['stock.move'].create({
            'name': product.name,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 1,
            'location_id': self.picking.location_id.id,
            'location_dest_id': self.picking.location_dest_id.id,
            'picking_id': self.picking.id,
            'sale_line_id': sale_line.id,
            'quantity': 1,
        })
        self.picking.sale_id = sale.id
        lines = self.picking._get_invoice_lines_for_invoice()
        self.assertEqual(lines[0][2]['price_unit'], sale_line.price_unit)
