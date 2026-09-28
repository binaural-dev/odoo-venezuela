# -*- coding: utf-8 -*-
from lxml import etree

from odoo.tests import tagged

from .common import StockAccountTestCommon


@tagged("post_install", "-at_install", "test_default_internal_transfer_reason")
class TestDefaultInternalTransferReason(StockAccountTestCommon):
    """Default reason of internal transfers configured per company."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Picking = cls.env["stock.picking"]
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.internal_type = cls.warehouse.int_type_id
        cls.outgoing_type = cls.warehouse.out_type_id
        cls.src = cls.warehouse.lot_stock_id
        cls.dest = cls.env["stock.location"].create(
            {"name": "Internal Dest 73452", "usage": "internal", "location_id": cls.src.id}
        )
        cls.reason_between_wh = cls.env.ref(
            "l10n_ve_stock_account.transfer_reason_transfer_between_warehouses"
        )
        cls.reason_other = cls.env.ref("l10n_ve_stock_account.transfer_reason_other_causes")
        cls.reason_sale = cls.env.ref("l10n_ve_stock_account.transfer_reason_sale")

    def _skip_if_dispatch_note_installed(self):
        """binaural_stock_dispatch_note (integra-addons) applies its own unguarded default."""
        if self.env["ir.module.module"].search_count(
            [("name", "=", "binaural_stock_dispatch_note"), ("state", "=", "installed")]
        ):
            self.skipTest("binaural_stock_dispatch_note applies its own unguarded default")

    def _vals(self, picking_type, **extra):
        return {
            "picking_type_id": picking_type.id,
            "location_id": self.src.id,
            "location_dest_id": self.dest.id,
            "company_id": self.company.id,
            **extra,
        }

    def test_settings_field_is_persisted_on_company(self):
        settings = self.env["res.config.settings"].create(
            {"internal_transfer_reason_id": self.reason_other.id}
        )
        self.assertEqual(settings.internal_transfer_reason_id, self.reason_other)
        settings.execute()
        self.assertEqual(self.company.internal_transfer_reason_id, self.reason_other)

    def test_field_domain_matches_allowed_reasons_for_internal(self):
        """Selectable reasons are exactly those `_compute_allowed_reason_ids` allows for internals."""
        picking = self.Picking.create(self._vals(self.internal_type))
        allowed = picking.allowed_reason_ids
        domain = self.env["res.company"]._fields["internal_transfer_reason_id"].domain
        selectable = self.env["transfer.reason"].search(
            [("code", "in", ("consignment", "transfer", "other_causes"))]
        )
        self.assertTrue(domain)
        self.assertEqual(allowed, selectable)
        settings_domain = self.env["res.config.settings"]._fields[
            "internal_transfer_reason_id"
        ].domain
        self.assertEqual(domain, settings_domain)

    def test_internal_picking_defaults_reason_from_company(self):
        self.company.internal_transfer_reason_id = self.reason_between_wh
        picking = self.Picking.create(self._vals(self.internal_type))
        self.assertEqual(picking.transfer_reason_id, self.reason_between_wh)

    def test_internal_picking_reason_remains_editable(self):
        self.company.internal_transfer_reason_id = self.reason_between_wh
        picking = self.Picking.create(self._vals(self.internal_type))
        picking.transfer_reason_id = self.reason_other
        self.assertEqual(picking.transfer_reason_id, self.reason_other)

    def test_create_preserves_explicit_reason(self):
        self.company.internal_transfer_reason_id = self.reason_between_wh
        picking = self.Picking.create(
            self._vals(self.internal_type, transfer_reason_id=self.reason_other.id)
        )
        self.assertEqual(picking.transfer_reason_id, self.reason_other)

    def test_create_without_default_keeps_existing_behavior(self):
        self.company.internal_transfer_reason_id = False
        picking = self.Picking.create(self._vals(self.internal_type))
        self.assertFalse(picking.transfer_reason_id)

    def test_non_internal_picking_ignores_default(self):
        self.company.internal_transfer_reason_id = self.reason_between_wh
        picking = self.Picking.create(self._vals(self.outgoing_type))
        self.assertFalse(picking.transfer_reason_id)

    def test_default_not_allowed_for_internal_is_ignored(self):
        """A reason not allowed for internals (e.g. stored by another module) is never applied."""
        self._skip_if_dispatch_note_installed()
        self.company.internal_transfer_reason_id = self.reason_sale
        picking = self.Picking.create(self._vals(self.internal_type))
        self.assertFalse(picking.transfer_reason_id)
        new = self.Picking.new(
            {"picking_type_id": self.internal_type.id, "company_id": self.company.id}
        )
        new._onchange_picking_type_id_default_internal_transfer_reason()
        self.assertFalse(new.transfer_reason_id)

    def test_consignation_destination_does_not_get_default(self):
        """Consignation warehouses keep their own (consignment) reason logic."""
        self._skip_if_dispatch_note_installed()
        partner = self.company.partner_id
        self.warehouse.lot_stock_id.partner_id = partner
        self.warehouse.is_consignation_warehouse = True
        dest = self.env["stock.location"].create(
            {
                "name": "Consignation Dest 73452",
                "usage": "internal",
                "location_id": self.src.id,
                "partner_id": partner.id,
            }
        )
        self.company.internal_transfer_reason_id = self.reason_between_wh
        picking = self.Picking.create(
            self._vals(self.internal_type, location_dest_id=dest.id)
        )
        self.assertNotEqual(picking.transfer_reason_id, self.reason_between_wh)

    def test_create_uses_picking_type_company_fallback(self):
        other_company = self.env["res.company"].create({"name": "Fallback Company 73452"})
        other_wh = self.env["stock.warehouse"].search(
            [("company_id", "=", other_company.id)], limit=1
        )
        other_company.internal_transfer_reason_id = self.reason_other
        dest = self.env["stock.location"].create(
            {
                "name": "Fallback Dest",
                "usage": "internal",
                "location_id": other_wh.lot_stock_id.id,
                "company_id": other_company.id,
            }
        )
        picking = self.Picking.create(
            {
                "picking_type_id": other_wh.int_type_id.id,
                "location_id": other_wh.lot_stock_id.id,
                "location_dest_id": dest.id,
            }
        )
        self.assertEqual(picking.transfer_reason_id, self.reason_other)

    def test_onchange_sets_reason_for_internal_without_reason(self):
        self.company.internal_transfer_reason_id = self.reason_between_wh
        picking = self.Picking.new(
            {
                "picking_type_id": self.internal_type.id,
                "company_id": self.company.id,
                "location_id": self.src.id,
                "location_dest_id": self.dest.id,
            }
        )
        picking._onchange_picking_type_id_default_internal_transfer_reason()
        # the existing compute of allowed reasons must not discard the default
        self.assertIn(self.reason_between_wh.id, picking.allowed_reason_ids._origin.ids)
        self.assertEqual(picking.transfer_reason_id, self.reason_between_wh)

    def test_onchange_is_idempotent_and_keeps_existing_reason(self):
        self.company.internal_transfer_reason_id = self.reason_between_wh
        picking = self.Picking.new(
            {
                "picking_type_id": self.internal_type.id,
                "company_id": self.company.id,
                "transfer_reason_id": self.reason_other.id,
            }
        )
        picking._onchange_picking_type_id_default_internal_transfer_reason()
        picking._onchange_picking_type_id_default_internal_transfer_reason()
        self.assertEqual(picking.transfer_reason_id, self.reason_other)

    def test_onchange_skips_non_internal(self):
        self.company.internal_transfer_reason_id = self.reason_between_wh
        picking = self.Picking.new(
            {"picking_type_id": self.outgoing_type.id, "company_id": self.company.id}
        )
        picking._onchange_picking_type_id_default_internal_transfer_reason()
        self.assertFalse(picking.transfer_reason_id)

    def test_settings_view_has_field_and_heading(self):
        info = self.env["res.config.settings"].get_view(view_type="form")
        doc = etree.fromstring(info["arch"])
        self.assertTrue(doc.xpath("//field[@name='internal_transfer_reason_id']"))
        self.assertTrue(
            doc.xpath(
                "//div[@id='l10n_ve_settings_hide_weight_field_dispatch_guide']"
            )
        )
        self.assertTrue(doc.xpath("//h2[contains(., 'Dispatch Guide Settings')]"))
