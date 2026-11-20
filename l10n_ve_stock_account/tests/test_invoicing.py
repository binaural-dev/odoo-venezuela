from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from .common import StockAccountCommon


@tagged("post_install", "-at_install", "l10n_ve_stock_account")
class TestPickingInvoicing(StockAccountCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor_journal = cls.env["account.journal"].create(
            {"name": "Diario de compras", "code": "COMP", "type": "purchase", "company_id": cls.company.id}
        )
        cls.company.vendor_journal_id = cls.vendor_journal
        cls.product_2 = cls.env["product.product"].create(
            {
                "name": "Producto Prueba 2",
                "type": "product",
                "list_price": 50,
                "taxes_id": [(6, 0, cls.tax_iva16.ids)],
            }
        )
        cls.stock_location = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        ).lot_stock_id
        for product in (cls.product, cls.product_2):
            cls.env["stock.quant"]._update_available_quantity(product, cls.stock_location, 100)

    def _validate(self, picking):
        picking.action_confirm()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.button_validate()
        return picking

    def _picking(self, operation_code="outgoing", products=None):
        picking = self.create_picking(operation_code=operation_code)
        for product in products or []:
            self.env["stock.move"].create(
                {
                    "name": product.name,
                    "product_id": product.id,
                    "product_uom_qty": 3,
                    "product_uom": product.uom_id.id,
                    "picking_id": picking.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                }
            )
        return picking

    def test_invoice_lines_include_every_move(self):
        picking = self._validate(self._picking(products=self.product_2))

        lines = picking._get_invoice_lines_for_invoice(from_picking_line=True)

        self.assertEqual(len(lines), 2)
        self.assertEqual({vals["product_id"] for _c, _i, vals in lines}, {self.product.id, self.product_2.id})
        self.assertTrue(all(vals["from_picking_line"] for _c, _i, vals in lines))

    def test_invoice_requires_sale_price(self):
        picking = self._validate(self._picking())
        self.product.product_tmpl_id.with_context(install_mode=True).list_price = 0
        with self.assertRaises(UserError):
            picking._get_invoice_lines_for_invoice()

    def test_invoice_requires_customer_journal(self):
        picking = self._validate(self._picking())
        self.company.customer_journal_id = False
        with self.assertRaises(UserError):
            picking.create_invoice()

    def test_posted_invoice_blocks_new_invoice(self):
        picking = self._validate(self._picking())
        invoice = picking.create_invoice()
        invoice.with_context(move_action_post_alert=True).action_post()
        self.assertEqual(invoice.state, "posted")

        with self.assertRaises(UserError):
            picking.create_invoice()

    def test_customer_credit_from_incoming_picking(self):
        picking = self._validate(self._picking("incoming", products=self.product_2))

        credit = picking.create_customer_credit()

        self.assertEqual(credit.move_type, "out_refund")
        self.assertEqual(len(credit), 1)
        self.assertEqual(len(credit.invoice_line_ids), 2)
        self.assertEqual(credit.picking_ids, picking)
        self.assertTrue(credit.from_picking)
        self.assertTrue(all(credit.invoice_line_ids.mapped("from_picking_line")))
        self.assertEqual(picking.state_guide_dispatch, "invoiced")

    def test_vendor_documents_from_pickings(self):
        incoming = self._validate(self._picking("incoming"))
        bill = incoming.create_bill()
        incoming.invalidate_recordset()
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertEqual(bill.journal_id, self.vendor_journal)
        self.assertEqual(incoming.invoice_ids, bill)
        self.assertEqual(incoming.invoice_count, 1)
        self.assertEqual(incoming.invoice_state, "draft")

        outgoing = self._validate(self._picking("outgoing"))
        refund = outgoing.create_vendor_credit()
        self.assertEqual(refund.move_type, "in_refund")
        self.assertEqual(refund.picking_ids, outgoing)

    def test_vendor_documents_require_journal(self):
        incoming = self._validate(self._picking("incoming"))
        outgoing = self._validate(self._picking("outgoing"))
        self.company.vendor_journal_id = False

        self.assertFalse(outgoing.create_bill())
        with self.assertRaises(UserError):
            incoming.create_bill()

    def test_multi_invoice_groups_products(self):
        first = self._validate(self._picking())
        second = self._validate(self._picking())

        invoice = first.create_multi_invoice(first | second)

        self.assertEqual(len(invoice.invoice_line_ids), 1)
        self.assertEqual(invoice.invoice_line_ids.quantity, 20)
        self.assertEqual(invoice.transfer_ids, first | second)
        self.assertEqual({first.state_guide_dispatch, second.state_guide_dispatch}, {"invoiced"})

        self.company.customer_journal_id = False
        with self.assertRaises(UserError):
            self._validate(self._picking()).create_multi_invoice(first)

    def test_multi_transfer_actions(self):
        outgoing = self._validate(self._picking()) | self._validate(self._picking())
        outgoing.action_create_multi_invoice_for_multi_transfer()
        invoice = self.env["account.move"].search([("transfer_ids", "in", outgoing.ids)])
        self.assertEqual(invoice.move_type, "out_invoice")

        incoming = self._validate(self._picking("incoming")) | self._validate(self._picking("incoming"))
        incoming.action_create_multi_invoice_for_multi_transfer()
        bill = self.env["account.move"].search([("transfer_ids", "in", incoming.ids)])
        self.assertEqual(bill.picking_ids, incoming)

        with self.assertRaises(UserError):
            (outgoing | incoming).action_create_multi_invoice_for_multi_transfer()

        other_partner = self.env["res.partner"].create({"name": "Otro cliente"})
        mixed = self._validate(self._picking()) | self._validate(self._picking())
        mixed[1].partner_id = other_partner
        mixed.action_create_multi_invoice_for_multi_transfer()
        self.assertEqual(set(mixed.mapped("state_guide_dispatch")), {"invoiced"})

    def test_invoice_wizard(self):
        first = self._validate(self._picking())
        second = self._validate(self._picking())
        context = {"active_ids": (first | second).ids}

        self.assertEqual(first.action_open_invoice_wizard()["res_model"], "picking.invoice.wizard")
        wizard = Form(self.env["picking.invoice.wizard"].with_context(**context))
        wizard.invoice_type_selection = "unique"
        wizard = wizard.save()
        self.assertEqual(wizard.pickings_ids, first | second)
        wizard.with_context(**context).picking_selection_invoice()
        self.assertEqual(len(self.env["account.move"].search([("transfer_ids", "in", first.ids)])), 1)

        third = self._validate(self._picking())
        fourth = self._validate(self._picking())
        wizard = self.env["picking.invoice.wizard"].with_context(active_ids=(third | fourth).ids).create(
            {"invoice_type_selection": "multiple"}
        )
        wizard.with_context(active_ids=(third | fourth).ids).picking_selection_invoice()
        (third | fourth).invalidate_recordset()
        self.assertEqual(set((third | fourth).mapped("invoice_count")), {1})

    def test_invoice_wizard_validations(self):
        Wizard = self.env["picking.invoice.wizard"]
        draft = self._picking()
        done = self._validate(self._picking())
        other = self._validate(self._picking())
        other.partner_id = self.env["res.partner"].create({"name": "Otro"})
        incoming = self._validate(self._picking("incoming"))

        def run(mode, pickings):
            return Wizard.with_context(active_ids=pickings.ids).create(
                {"invoice_type_selection": mode, "pickings_ids": [(6, 0, pickings.ids)]}
            ).with_context(active_ids=pickings.ids).picking_selection_invoice()

        for mode, pickings in [
            ("unique", draft | done),
            ("unique", done | other),
            ("unique", incoming),
            ("multiple", done | other),
            ("multiple", incoming),
        ]:
            with self.assertRaises(UserError):
                run(mode, pickings)

        done.state_guide_dispatch = "invoiced"
        with self.assertRaises(UserError):
            run("multiple", done)

    def test_buttons_and_actions(self):
        picking = self._validate(self._picking())
        self.assertTrue(picking.show_create_invoice)
        self.assertFalse(picking.show_create_customer_credit)

        action = picking.action_open_picking_invoice()
        self.assertEqual(action["domain"], [("transfer_ids", "in", picking.id)])
        self.assertEqual(picking.print_dispatch_guide()["report_name"], "l10n_ve_stock_account.dispatch_guide_template")
        self.assertEqual(picking.get_digits(), self.env.ref("base.VEF").decimal_places)
        self.assertFalse(picking.get_foreign_currency_is_vef())

        invoice = picking.create_invoice()
        self.assertIn(picking, self.env["stock.picking"].search([("invoice_ids", "in", invoice.ids)]))
        self.assertEqual(invoice.guide_number, picking.guide_number)

    def test_origin_names(self):
        order = self.create_sale_order()
        order.action_confirm()
        self.assertEqual(order.picking_ids._get_origin_name(order.picking_ids), order.name)

        internal = self.create_picking("transfer", operation_code="internal")
        self.assertEqual(internal._get_origin_name(internal), internal.transfer_reason_id.name)

        incoming = self._picking("incoming")
        self.assertEqual(incoming._get_origin_name(incoming), incoming.name)

    def test_sale_invoice_updates_order(self):
        order = self.create_sale_order()
        order.action_confirm()
        picking = order.picking_ids
        self._validate(picking)

        picking.create_invoice()

        self.assertEqual(picking.state_guide_dispatch, "invoiced")
        self.assertEqual(picking.move_line_ids.qty_invoiced, 0)
        order.invoice_ids.with_context(move_action_post_alert=True).action_post()
        picking.move_line_ids.invalidate_recordset()
        picking.move_line_ids._compute_qty_invoiced()
        self.assertEqual(picking.move_line_ids.qty_invoiced, 2)

    def test_line_values_for_dispatch_guide(self):
        order = self.create_sale_order()
        order.order_line.filtered("product_id").discount = 10
        order.action_confirm()
        move = order.picking_ids.move_ids
        move.quantity = 2

        values = move._get_line_values()
        self.assertEqual(values["subtotal"], 200)
        self.assertEqual(values["discount_amount"], 20)
        self.assertAlmostEqual(values["total_with_tax"], 208.8)

        foreign = move._get_line_values(use_foreign_currency=True)
        self.assertEqual(foreign["quantity"], 2)

        manual = self.create_picking().move_ids
        self.assertEqual(manual._get_line_values()["subtotal"], 0)

    def test_free_form_print_counter_and_vendor_block(self):
        picking = self._validate(self._picking())
        invoice = picking.create_invoice()
        invoice.print_invoice_free_form()
        self.assertEqual(invoice.free_form_copy_number, 1)

        bill = self._validate(self._picking("incoming")).create_bill()
        report = self.env.ref("l10n_ve_invoice.action_invoice_free_form_l10n_ve_invoice")
        with self.assertRaises(ValidationError):
            self.env["ir.actions.report"]._render_qweb_pdf(report.report_name, bill.ids)
