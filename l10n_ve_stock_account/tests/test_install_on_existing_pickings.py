# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.l10n_ve_stock_account import fill_historical_transfer_reasons

from .common import StockAccountTestCommon


@tagged("post_install", "-at_install", "test_install_on_existing_pickings")
class TestInstallOnExistingPickings(StockAccountTestCommon):
    """Installing the module on a database that already has pickings.

    On install, _compute_allowed_reason_ids runs on every existing picking before
    data/transfer_reason.xml is loaded; post_init_hook then fills the historical reasons.
    """

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
            {"name": "Internal Dest 91873", "usage": "internal", "location_id": cls.src.id}
        )
        cls.customer = cls.env.ref("stock.stock_location_customers")
        cls.consignation_warehouse = cls.env["stock.warehouse"].create(
            {"name": "Consignation 91873", "code": "C9187", "company_id": cls.company.id}
        )
        cls.consignation_warehouse.is_consignation_warehouse = True
        cls.partner = cls.env["res.partner"].create({"name": "Customer 91873"})
        cls.company.internal_transfer_reason_id = False

        ref = cls.env.ref
        cls.reason_between_wh = ref(
            "l10n_ve_stock_account.transfer_reason_transfer_between_warehouses"
        )
        cls.reason_consignment = ref("l10n_ve_stock_account.transfer_reason_consignment")
        cls.reason_other = ref("l10n_ve_stock_account.transfer_reason_other_causes")
        cls.reason_sale = ref("l10n_ve_stock_account.transfer_reason_sale")
        cls.reason_self_consumption = ref(
            "l10n_ve_stock_account.transfer_reason_self_consumption"
        )

    def _picking(self, picking_type, dest, **extra):
        return self.Picking.create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.src.id,
                "location_dest_id": dest.id,
                "company_id": self.company.id,
                **extra,
            }
        )

    def _clear_reason(self, pickings):
        """Leave the pickings as the install leaves them: no reason, nothing that follows from it."""
        self.env.flush_all()
        self.env.cr.execute(
            """
            UPDATE stock_picking
               SET transfer_reason_id = NULL, is_consignment = false, is_dispatch_guide = false,
                   is_transfer_between_warehouses = false, is_consignment_readonly = false
             WHERE id IN %s
            """,
            [tuple(pickings.ids)],
        )
        field = self.Picking._fields["allowed_reason_ids"]
        self.env.cr.execute(
            f'DELETE FROM "{field.relation}" WHERE "{field.column1}" IN %s', [tuple(pickings.ids)]
        )
        self.env.invalidate_all()

    def test_compute_without_reasons_does_not_write_an_empty_reason(self):
        """Before transfer_reason.xml is loaded, an internal picking must not abort the install."""
        self.env.cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE module = 'l10n_ve_stock_account' AND model = 'transfer.reason'
            """
        )
        self.env.registry.clear_cache()
        self.assertFalse(
            self.env.ref(
                "l10n_ve_stock_account.transfer_reason_transfer_between_warehouses",
                raise_if_not_found=False,
            )
        )

        picking = self._picking(self.internal_type, self.dest)

        self.assertFalse(picking.transfer_reason_id)
        # Without known reasons the compute offers every transfer.reason (none at install time).
        self.assertEqual(picking.allowed_reason_ids, self.env["transfer.reason"].search([]))

    def test_hook_fills_internal_pickings(self):
        internal = self._picking(self.internal_type, self.dest)
        consignation = self._picking(
            self.internal_type, self.consignation_warehouse.lot_stock_id
        )
        self._clear_reason(internal | consignation)

        fill_historical_transfer_reasons(self.env)

        self.assertEqual(internal.transfer_reason_id, self.reason_between_wh)
        self.assertIn(self.reason_between_wh, internal.allowed_reason_ids)
        self.assertTrue(internal.is_transfer_between_warehouses)
        self.assertEqual(consignation.transfer_reason_id, self.reason_consignment)
        self.assertTrue(consignation.is_consignment)
        self.assertTrue(consignation.is_consignment_readonly)
        self.assertTrue(consignation.is_dispatch_guide)

    def test_hook_does_not_write_on_each_picking(self):
        """The historical pickings are filled by SQL: no write() override, no tracking message."""
        internal = self._picking(self.internal_type, self.dest)
        consignation = self._picking(
            self.internal_type, self.consignation_warehouse.lot_stock_id
        )
        self._clear_reason(internal | consignation)
        Picking = type(self.Picking)

        with patch.object(Picking, "write", autospec=True, side_effect=Picking.write) as write:
            fill_historical_transfer_reasons(self.env)

        self.assertFalse(write.call_count)
        self.assertEqual(consignation.transfer_reason_id, self.reason_consignment)

    def test_hook_uses_the_company_default_reason(self):
        self.company.internal_transfer_reason_id = self.reason_other
        internal = self._picking(self.internal_type, self.dest)
        self._clear_reason(internal)

        fill_historical_transfer_reasons(self.env)

        self.assertEqual(internal.transfer_reason_id, self.reason_other)

    def test_hook_fills_outgoing_pickings(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        with_sale = self._picking(self.outgoing_type, self.customer)
        without_sale = self._picking(self.outgoing_type, self.customer)
        self.env.cr.execute(
            "UPDATE stock_picking SET sale_id = %s WHERE id = %s", [order.id, with_sale.id]
        )
        with_sale.invalidate_recordset(["sale_id"])
        self._clear_reason(with_sale | without_sale)

        fill_historical_transfer_reasons(self.env)

        self.assertEqual(with_sale.transfer_reason_id, self.reason_sale)
        self.assertEqual(without_sale.transfer_reason_id, self.reason_self_consumption)

    def test_hook_keeps_existing_reasons(self):
        internal = self._picking(self.internal_type, self.dest)
        internal.transfer_reason_id = self.reason_other

        fill_historical_transfer_reasons(self.env)

        self.assertEqual(internal.transfer_reason_id, self.reason_other)
