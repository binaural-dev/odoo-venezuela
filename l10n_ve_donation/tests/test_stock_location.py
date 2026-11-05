from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from .common import TestDonationCommon


@tagged('l10n_ve_donation', 'stock_location', '-at_install', 'post_install')
class TestStockLocation(TestDonationCommon):
    """The destination of a donation delivery operation type determines the
    accounts of the delivery entries: it cannot be left incoherent, and a new
    `inventory` location of the donation warehouse starts with the company
    donation account."""

    def _create_location(self, warehouse, **vals):
        return self.env["stock.location"].create({
            "name": "Location Test",
            "location_id": warehouse.view_location_id.id,
            **vals,
        })

    def test_01_donation_destination_account_is_not_required_by_the_constraint(self):
        """The incoming account of the destination of a donation delivery
        type can be emptied: it is only required by the delivery validation."""
        location = self.location_donation
        self.assertEqual(location, self.picking_type_donation.default_location_dest_id)
        location.valuation_in_account_id = False
        self.assertFalse(location.valuation_in_account_id)

    def test_02_donation_destination_cannot_change_usage(self):
        with self.assertRaises(ValidationError):
            self.location_donation.usage = "internal"
        self.assertEqual(self.location_donation.usage, "inventory")

    def test_03_donation_destination_can_change_account(self):
        """Another account is allowed: only structural checks, no account type."""
        self.location_donation.valuation_in_account_id = self.account_income
        self.assertEqual(self.location_donation.valuation_in_account_id, self.account_income)

    def test_04_other_locations_are_free(self):
        """Locations that are not the destination of a donation delivery type,
        or whose type is not a donation one, keep the standard behavior."""
        location = self._create_location(
            self.warehouse_donation, usage="inventory", valuation_in_account_id=False
        )
        location.usage = "internal"
        self.assertEqual(location.usage, "internal")

        plain_type = self.env["stock.picking.type"].create({
            "name": "Plain Delivery Location Test",
            "code": "outgoing",
            "sequence_code": "PLNLOC",
            "warehouse_id": self.warehouse_normal.id,
            "default_location_dest_id": location.id,
        })
        self.assertFalse(plain_type.is_donation_picking_type)
        location.write({"usage": "inventory", "valuation_in_account_id": False})
        self.assertFalse(location.valuation_in_account_id)

    def test_05_initial_account_in_donation_warehouse(self):
        """A new `inventory` location of the donation warehouse proposes the
        company donation account."""
        self.assertEqual(self.company.donation_account_id, self.account_expense)
        location = self._create_location(self.warehouse_donation, usage="inventory")
        self.assertEqual(location.valuation_in_account_id, self.account_expense)
        # also under the stock location (a child of the view location)
        child = self.env["stock.location"].create({
            "name": "Child Inventory Loss",
            "usage": "inventory",
            "location_id": self.warehouse_donation.lot_stock_id.id,
        })
        self.assertEqual(child.valuation_in_account_id, self.account_expense)

    def test_06_initial_account_is_not_forced(self):
        """An explicit account (or an explicit empty one) is respected."""
        location = self._create_location(
            self.warehouse_donation, usage="inventory", valuation_in_account_id=self.account_income.id
        )
        self.assertEqual(location.valuation_in_account_id, self.account_income)
        location = self._create_location(
            self.warehouse_donation, usage="inventory", valuation_in_account_id=False
        )
        self.assertFalse(location.valuation_in_account_id)

    def test_07_no_initial_account_outside_the_donation_case(self):
        """Neither other usages, nor other warehouses, nor a company without
        donation account get a proposal."""
        self.assertFalse(
            self._create_location(self.warehouse_donation, usage="internal").valuation_in_account_id
        )
        self.assertFalse(
            self._create_location(self.warehouse_normal, usage="inventory").valuation_in_account_id
        )
        self.company.donation_account_id = False
        self.assertFalse(
            self._create_location(self.warehouse_donation, usage="inventory").valuation_in_account_id
        )

    def test_08_default_usage_from_context(self):
        """The usage can come from the default of the context."""
        location = self.env["stock.location"].with_context(default_usage="inventory").create({
            "name": "Default Usage Inventory Loss",
            "location_id": self.warehouse_donation.view_location_id.id,
        })
        self.assertEqual(location.valuation_in_account_id, self.account_expense)

    def test_09_context_default_account_is_respected(self):
        """A `default_valuation_in_account_id` in the context skips the
        proposal."""
        location = self.env["stock.location"].with_context(
            default_valuation_in_account_id=self.account_income.id
        ).create({
            "name": "Context Default Account",
            "usage": "inventory",
            "location_id": self.warehouse_donation.view_location_id.id,
        })
        self.assertEqual(location.valuation_in_account_id, self.account_income)
        location = self.env["stock.location"].with_context(
            default_valuation_in_account_id=False
        ).create({
            "name": "Context Default Empty Account",
            "usage": "inventory",
            "location_id": self.warehouse_donation.view_location_id.id,
        })
        self.assertFalse(location.valuation_in_account_id)

    def test_10_initial_account_comes_from_the_company_of_the_warehouse(self):
        """With several companies, the proposed account is the donation
        account of the company of the warehouse."""
        company_b = self.env["res.company"].create({"name": "Company B Donation"})
        account_b = self.env["account.account"].create({
            "name": "Donation Expense B",
            "code": "610002",
            "account_type": "expense",
            "company_id": company_b.id,
        })
        company_b.donation_account_id = account_b
        warehouse_b = self.env["stock.warehouse"].create({
            "name": "Donation Warehouse B",
            "code": "DWHB",
            "company_id": company_b.id,
            "is_donation_warehouse": True,
        })
        location_b = self.env["stock.location"].create({
            "name": "Inventory Loss B",
            "usage": "inventory",
            "company_id": company_b.id,
            "location_id": warehouse_b.view_location_id.id,
        })
        self.assertEqual(location_b.valuation_in_account_id, account_b)
        location_a = self._create_location(self.warehouse_donation, usage="inventory")
        self.assertEqual(location_a.valuation_in_account_id, self.account_expense)

    def test_11_donation_type_can_point_to_inventory_location_without_account(self):
        """A donation delivery type can be pointed to an `inventory` location
        without account (the delivery validation covers it)."""
        location = self._create_location(
            self.warehouse_donation, usage="inventory", valuation_in_account_id=False
        )
        self.picking_type_donation.default_location_dest_id = location
        self.assertEqual(self.picking_type_donation.default_location_dest_id, location)

    def _new_location_form(self):
        # The accounting fields of the form need the automatic stock
        # accounting group (as in the standard stock_account tests).
        self.env.user.groups_id += self.env.ref("stock_account.group_stock_accounting_automatic")
        form = Form(self.env["stock.location"])
        form.name = "Onchange Location"
        return form

    def test_12_onchange_proposes_account_when_choosing_parent_and_usage(self):
        """In the form, the account is proposed when the location is
        `inventory` inside the donation warehouse, whichever of the parent
        and the usage is chosen last."""
        form = self._new_location_form()
        form.location_id = self.warehouse_donation.view_location_id
        self.assertFalse(form.valuation_in_account_id)  # still internal
        form.usage = "inventory"
        self.assertEqual(form.valuation_in_account_id, self.account_expense)
        location = form.save()
        self.assertEqual(location.valuation_in_account_id, self.account_expense)

        form = self._new_location_form()
        form.usage = "inventory"
        form.location_id = self.warehouse_normal.view_location_id
        self.assertFalse(form.valuation_in_account_id)
        form.location_id = self.warehouse_donation.view_location_id
        self.assertEqual(form.valuation_in_account_id, self.account_expense)

    def test_13_onchange_does_not_overwrite_an_account(self):
        """An account already set is kept when the parent or the usage change."""
        form = self._new_location_form()
        form.usage = "inventory"
        form.location_id = self.warehouse_normal.view_location_id
        form.valuation_in_account_id = self.account_income
        form.location_id = self.warehouse_donation.view_location_id
        self.assertEqual(form.valuation_in_account_id, self.account_income)
        location = form.save()
        self.assertEqual(location.valuation_in_account_id, self.account_income)
