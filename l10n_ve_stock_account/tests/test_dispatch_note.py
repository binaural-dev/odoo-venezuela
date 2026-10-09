# -*- coding: utf-8 -*-
from lxml import etree

from odoo.tests import tagged

from .common import StockAccountTestCommon


@tagged("post_install", "-at_install", "test_dispatch_note")
class TestDispatchNote(StockAccountTestCommon):
    """Reporte Nota de Despacho, botón por grupo y toggle de ajustes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref("l10n_ve_stock_account.group_dispatch_note_print")
        cls.report = cls.env.ref("l10n_ve_stock_account.action_dispatch_note")
        wh = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.warehouse = wh
        cls.product = cls.env["product.product"].create(
            {"name": "Dispatch Note Product", "type": "consu", "is_storable": True}
        )
        cls.customer = cls.env["res.partner"].create({"name": "Dispatch Note Customer"})

    def _internal_picking(self):
        dest = self.env["stock.location"].create(
            {"name": "DN Dest", "usage": "internal", "location_id": self.warehouse.lot_stock_id.id}
        )
        return self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.int_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": dest.id,
            "move_ids": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 3,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": dest.id,
            })],
        })

    def _render(self, picking):
        html, _ = self.report._render_qweb_html(self.report.report_name, picking.ids)
        return html.decode()

    def test_report_paperformat_not_default(self):
        paperformat = self.env.ref("l10n_ve_stock_account.dispatch_note_paperformat")
        self.assertEqual(self.report.paperformat_id, paperformat)
        self.assertFalse(paperformat.default)

    def test_render_internal_picking(self):
        picking = self._internal_picking()
        html = self._render(picking)
        self.assertIn(picking.name, html)
        self.assertIn("Dispatch Note Product", html)
        self.assertIn("Desde:", html)
        self.assertNotIn("Despacho de Factura", html)

    def test_render_outgoing_picking_with_invoiced_sale(self):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 2})],
        })
        order.action_confirm()
        picking = order.picking_ids
        self.assertEqual(picking.picking_type_code, "outgoing")
        invoice = order._create_invoices()
        # Numero explicito: en el entorno de pruebas la factura publicada
        # puede quedar como "/" (sin serie), que la nota no debe mostrar.
        invoice.name = "INV/TEST/73452-1"
        # Sin este contexto l10n_ve_accountant devuelve el asistente de
        # confirmacion y la factura queda en borrador.
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.name, "INV/TEST/73452-1")
        self.assertEqual(picking.dispatch_note_invoice_names, invoice.name)
        html = self._render(picking)
        self.assertIn("Despacho de Factura", html)
        self.assertIn(invoice.name, html)

    def test_draft_invoice_and_refund_are_not_listed(self):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id,
            "order_line": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 2})],
        })
        order.action_confirm()
        picking = order.picking_ids
        draft = order._create_invoices()
        self.assertEqual(draft.state, "draft")
        self.assertFalse(picking.dispatch_note_invoice_names)
        draft.name = "INV/TEST/73452-2"
        draft.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(draft.state, "posted")
        refund = draft._reverse_moves()
        refund.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(refund.state, "posted")
        self.assertEqual(refund.move_type, "out_refund")
        self.assertEqual(picking.dispatch_note_invoice_names, draft.name)
        self.assertNotIn(refund.name, picking.dispatch_note_invoice_names)

    def test_outgoing_picking_without_sale_has_no_invoice(self):
        picking = self._internal_picking()
        self.assertFalse(picking.dispatch_note_invoice_names)

    def _button_visible_for(self, user):
        picking = self._internal_picking()
        view = picking.with_user(user).get_view(
            self.env.ref("stock.view_picking_form").id, "form"
        )
        arch = etree.fromstring(view["arch"])
        return bool(arch.xpath("//button[@string='Print Dispatch Note']"))

    def test_button_restricted_by_group(self):
        user = self.env["res.users"].create({
            "name": "DN User", "login": "dn_user_73452",
            "group_ids": [(6, 0, [self.env.ref("stock.group_stock_user").id])],
        })
        self.assertFalse(self._button_visible_for(user))
        user.group_ids = [(4, self.group.id)]
        self.assertTrue(self._button_visible_for(user))

    def test_settings_toggle_applies_and_removes_group(self):
        internal_group = self.env.ref("base.group_user")
        settings = self.env["res.config.settings"].create({"group_dispatch_note_print": True})
        settings.execute()
        self.assertTrue(self.company.group_dispatch_note_print)
        self.assertIn(self.group, internal_group.implied_ids)
        settings = self.env["res.config.settings"].create({"group_dispatch_note_print": False})
        settings.execute()
        self.assertFalse(self.company.group_dispatch_note_print)
        self.assertNotIn(self.group, internal_group.implied_ids)
