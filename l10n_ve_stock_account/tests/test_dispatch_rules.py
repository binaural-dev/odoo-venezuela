from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from .common import StockAccountCommon

PICKING_MODULE = "odoo.addons.l10n_ve_stock_account.models.stock_picking"


def _fake_date(today):
    class FakeDate(date):
        @classmethod
        def today(cls):
            return today

    return FakeDate


@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestDispatchRules(StockAccountCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.warehouse.lot_stock_id, 100)

    def _reason(self, xmlid):
        return self.env.ref(f"l10n_ve_stock_account.{xmlid}")

    def _validate(self, picking):
        picking.action_confirm()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()
        return picking

    def test_allowed_reasons_by_operation(self):
        outgoing = self.create_picking()
        self.assertIn(self._reason("transfer_reason_self_consumption"), outgoing.allowed_reason_ids)
        self.assertNotIn(self._reason("transfer_reason_sale"), outgoing.allowed_reason_ids)

        order = self.create_sale_order()
        order.action_confirm()
        sale_picking = order.picking_ids
        sale_picking._compute_allowed_reason_ids()
        self.assertEqual(sale_picking.transfer_reason_id, self._reason("transfer_reason_sale"))
        self.assertIn(self._reason("transfer_reason_export"), sale_picking.allowed_reason_ids)

        internal = self.create_picking("transfer", operation_code="internal")
        self.assertIn(self._reason("transfer_reason_consignment"), internal.allowed_reason_ids)
        self.assertFalse(internal.is_consignment_readonly)

        incoming = self.create_picking(operation_code="incoming")
        self.assertEqual(incoming.allowed_reason_ids, self.env["transfer.reason"].search([]))

    def test_donation_and_subcontracting_sales(self):
        order = self.create_sale_order()
        order.is_donation = True
        order.action_confirm()
        order.picking_ids._compute_allowed_reason_ids()
        self.assertEqual(order.picking_ids.transfer_reason_id, self._reason("transfer_reason_donation"))

        self.company.is_subcontracting = True
        order = self.create_sale_order()
        order.is_subcontracting = True
        order.action_confirm()
        order.picking_ids._compute_allowed_reason_ids()
        self.assertEqual(order.picking_ids.allowed_reason_ids, self._reason("transfer_reason_subcontracting"))

    def test_internal_transfer_requires_reason(self):
        with self.assertRaises(ValidationError):
            self.create_picking(operation_code="internal")

    def test_reason_flags(self):
        picking = self.create_picking("other_causes")
        self.assertTrue(picking.show_other_causes_transfer_reason)
        self.assertTrue(picking.is_dispatch_guide)

        picking.transfer_reason_id = self._reason("transfer_reason_repair")
        self.assertFalse(picking.show_other_causes_transfer_reason)

        self.company.optional_internal_movement_guidance = True
        internal = self.create_picking("transfer", operation_code="internal")
        self.assertTrue(internal.reasons_optional_guide_dispatch)

        consignment = self.create_picking("consignment", operation_code="internal")
        self.assertTrue(consignment.is_consignment)

    def test_invoice_document_disables_dispatch_guide(self):
        order = self.create_sale_order()
        order.document = "invoice"
        order.action_confirm()
        picking = order.picking_ids
        self.assertFalse(picking.is_dispatch_guide)
        self.assertTrue(picking.has_document)

        self._validate(picking)
        self.assertFalse(picking.dispatch_guide_controls)
        self.assertFalse(picking.guide_number)

    def test_guide_sequence_is_created_per_company(self):
        self.env["ir.sequence"].sudo().search(
            [("code", "=", "guide.number"), ("company_id", "=", self.company.id)]
        ).unlink()
        picking = self._validate(self.create_picking())

        self.assertTrue(picking.guide_number.startswith("GUIDE"))
        self.assertTrue(picking.match_guide_dispatch_domain)

    def test_return_types(self):
        picking = self._validate(self.create_picking())
        self.assertEqual(picking.type_of_return, "n/a")

        def return_qty(qty):
            wizard = Form(
                self.env["stock.return.picking"].with_context(active_id=picking.id, active_model="stock.picking")
            ).save()
            wizard.product_return_moves.quantity = qty
            returned = self.env["stock.picking"].browse(wizard.create_returns()["res_id"])
            self.assertTrue(returned.is_return)
            self.assertFalse(returned.is_dispatch_guide)
            return self._validate(returned)

        partial = return_qty(4)
        self.assertEqual(picking.move_ids.qty_return, 4)
        self.assertEqual(picking.type_of_return, "partial")
        self.assertFalse(partial.guide_number)

        return_qty(6)
        self.assertEqual(picking.type_of_return, "total")
        self.assertFalse(picking.match_guide_dispatch_domain)

    def test_execution_day_and_time(self):
        Picking = self.env["stock.picking"]
        with patch.object(fields.Date, "context_today", return_value=date(2026, 10, 31)):
            self.assertTrue(Picking._is_execution_day("last_day"))
            self.assertFalse(Picking._is_execution_day("last_business_day"))
        with patch.object(fields.Date, "context_today", return_value=date(2026, 10, 30)):
            self.assertTrue(Picking._is_execution_day("last_business_day"))

        class FakeNow:
            hour = 18
            minute = 15

        with patch(f"{PICKING_MODULE}.datetime") as mocked:
            mocked.now.return_value = FakeNow
            self.assertTrue(Picking._is_execution_time(18.0))
            self.assertFalse(Picking._is_execution_time(10.0))

    def test_cron_invoices_pending_pickings(self):
        picking = self._validate(self.create_picking())
        Picking = self.env["stock.picking"]

        with patch.object(type(Picking), "_is_execution_day", return_value=False):
            Picking._cron_generate_invoices_from_pickings()
        self.assertEqual(picking.invoice_count, 0)

        with patch.object(type(Picking), "_is_execution_day", return_value=True), patch.object(
            type(Picking), "_is_execution_time", return_value=True
        ):
            Picking._cron_generate_invoices_from_pickings()
        picking.invalidate_recordset()
        self.assertEqual(picking.invoice_count, 1)
        self.assertEqual(picking.state_guide_dispatch, "invoiced")

    def test_cron_logs_errors(self):
        picking = self._validate(self.create_picking())
        self.company.customer_journal_id = False

        with self.assertLogs(PICKING_MODULE, level="ERROR"):
            self.env["stock.picking"]._create_invoices_from_pickings()

        self.assertIn("Error", picking.message_ids[0].body)

    def test_pending_guides_alert(self):
        self._validate(self.create_picking())
        company_ids = str(self.company.id)
        Picking = self.env["stock.picking"]

        self.company.taxpayer_type = "special"
        with patch(f"{PICKING_MODULE}.date", _fake_date(date(2026, 10, 10))):
            self.assertIn("15-10-2026", Picking.alert_views(company_ids))
        with patch(f"{PICKING_MODULE}.date", _fake_date(date(2026, 10, 20))):
            self.assertIn("31-10-2026", Picking.alert_views(company_ids))

        self.company.taxpayer_type = "ordinary"
        with patch(f"{PICKING_MODULE}.date", _fake_date(date(2026, 2, 3))):
            message = Picking.alert_views(company_ids)
        self.assertIn("28-02-2026", message)
        self.assertIn("guías de despacho sin facturar", message)

        self.assertIsNone(Picking.with_user(self.user_restricted).alert_views(company_ids))

    def test_internal_between_warehouses_is_emited(self):
        picking = self.create_picking("transfer", operation_code="internal")
        self._validate(picking)
        self.assertEqual(picking.state_guide_dispatch, "emited")

    def test_self_consumption_wizard(self):
        picking = self.create_picking("self_consumption")
        picking.action_confirm()
        picking.move_ids.quantity = picking.move_ids.product_uom_qty
        picking.move_ids.picked = True
        wizard = self.env["stock.picking.self.consumption.wizard"].create({"picking_id": picking.id})

        self.assertEqual(wizard.action_cancel()["type"], "ir.actions.act_window_close")
        wizard.action_confirm()
        self.assertEqual(picking.state, "done")

    def test_main_partner(self):
        contact = self.env["res.partner"].create({"name": "Contacto", "parent_id": self.partner.id})
        self.assertEqual(contact._get_main_partner(), self.partner)
        self.assertEqual(self.partner._get_main_partner(), self.partner)
        self.assertFalse(self.env["res.partner"]._get_main_partner())
