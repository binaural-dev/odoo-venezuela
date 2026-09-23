# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from odoo import Command


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationStockPicking(TransactionCase):
    """Coverage for the `is_donation` field and related overrides that
    `l10n_ve_donation` adds to `stock.picking` (moved here from
    `l10n_ve_stock_account` -- see that module's `test_stock_picking.py`)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.company_partner = cls.company.partner_id

        # `l10n_ve_accountant`'s tax-totals computation needs a foreign
        # currency configured on the company to resolve `currency_id` to a
        # singleton -- without it, a sale order line write triggers a
        # dual-currency compute that raises on an empty recordset.
        currency_usd = cls.env.ref("base.USD")
        currency_usd.active = True
        currency_vef = cls.env.ref("base.VEF")
        currency_vef.active = True
        cls.company.write({
            "currency_id": currency_vef.id,
            "foreign_currency_id": currency_usd.id,
        })

        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.sale_journal:
            cls.sale_journal = cls.env["account.journal"].create({
                "name": "Donation Sale Journal",
                "type": "sale",
                "code": "DONSJ",
                "company_id": cls.company.id,
            })
        cls.company.customer_journal_id = cls.sale_journal.id

        # `l10n_ve_accountant` requires every product to resolve exactly one
        # sale/purchase tax, either explicitly or via the company's default
        # fiscal configuration -- set the latter so the product below (with
        # taxes_id/supplier_taxes_id cleared) doesn't raise a
        # fiscal-inconsistency UserError.
        # `tax_group_id` has no usable default in a minimal database (no
        # fiscal localization data loaded) -- pass one explicitly to avoid a
        # NOT NULL violation.
        if not cls.company.account_sale_tax_id or not cls.company.account_purchase_tax_id:
            country_ve = cls.env.ref("base.ve")
            tax_group = cls.env["account.tax.group"].create({
                "name": "Donation Picking Test Tax Group",
                "country_id": country_ve.id,
            })
        if not cls.company.account_sale_tax_id:
            cls.company.account_sale_tax_id = cls.env["account.tax"].create({
                "name": "Donation Picking Test Sale Tax",
                "amount": 16,
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": tax_group.id,
                "country_id": country_ve.id,
            })
        if not cls.company.account_purchase_tax_id:
            cls.company.account_purchase_tax_id = cls.env["account.tax"].create({
                "name": "Donation Picking Test Purchase Tax",
                "amount": 16,
                "type_tax_use": "purchase",
                "company_id": cls.company.id,
                "tax_group_id": tax_group.id,
                "country_id": country_ve.id,
            })

        cls.income_account = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_ids", "in", cls.company.ids)],
            limit=1,
        ) or cls.env["account.account"].create({
            "name": "Donation Income Test",
            "code": "DONINC01",
            "account_type": "income",
            "company_ids": [Command.set([cls.company.id])],
        })

        # `create_invoice()` needs a receivable account on the invoice
        # partner (the company's own partner, for donations) to build the
        # payment-term line -- a minimal database has no default one.
        if not cls.company_partner.property_account_receivable_id:
            cls.receivable_account = cls.env["account.account"].search(
                [("account_type", "=", "asset_receivable"), ("company_ids", "in", cls.company.ids)],
                limit=1,
            ) or cls.env["account.account"].create({
                "name": "Donation Receivable Test",
                "code": "DONREC01",
                "account_type": "asset_receivable",
                "company_ids": [Command.set([cls.company.id])],
            })
            cls.company_partner.property_account_receivable_id = cls.receivable_account.id

        cls.partner = cls.env["res.partner"].create({"name": "Donation Test Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Donation Coverage Product",
            "type": "consu",
            "lst_price": 100.0,
            "property_account_income_id": cls.income_account.id,
            "taxes_id": [Command.clear()],
            "supplier_taxes_id": [Command.clear()],
        })

        cls.picking_type_internal = cls.env.ref("stock.picking_type_internal")
        cls.location_stock = cls.env.ref("stock.stock_location_stock")

        cls.reason_self_consumption = cls.env.ref(
            "l10n_ve_stock_account.transfer_reason_self_consumption"
        )

    # ── Helpers ──

    def _create_sale_order(self, is_donation=True, partner=None):
        partner = partner or self.company_partner
        so = self.env["sale.order"].create({
            "partner_id": partner.id,
            "document": "dispatch_guide",
            "is_donation": is_donation,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 100.0,
                "tax_ids": [Command.clear()],
            })],
        })
        return so

    def _create_outgoing_donation_picking(self, validate=True):
        # Built directly (not via sale.order.action_confirm()) to avoid the
        # procurement/stock-rule machinery, which needs warehouse routes
        # that don't exist in this minimal test database.
        so = self._create_sale_order(is_donation=True)
        picking_type_out = self.env.ref("stock.picking_type_out")
        location_customers = self.env.ref("stock.stock_location_customers")
        picking = self.env["stock.picking"].create({
            "partner_id": so.partner_id.id,
            "picking_type_id": picking_type_out.id,
            "location_id": self.location_stock.id,
            "location_dest_id": location_customers.id,
            "sale_id": so.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "location_id": self.location_stock.id,
                "location_dest_id": location_customers.id,
            })],
        })
        picking.action_confirm()
        if validate:
            picking.move_ids.write({"quantity": 1, "picked": True})
            picking.button_validate()
        return picking

    def _create_internal_picking(self):
        return self.env["stock.picking"].create({
            "picking_type_id": self.picking_type_internal.id,
            "location_id": self.location_stock.id,
            "location_dest_id": self.location_stock.id,
        })

    # ── _compute_is_donation ──

    def test_compute_is_donation_follows_sale_order(self):
        picking = self._create_outgoing_donation_picking(validate=False)
        self.assertTrue(picking.is_donation)

    def test_compute_is_donation_false_without_sale(self):
        picking = self._create_internal_picking()
        self.assertFalse(picking.is_donation)

    # ── onchange is_donation / partner_id ──

    def test_onchange_is_donation_sets_company_partner(self):
        picking = self._create_internal_picking()
        picking.is_donation = True
        picking.is_dispatch_guide = True
        picking._onchange_is_donation()
        self.assertEqual(picking.partner_id, self.company_partner)
        self.assertFalse(picking.is_dispatch_guide)

    def test_onchange_partner_id_donation_allows_company_partner(self):
        picking = self._create_internal_picking()
        picking.is_donation = True
        picking.partner_id = self.company_partner
        picking._onchange_partner_id_donation()  # should not raise

    def test_onchange_partner_id_donation_raises_for_other_partner(self):
        picking = self._create_internal_picking()
        picking.is_donation = True
        picking.partner_id = self.partner
        with self.assertRaises(UserError):
            picking._onchange_partner_id_donation()

    # ── _compute_picking_type_domain ──

    def test_compute_picking_type_domain_uses_native_domain_for_donation(self):
        # l10n_ve_donation no longer restricts the domain by
        # `is_donation_picking_type` -- no data ever sets that flag, which
        # used to leave donation pickings with an empty (unusable) domain.
        picking = self._create_internal_picking()
        picking.is_donation = True
        picking._compute_picking_type_domain()
        self.assertIn("internal", picking.picking_type_domain)

    # ── _compute_allowed_reason_ids ──

    def test_compute_allowed_reason_ids_forces_self_consumption(self):
        picking = self._create_outgoing_donation_picking(validate=False)
        picking._compute_allowed_reason_ids()
        self.assertEqual(picking.allowed_reason_ids, self.reason_self_consumption)
        self.assertEqual(picking.transfer_reason_id, self.reason_self_consumption)

    def test_compute_allowed_reason_ids_replaces_not_extends(self):
        # (6, 0, [id]) must replace whatever super() computed (e.g. the
        # "sale" reason for an outgoing picking with a sale order), not
        # add self-consumption on top of it.
        picking = self._create_outgoing_donation_picking(validate=False)
        picking._compute_allowed_reason_ids()
        self.assertNotIn(self.env.ref("l10n_ve_stock_account.transfer_reason_sale").id, picking.allowed_reason_ids.ids)

    # ── create_invoice ──

    def test_create_invoice_marks_invoice_as_donation(self):
        picking = self._create_outgoing_donation_picking(validate=True)
        invoice = picking.create_invoice()
        self.assertTrue(invoice)
        self.assertTrue(invoice.is_donation)

    def test_create_invoice_raises_on_multiple_pickings(self):
        picking_a = self._create_outgoing_donation_picking(validate=True)
        picking_b = self._create_outgoing_donation_picking(validate=True)
        with self.assertRaises(ValueError):
            (picking_a | picking_b).create_invoice()
