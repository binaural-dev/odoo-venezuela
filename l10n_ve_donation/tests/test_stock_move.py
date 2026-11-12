from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged("l10n_ve_donation", "stock_move", "-at_install", "post_install")
class TestStockMove(TestDonationCommon):
    """Valuation journal entry of an outgoing donation delivery
    (`_get_account_move_line_vals` / `_create_account_move`). The donation
    mark and the forcing of the line partner only apply to
    `is_donation and not sale_id and outgoing` pickings."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_partner = cls.company.partner_id

    def _entry(self, picking):
        entry = picking.move_ids.account_move_id
        self.assertEqual(len(entry), 1, "The delivery must generate one valuation entry.")
        return entry

    def test_01_delivery_entry_is_marked_as_donation(self):
        picking = self._create_donation_picking(reason="Medication for patient", validate=True)
        entry = self._entry(picking)
        self.assertTrue(entry.is_donation)
        self.assertEqual(entry.state, "posted")
        self.assertEqual(entry.ref, "Medication for patient")

    def test_02_entry_header_keeps_the_beneficiary(self):
        """The header is the real counterparty (the beneficiary): it is
        what the donation certificate shows."""
        picking = self._create_donation_picking(partner=self.partner, validate=True)
        entry = self._entry(picking)
        self.assertEqual(entry.partner_id, self.partner)

    def test_03_every_line_has_the_company_partner(self):
        """`_check_partner_donation` rejects lines whose partner is not
        the company: with a beneficiary the lines must be forced."""
        picking = self._create_donation_picking(partner=self.partner, validate=True)
        entry = self._entry(picking)
        self.assertTrue(entry.line_ids)
        self.assertEqual(entry.line_ids.partner_id, self.company_partner)

    def test_04_line_names_carry_the_donation_reason(self):
        picking = self._create_donation_picking(
            partner=self.partner, reason="Medication for patient", validate=True
        )
        for line in self._entry(picking).line_ids:
            self.assertIn("Medication for patient", line.name)

    def test_05_entry_debits_the_donation_account(self):
        """Debit: valuation account of the destination (inventory) location;
        credit: the stock valuation account of the product."""
        picking = self._create_donation_picking(quantity=2, reason="x", validate=True)
        entry = self._entry(picking)
        debit = entry.line_ids.filtered("debit")
        credit = entry.line_ids.filtered("credit")
        self.assertEqual(debit.account_id, self.account_expense)
        self.assertEqual(credit.account_id, self.account_stock)
        self.assertEqual(debit.debit, 30.0)

    def test_06_entry_without_reason_keeps_the_core_reference(self):
        picking = self._create_donation_picking(partner=self.partner, validate=True)
        self.assertTrue(self._entry(picking).ref)

    def test_07_regular_delivery_is_not_a_donation(self):
        picking_type = self.warehouse_normal.out_type_id
        product = self.product_storable
        location_src = picking_type.default_location_src_id
        self._create_stock(product, 1, location_src)
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": location_src.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "partner_id": self.partner.id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 1,
                "product_uom": product.uom_id.id,
                "location_id": location_src.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            })],
        })
        self.assertFalse(picking.is_donation)
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({"quantity": 1, "picked": True})
        picking.button_validate()
        self.assertFalse(picking.move_ids._is_donation_delivery_move())
        for entry in picking.move_ids.account_move_id:
            self.assertFalse(entry.is_donation)

    def test_08_donation_and_regular_moves_are_valued_apart(self):
        """The core creates ONE entry for the whole recordset: the donation
        move must not drag the regular one into the donation entry."""
        donation_picking = self._create_donation_picking(partner=self.partner)
        inventory_loss = self.env["stock.location"].create({
            "name": "Regular Inventory Loss",
            "usage": "inventory",
            "company_id": self.company.id,
            "valuation_account_id": self.account_expense.id,
        })
        regular_picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse_normal.out_type_id.id,
            "location_id": self.warehouse_normal.lot_stock_id.id,
            "location_dest_id": inventory_loss.id,
            "move_ids": [Command.create({
                "product_id": self.product_storable.id,
                "product_uom_qty": 1,
                "product_uom": self.product_storable.uom_id.id,
                "location_id": self.warehouse_normal.lot_stock_id.id,
                "location_dest_id": inventory_loss.id,
            })],
        })
        regular_move = regular_picking.move_ids
        self._create_stock(self.product_storable, 1, donation_picking.location_id)
        self._create_stock(self.product_storable, 1, regular_move.location_id)
        moves = donation_picking.move_ids | regular_move
        for move in moves:
            move._action_confirm()
            move._action_assign()
            move.write({"quantity": 1, "picked": True})
        moves._action_done()

        donation_entry = donation_picking.move_ids.account_move_id
        regular_entry = regular_move.account_move_id
        self.assertTrue(donation_entry.is_donation)
        self.assertTrue(regular_entry)
        self.assertFalse(regular_entry.is_donation)
        self.assertNotEqual(donation_entry, regular_entry)

    def test_08b_leaked_default_is_donation_does_not_mark_a_regular_entry(self):
        """A `default_is_donation` in the context (e.g. from an action of
        another module) must not mark the valuation entry of a delivery
        that is not a donation (here, one that goes to the inventory loss
        location, so that it does generate an entry)."""
        picking = self._create_donation_picking(reason="Medication")
        picking.is_donation = False
        self._create_stock(self.product_storable, 1, picking.location_id)
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({"quantity": 1, "picked": True})
        picking.with_context(default_is_donation=True).button_validate()
        self.assertEqual(picking.state, "done")
        entries = picking.move_ids.account_move_id
        self.assertTrue(entries, "The delivery must generate a valuation entry.")
        self.assertFalse(entries.filtered("is_donation"))

    def test_08c_leaked_default_is_donation_keeps_the_donation_entry(self):
        picking = self._create_donation_picking(reason="Medication", validate=False)
        self._create_stock(self.product_storable, 1, picking.location_id)
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({"quantity": 1, "picked": True})
        picking.with_context(default_is_donation=True).button_validate()
        self.assertTrue(self._entry(picking).is_donation)

    def test_09_receipt_and_sale_pickings_are_not_donation_deliveries(self):
        receipt_type = self.env["stock.picking.type"].create({
            "name": "Donation Receipt Move Test",
            "code": "incoming",
            "sequence_code": "TDONRCV3",
            "warehouse_id": self.warehouse_donation.id,
            "company_id": self.company.id,
            "is_donation_picking_type": True,
        })
        receipt = self.env["stock.picking"].create({
            "picking_type_id": receipt_type.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": self.warehouse_donation.lot_stock_id.id,
            "is_donation": True,
            "move_ids": [Command.create({
                "product_id": self.product_storable.id,
                "product_uom_qty": 1,
                "product_uom": self.product_storable.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.warehouse_donation.lot_stock_id.id,
            })],
        })
        self.assertFalse(receipt.move_ids._is_donation_delivery_move())

        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_donation": True,
            "order_line": [Command.create({
                "product_id": self.product_storable.id,
                "product_uom_qty": 1,
                "price_unit": 10.0,
            })],
        })
        delivery_of_sale = self._create_donation_picking()
        delivery_of_sale.sale_id = order
        self.assertFalse(delivery_of_sale.move_ids._is_donation_delivery_move())

    def test_10_valuation_entry_has_no_donation_certificate(self):
        """The valuation entry of a donation delivery is marked as donation
        but its certificate is the delivery certificate of the picking: the
        entry certificate is refused and points to the picking."""
        picking = self._create_donation_picking(reason="Medication", validate=True)
        entry = self._entry(picking)
        self.assertTrue(entry.is_donation)
        self.assertTrue(entry.is_stock_valuation_entry)
        with self.assertRaises(UserError) as error:
            entry.print_donation_certificate()
        self.assertIn(picking.name, error.exception.args[0])
        # The picking does have its own certificate.
        self.assertIsInstance(picking.print_donation_certificate(), dict)
