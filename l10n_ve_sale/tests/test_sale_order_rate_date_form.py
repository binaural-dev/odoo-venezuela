from datetime import timedelta

from lxml import etree

from odoo import fields
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderRateDateForm(TransactionCase):
    """foreign_rate / foreign_inverse_rate must follow date_order when it is
    edited from the form, both on a new order and on a saved draft."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.usd = self.env.ref("base.USD")
        self.company.write({
            "currency_id": self.env.ref("base.VEF").id,
            "foreign_currency_id": self.usd.id,
            "update_sale_order_rate_using_date_order": True,
        })
        self.today = fields.Date.today()
        self.past = self.today - timedelta(days=5)
        self.past_next = self.past + timedelta(days=1)
        for day, rate in (
            (self.today, 1 / 40.0),
            (self.past, 1 / 30.0),
            (self.past_next, 1 / 35.0),
        ):
            self.env["res.currency.rate"].create({
                "currency_id": self.usd.id,
                "company_id": self.company.id,
                "name": day,
                "rate": rate,
            })
        self.partner = self.env["res.partner"].create({"name": "Rate Form Partner"})
        self.product = self.env["product.product"].create(
            {"name": "Rate Form Service", "type": "service", "list_price": 10}
        )

    def _expected(self, day):
        return self.env["res.currency.rate"].compute_rate(self.usd.id, day)

    def _set_date_order(self, form, day):
        # En borrador el core muestra date_order ("Quotation Date") solo en modo
        # debug, y Form no deja escribir un campo invisible: se simula la edicion
        # con el mismo onchange que dispara el cliente.
        form._values["date_order"] = fields.Datetime.to_datetime(day)
        form._perform_onchange("date_order")

    def _set_order_date(self, order, day):
        with Form(order) as form:
            self._set_date_order(form, day)
        return order

    def _set_invoice_date(self, invoice, day):
        with Form(invoice) as form:
            form.invoice_date_display = day
        return invoice

    def _rate_date_readonly_expr(self, move_type_marker):
        """readonly del campo invoice_date visible para ese tipo de documento (el core
        tiene uno para ventas y otro para compras)."""
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        for node in etree.fromstring(arch).xpath("//field[@name='invoice_date']"):
            if move_type_marker in (node.get("invisible") or "") and "not in" in (node.get("invisible") or ""):
                return node.get("readonly") or ""
        return ""

    def _banner(self, form):
        """Texto del aviso de la vista y si esta oculto para el registro del form: se evalua
        el `invisible` del div con los valores que el form tiene (lo que haria el cliente)."""
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        nodes = [
            node for node in etree.fromstring(arch).xpath("//div[hasclass('alert-info')]")
            if "use_invoice_rate_from_sale_order" in (node.get("invisible") or "")
        ]
        self.assertEqual(len(nodes), 1, "La vista debe tener el aviso de la tasa de la orden")
        values = {
            "use_invoice_rate_from_sale_order": form.use_invoice_rate_from_sale_order,
            "move_type": form.move_type,
            "sale_order_count": form.sale_order_count,
        }
        return " ".join(nodes[0].text.split()), safe_eval(nodes[0].get("invisible"), values)

    def _assert_form_rates(self, form, day):
        expected = self._expected(day)
        self.assertAlmostEqual(form.foreign_rate, expected["foreign_rate"], places=6)
        self.assertAlmostEqual(
            form.foreign_inverse_rate, expected["foreign_inverse_rate"], places=6
        )

    def test_new_order_date_change_computes_rates(self):
        self.assertNotAlmostEqual(
            self._expected(self.past)["foreign_rate"],
            self._expected(self.today)["foreign_rate"],
        )
        with Form(self.env["sale.order"]) as form:
            form.partner_id = self.partner
            self._set_date_order(form, self.past)
            # Los campos estan en la vista: el onchange los recalcula ya en el form
            self._assert_form_rates(form, self.past)
        order = form.save()
        # force_save: lo que calculo el form es lo que se guarda
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.past)["foreign_rate"], places=6
        )
        self.assertAlmostEqual(
            order.foreign_inverse_rate,
            self._expected(self.past)["foreign_inverse_rate"],
            places=6,
        )

    def test_existing_order_date_change_recomputes_rates(self):
        order = self._new_order_with_line()
        with Form(order) as form:
            self._set_date_order(form, self.past)
            self._assert_form_rates(form, self.past)
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.past)["foreign_rate"], places=6
        )
        self.assertAlmostEqual(
            order.foreign_inverse_rate,
            self._expected(self.past)["foreign_inverse_rate"],
            places=6,
        )

    def _new_order_with_line(self, day=None):
        with Form(self.env["sale.order"]) as form:
            form.partner_id = self.partner
            with form.order_line.new() as line:
                line.product_id = self.product
            if day:
                self._set_date_order(form, day)
        return form.save()

    def test_new_order_with_past_date_follows_setting(self):
        # Activo: la tasa es la de date_order. Apagado: la de la fecha de creacion (hoy).
        self.company.update_sale_order_rate_using_date_order = True
        order = self._new_order_with_line(self.past)
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.past)["foreign_rate"], places=6
        )
        self.assertEqual(order.foreign_rate_date, self.past)
        self.company.update_sale_order_rate_using_date_order = False
        order = self._new_order_with_line(self.past)
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.today)["foreign_rate"], places=6
        )
        self.assertEqual(order.foreign_rate_date, self.today)
        # Cambiar la fecha despues no mueve la tasa: sale de la fecha de creacion
        self._set_order_date(order, self.past_next)
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.today)["foreign_rate"], places=6
        )

    def test_confirm_keeps_rate_of_chosen_date_order(self):
        order = self._new_order_with_line()
        self._set_order_date(order, self.past)
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.past)["foreign_rate"], places=6
        )
        order.action_confirm()  # respeta date_order: no la reescribe con la fecha de hoy
        self.assertEqual(fields.Datetime.context_timestamp(order, order.date_order).date(), self.past)
        expected = self._expected(self.past)
        self.assertAlmostEqual(order.foreign_rate, expected["foreign_rate"], places=6)
        self.assertAlmostEqual(
            order.foreign_inverse_rate, expected["foreign_inverse_rate"], places=6
        )
        self.assertEqual(order.foreign_rate_date, self.past)

    def test_invoice_from_order_takes_rate_of_its_own_date(self):
        # Caso del reporte: orden con otra fecha, confirmar y facturar con otra fecha
        order = self._new_order_with_line()
        self._set_order_date(order, self.past)
        order.action_confirm()
        invoice = order._create_invoices()
        with Form(invoice) as form:
            form.invoice_date_display = self.past_next
            expected = self._expected(self.past_next)
            self.assertAlmostEqual(form.foreign_rate, expected["foreign_rate"], places=6)
        self.assertAlmostEqual(invoice.foreign_rate, expected["foreign_rate"], places=6)
        self.assertAlmostEqual(
            invoice.foreign_inverse_rate, expected["foreign_inverse_rate"], places=6
        )
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.past)["foreign_rate"], places=6
        )

    def _invoice_from_past_order(self):
        order = self._new_order_with_line()
        self._set_order_date(order, self.past)
        order.action_confirm()
        return order, order._create_invoices()

    def test_invoice_with_order_rate_setting_freezes_rate_and_locks_rate_date(self):
        # "Usar la tasa de la orden en la factura": la tasa queda congelada y la
        # fecha de tasa bloqueada aunque se cambie la fecha de la factura.
        self.company.use_invoice_rate_from_sale_order = True
        order, invoice = self._invoice_from_past_order()
        self.assertTrue(invoice._is_rate_date_locked())
        self.assertFalse(invoice.manually_set_rate)  # el bloqueo sigue al ajuste, no a una marca
        self.assertEqual(invoice.invoice_date, self.past)
        order_rate = self._expected(self.past)
        with Form(invoice) as form:
            # La vista lee el ajuste: Rate Date en solo lectura y aviso arriba
            self.assertTrue(form.use_invoice_rate_from_sale_order)
            self.assertIn("use_invoice_rate_from_sale_order", self._rate_date_readonly_expr("out_invoice"))
            form.invoice_date_display = self.past_next
            self.assertEqual(fields.Date.to_date(form.invoice_date), self.past)  # la fecha de tasa no se mueve
            self.assertAlmostEqual(form.foreign_rate, order_rate["foreign_rate"], places=6)
        self.assertEqual(invoice.invoice_date, self.past)
        # Cambiar la fecha de la factura otra vez: la tasa sigue siendo la de la orden
        self._set_invoice_date(invoice, self.past_next)
        self.assertAlmostEqual(invoice.foreign_rate, order_rate["foreign_rate"], places=6)
        self.assertAlmostEqual(
            invoice.foreign_inverse_rate, order_rate["foreign_inverse_rate"], places=6
        )

    def test_invoice_without_order_rate_setting_follows_its_date(self):
        self.company.use_invoice_rate_from_sale_order = False
        order, invoice = self._invoice_from_past_order()
        self.assertFalse(invoice._is_rate_date_locked())
        with Form(invoice) as form:
            self.assertFalse(form.use_invoice_rate_from_sale_order)
            form.invoice_date_display = self.past_next
            self.assertEqual(form.invoice_date, self.past_next)
        expected = self._expected(self.past_next)
        self.assertAlmostEqual(invoice.foreign_rate, expected["foreign_rate"], places=6)

    def test_toggling_order_rate_setting_does_not_recalculate(self):
        # La fecha tasa lo decide todo: activar o desactivar el ajuste no recalcula nada; solo
        # cambia lo que pasa al editar la fecha desde entonces.
        self.company.use_invoice_rate_from_sale_order = False
        order, invoice = self._invoice_from_past_order()
        self._set_invoice_date(invoice, self.past_next)
        own = self._expected(self.past_next)["foreign_rate"]
        self.company.use_invoice_rate_from_sale_order = True
        self.assertAlmostEqual(invoice.foreign_rate, own, places=6)
        self.assertTrue(invoice._is_rate_date_locked())
        self.company.use_invoice_rate_from_sale_order = False
        self.assertAlmostEqual(invoice.foreign_rate, own, places=6)
        self._set_invoice_date(invoice, self.past)
        self.assertAlmostEqual(
            invoice.foreign_rate, self._expected(self.past)["foreign_rate"], places=6
        )

    def test_toggling_setting_does_not_rewrite_posted_invoice(self):
        self.company.use_invoice_rate_from_sale_order = False
        order, invoice = self._invoice_from_past_order()
        self._set_invoice_date(invoice, self.past_next)
        invoice._post()
        posted_rate = invoice.foreign_rate
        self.assertEqual(invoice.state, "posted")
        self.company.use_invoice_rate_from_sale_order = True
        self.assertAlmostEqual(invoice.foreign_rate, posted_rate, places=6)

    def test_approved_order_keeps_rate_but_draft_follows_date_order(self):
        self.company.update_sale_order_rate_using_date_order = True
        order = self._new_order_with_line()
        self._set_order_date(order, self.past)
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.past)["foreign_rate"], places=6
        )
        order.action_confirm()
        self._set_order_date(order, self.past_next)
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.past)["foreign_rate"], places=6
        )

    def test_order_date_uses_user_timezone_not_server(self):
        # 01:00 UTC del dia siguiente sigue siendo el dia de la tasa en Caracas
        self.company.update_sale_order_rate_using_date_order = True
        self.env.user.tz = "America/Caracas"
        order = self.env["sale.order"].with_context(tz=False)
        with Form(order) as form:
            form.partner_id = self.partner
            with form.order_line.new() as line:
                line.product_id = self.product
            self._set_date_order(
                form, fields.Datetime.to_datetime(self.past_next).replace(hour=1)
            )
            self._assert_form_rates(form, self.past)
        self.assertEqual(form.save().foreign_rate_date, self.past)

    def test_banner_shows_only_when_setting_is_on(self):
        for flag in (True, False):
            self.company.use_invoice_rate_from_sale_order = flag
            order, invoice = self._invoice_from_past_order()
            with Form(invoice) as form:
                text, hidden = self._banner(form)
            self.assertEqual(hidden, not flag)
            self.assertIn("This document uses the exchange rate of its sale order", text)
            self.assertIn("the Rate Date is locked", text)
            self.assertIn("will not be recalculated when the invoice date changes", text)

    def test_banner_hidden_for_invoice_without_order(self):
        self.company.use_invoice_rate_from_sale_order = True
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as form:
            form.partner_id = self.partner
            _text, hidden = self._banner(form)
        self.assertTrue(hidden)

    def test_lock_follows_linked_order_not_typed_origin(self):
        # El aviso y el bloqueo salen de la configuracion y de la orden realmente vinculada
        # (sale_order_count), no del texto de invoice_origin.
        self.company.use_invoice_rate_from_sale_order = True
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as form:
            form.partner_id = self.partner
            _text, hidden = self._banner(form)
            self.assertTrue(hidden)
            self.assertEqual(form.sale_order_count, 0)
        expr = self._rate_date_readonly_expr("out_invoice")
        self.assertIn("sale_order_count == 1", expr)
        self.assertNotIn("invoice_origin", expr)

    def test_invoice_from_manual_order_is_not_marked_manual(self):
        # manually_set_rate no viaja a la factura: la tasa de la factura sale de la configuracion
        for use in (True, False):
            self.company.use_invoice_rate_from_sale_order = use
            order = self._new_order_with_line(self.past)
            order.write({"manually_set_rate": True, "foreign_rate": 77.0})
            order.action_confirm()
            invoice = order._create_invoices()
            self.assertFalse(invoice.manually_set_rate)
            self.assertNotEqual(invoice.foreign_rate, 77.0)

    def test_every_setting_combination_from_the_form(self):
        # Orden creada hoy con fecha pasada, aprobada y facturada con otra fecha
        for update in (True, False):
            for use in (True, False):
                self.company.update_sale_order_rate_using_date_order = update
                self.company.use_invoice_rate_from_sale_order = use
                order = self._new_order_with_line(self.past)
                order.action_confirm()
                order_day = self.past if update else self.today
                self.assertAlmostEqual(
                    order.foreign_rate, self._expected(order_day)["foreign_rate"], places=6
                )
                invoice = order._create_invoices()
                with Form(invoice) as form:
                    if not use:
                        form.invoice_date_display = self.past_next
                    invoice_day = order_day if use else self.past_next
                    self._assert_form_rates(form, invoice_day)
                self.assertAlmostEqual(
                    invoice.foreign_rate, self._expected(invoice_day)["foreign_rate"], places=6,
                    msg="update=%s use=%s" % (update, use),
                )

    def test_toggling_setting_leaves_unrelated_documents_alone(self):
        # Solo se recalculan las facturas de cliente en borrador que vienen de una orden: un
        # asiento y una factura sin orden conservan la tasa que tengan. (El asiento no tiene
        # formulario de captura de tasa: se crea por codigo.)
        entry = self.env["account.move"].create({"move_type": "entry"})
        entry.foreign_rate = 777.0
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as form:
            form.partner_id = self.partner
            form.invoice_date_display = self.past
        free_invoice = form.save()
        free_invoice.foreign_rate = 555.0
        self.company.use_invoice_rate_from_sale_order = True
        self.company.use_invoice_rate_from_sale_order = False
        self.assertEqual(entry.foreign_rate, 777.0)
        self.assertEqual(free_invoice.foreign_rate, 555.0)

    def test_manual_order_without_rate_gets_one(self):
        # El check manual va oculto: lo fijan integraciones y codigo. Una orden marcada manual
        # que nace sin tasa la calcula; con tasa, la respeta.
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "manually_set_rate": True}
        )
        self.assertAlmostEqual(
            order.foreign_rate, self._expected(self.today)["foreign_rate"], places=6
        )
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "manually_set_rate": True, "foreign_rate": 77.0}
        )
        self.assertEqual(order.foreign_rate, 77.0)

    def test_purchase_setting_does_not_act_on_sale_invoices(self):
        if "use_invoice_rate_from_purchase_order" not in self.company._fields:
            self.skipTest("binaural_purchase no esta instalado")
        self.company.use_invoice_rate_from_sale_order = False
        self.company.use_invoice_rate_from_purchase_order = True
        order, invoice = self._invoice_from_past_order()
        self.assertFalse(invoice._is_rate_date_locked())
