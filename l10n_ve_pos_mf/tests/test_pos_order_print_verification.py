import re

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestPosOrderPrintVerification(TransactionCase):
    """Pedidos cuya impresión fiscal quedó "por verificar" (el driver no
    confirmó si la máquina emitió el documento). Tarea 85447.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        config = cls.env["pos.config"].create({"name": "MF verification"})
        session = cls.env["pos.session"].create({"config_id": config.id})
        cls.order = cls.env["pos.order"].create(
            {
                "session_id": session.id,
                "amount_tax": 0.0,
                "amount_total": 1.0,
                "amount_paid": 1.0,
                "amount_return": 0.0,
            }
        )
        cls.verification = {
            "docType": "invoice",
            "before": {
                "number": 504,
                "salesSubtotal": "100",
                "dailyClosureCounter": 137,
                "serial": "Z7C7046254",
            },
            "paymentSent": True,
            "closeAcked": False,
        }

    def _flag(self):
        self.order.mf_print_verification = self.verification

    def test_01_field_loaded_in_pos(self):
        fields_list = self.env["pos.order"]._load_pos_data_fields(self.order.config_id)
        self.assertTrue(not fields_list or "mf_print_verification" in fields_list)

    def test_02_set_print_verification(self):
        Order = self.env["pos.order"]
        self.assertTrue(Order.mf_set_print_verification(self.order.uuid, self.verification))
        self.assertEqual(self.order.mf_print_verification, self.verification)
        self.assertFalse(Order.mf_set_print_verification("no-such-uuid", self.verification))

    def test_03_set_skips_order_with_fiscal_number(self):
        self.order.write_mf_invoice_data("504", "Z7C7046254", "138")
        self.assertFalse(
            self.env["pos.order"].mf_set_print_verification(self.order.uuid, self.verification)
        )
        self.assertFalse(self.order.mf_print_verification)

    def test_04_resolve_printed(self):
        self._flag()
        resolved = {"printed": True, "invoiceNumber": "505", "serial": "Z7C7046254", "reportZ": 138}
        self.assertTrue(self.env["pos.order"].mf_resolve_print_verification(self.order.uuid, resolved))
        self.assertEqual(self.order.mf_invoice_number, "505")
        self.assertEqual(self.order.fiscal_machine, "Z7C7046254")
        self.assertEqual(self.order.mf_reportz, "138")
        self.assertFalse(self.order.mf_print_verification)

    def test_05_resolve_not_printed(self):
        self._flag()
        self.assertTrue(
            self.env["pos.order"].mf_resolve_print_verification(self.order.uuid, {"printed": False})
        )
        self.assertFalse(self.order.mf_invoice_number)
        self.assertFalse(self.order.mf_print_verification)

    def test_06_resolve_unknown_order(self):
        self.assertFalse(
            self.env["pos.order"].mf_resolve_print_verification("no-such-uuid", {"printed": False})
        )

    def test_06b_resolve_needs_flag(self):
        """Sin la marca no se escribe nada: no sirve para numerar cualquier pedido."""
        resolved = {"printed": True, "invoiceNumber": "505", "serial": "Z7C7046254", "reportZ": 138}
        self.assertTrue(self.env["pos.order"].mf_resolve_print_verification(self.order.uuid, resolved))
        self.assertFalse(self.order.mf_invoice_number)

    def test_06c_invalid_data(self):
        Order = self.env["pos.order"]
        self._flag()
        invalid = (
            "printed",
            {},
            {"printed": "yes"},
            {"printed": True, "invoiceNumber": ""},
            {"printed": True, "invoiceNumber": "505A"},
            {"printed": True, "invoiceNumber": "-505"},
            {"printed": True, "invoiceNumber": True},
            {"printed": True, "invoiceNumber": ["505"]},
        )
        for resolved in invalid:
            with self.assertRaises(UserError):
                Order.mf_resolve_print_verification(self.order.uuid, resolved)
        for verification in ("x", {}, {"before": "x"}):
            with self.assertRaises(UserError):
                Order.mf_set_print_verification(self.order.uuid, verification)
        self.assertFalse(self.order.mf_invoice_number)
        self.assertEqual(self.order.mf_print_verification, self.verification)

    def test_06d_resolve_number_from_driver(self):
        """El driver puede mandar el número como texto con espacios o como entero."""
        Order = self.env["pos.order"]
        for number, expected in ((" 505 ", "505"), (506, "506")):
            self.order.write({"mf_invoice_number": False})
            self._flag()
            Order.mf_resolve_print_verification(self.order.uuid, {"printed": True, "invoiceNumber": number})
            self.assertEqual(self.order.mf_invoice_number, expected)

    def test_07_resolve_keeps_existing_number(self):
        self.order.write_mf_invoice_data("504", "Z7C7046254", "138")
        self._flag()
        resolved = {"printed": True, "invoiceNumber": "999", "serial": "Z7C7046254", "reportZ": 138}
        self.env["pos.order"].mf_resolve_print_verification(self.order.uuid, resolved)
        self.assertEqual(self.order.mf_invoice_number, "504")
        self.assertFalse(self.order.mf_print_verification)
        # El chatter no contradice al pedido: dice que conserva su número.
        self.assertIn("keeps", self.order.message_ids[:1].body)
        self.assertIn("504", self.order.message_ids[:1].body)

    def _wizard(self, **values):
        return self.env["pos.order.mf.verification.wizard"].create({"order_id": self.order.id, **values})

    def test_08_wizard_suggests_expected_number(self):
        self._flag()
        wizard = self._wizard(result="printed")
        self.assertEqual(wizard.expected_number, "505")
        self.assertEqual(wizard.expected_serial, "Z7C7046254")
        self.assertEqual(wizard.expected_reportz, "138")

    def test_09_wizard_printed(self):
        self._flag()
        self._wizard(
            result="printed", mf_invoice_number="505", fiscal_machine="Z7C7046254", mf_reportz="138"
        ).action_confirm()
        self.assertEqual(self.order.mf_invoice_number, "505")
        self.assertFalse(self.order.mf_print_verification)

    def test_10_wizard_not_printed(self):
        self._flag()
        self._wizard(result="not_printed").action_confirm()
        self.assertFalse(self.order.mf_invoice_number)
        self.assertFalse(self.order.mf_print_verification)

    def test_11_wizard_errors(self):
        with self.assertRaises(UserError):
            self._wizard(result="not_printed").action_confirm()
        self._flag()
        with self.assertRaises(UserError):
            self._wizard(result="printed").action_confirm()
        self.assertTrue(self.order.mf_print_verification)

    def test_12_pos_user_without_sudo(self):
        """El usuario del PdV marca y resuelve con sus propios permisos."""
        user = new_test_user(self.env, login="mf_pos_user", groups="point_of_sale.group_pos_user")
        Order = self.env["pos.order"].with_user(user)
        self.assertTrue(Order.mf_set_print_verification(self.order.uuid, self.verification))
        resolved = {"printed": True, "invoiceNumber": "505", "serial": "Z7C7046254", "reportZ": 138}
        before = set(self.order.message_ids.ids)
        self.assertTrue(Order.mf_resolve_print_verification(self.order.uuid, resolved))
        self.assertEqual(self.order.mf_invoice_number, "505")
        self.assertFalse(self.order.mf_print_verification)
        message = self.order.message_ids.filtered(lambda m: m.id not in before)
        self.assertEqual(len(message), 1)
        self.assertEqual(message.author_id, user.partner_id)

    def test_13_read_only_user_cannot_flag(self):
        user = new_test_user(self.env, login="mf_internal_user", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.env["pos.order"].with_user(user).mf_set_print_verification(
                self.order.uuid, self.verification
            )

    # Revisión del PR (tarea 85447): el número de otro documento, el rastro de
    # la resolución y la impresión desde Contabilidad.

    def _other_order(self, amount=1.0):
        return self.env["pos.order"].create(
            {
                "session_id": self.order.session_id.id,
                "amount_tax": 0.0,
                "amount_total": amount,
                "amount_paid": amount,
                "amount_return": 0.0,
            }
        )

    def _invoice(self, move_type="out_invoice"):
        # La localización exige la tasa del día de la moneda extranjera.
        company = self.env.company
        foreign = company.foreign_currency_id if "foreign_currency_id" in company._fields else False
        today = fields.Date.context_today(self.env.user)
        Rate = self.env["res.currency.rate"]
        if foreign and not Rate.search_count(
            [("currency_id", "=", foreign.id), ("company_id", "=", company.id), ("name", "=", today)]
        ):
            Rate.create({"currency_id": foreign.id, "company_id": company.id, "name": today, "rate": 1.0})
        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.env.company.id)], limit=1
        ) or self.env["account.journal"].create({"name": "MF sales", "code": "MFS", "type": "sale"})
        return self.env["account.move"].create({"move_type": move_type, "journal_id": journal.id})

    def test_14_wizard_rejects_number_of_other_order(self):
        """El número sugerido puede ser de otro pedido: con ceros a la izquierda también."""
        other = self._other_order()
        other.write_mf_invoice_data("00000505", "Z7C7046254", "138")
        self._flag()
        wizard = self._wizard(result="printed")
        wizard._onchange_result()
        self.assertEqual(wizard.mf_invoice_number, "505")
        with self.assertRaisesRegex(UserError, re.escape(other.display_name)):
            wizard.action_confirm()
        self.assertFalse(self.order.mf_invoice_number)
        self.assertTrue(self.order.mf_print_verification)

    def test_15_wizard_same_number_other_printer_or_document(self):
        """Otra máquina, o una nota de crédito (contador aparte), no son el mismo número."""
        self._other_order().write_mf_invoice_data("505", "Z7C0000001", "1")
        self._other_order(amount=-1.0).write_mf_invoice_data("505", "Z7C7046254", "138")
        self._other_order().write_mf_invoice_data("1505", "Z7C7046254", "138")
        self._flag()
        self._wizard(
            result="printed", mf_invoice_number="505", fiscal_machine="Z7C7046254", mf_reportz="138"
        ).action_confirm()
        self.assertEqual(self.order.mf_invoice_number, "505")
        self.assertFalse(self.order.mf_print_verification)

    def test_16_wizard_number_only_digits(self):
        self._flag()
        for number in ("50S", "-505", "5 05", "\uff15\uff10\uff15"):
            with self.assertRaises(UserError):
                self._wizard(
                    result="printed", mf_invoice_number=number, fiscal_machine="Z7C7046254"
                ).action_confirm()
        self.assertFalse(self.order.mf_invoice_number)
        self.assertTrue(self.order.mf_print_verification)

    def test_17_wizard_rejects_number_of_backend_invoice(self):
        """La factura del backend usa el mismo contador de la máquina que el PdV."""
        invoice = self._invoice()
        invoice.write({"mf_invoice_number": "505", "mf_serial": "Z7C7046254"})
        refund = self._invoice("out_refund")
        refund.write({"mf_invoice_number": "506", "mf_serial": "Z7C7046254"})
        self._flag()
        with self.assertRaisesRegex(UserError, re.escape(invoice.display_name)):
            self._wizard(
                result="printed", mf_invoice_number="505", fiscal_machine="Z7C7046254"
            ).action_confirm()
        self._wizard(
            result="printed", mf_invoice_number="506", fiscal_machine="Z7C7046254"
        ).action_confirm()
        self.assertEqual(self.order.mf_invoice_number, "506")

    def test_18_resolution_in_chatter(self):
        """Queda quién resolvió, el resultado y la foto que se descarta."""
        self._flag()
        before = set(self.order.message_ids.ids)
        resolved = {"printed": True, "invoiceNumber": "505", "serial": "Z7C7046254", "reportZ": 138}
        self.env["pos.order"].mf_resolve_print_verification(self.order.uuid, resolved)
        message = self.order.message_ids.filtered(lambda m: m.id not in before)
        self.assertEqual(len(message), 1)
        self.assertIn("505", message.body)
        self.assertIn("504", message.body)
        self.assertIn("Z7C7046254", message.body)

        self.order.write({"mf_invoice_number": False})
        self._flag()
        before = set(self.order.message_ids.ids)
        self._wizard(result="not_printed").action_confirm()
        message = self.order.message_ids.filtered(lambda m: m.id not in before)
        self.assertEqual(len(message), 1)
        self.assertIn("did not print", message.body)
        self.assertIn("504", message.body)

    def test_19_filter_orders_to_verify(self):
        resolved = self._other_order()
        resolved.mf_print_verification = self.verification
        resolved.mf_print_verification = False
        self._flag()
        found = self.env["pos.order"].search([("mf_print_verification", "!=", False)])
        self.assertIn(self.order, found)
        self.assertNotIn(resolved, found)

    def test_20_backend_print_blocked_while_verifying(self):
        """Desde Contabilidad no se imprime el documento de un pedido por verificar."""
        if not hasattr(self.env["account.move"], "_mf_check_pos_print_verification"):
            self.skipTest("l10n_ve_account_mf no está instalado")
        invoice = self._invoice()
        self.order.account_move = invoice
        self._flag()
        with self.assertRaisesRegex(ValidationError, re.escape(self.order.display_name)):
            invoice.check_print_out_invoice()

        refund = self._invoice("out_refund")
        self.order.account_move = refund
        with self.assertRaisesRegex(ValidationError, re.escape(self.order.display_name)):
            refund.check_print_out_refund()

        # Resuelto, vuelven las validaciones de siempre (aquí, factura en borrador).
        self.order.account_move = invoice
        self.order.mf_print_verification = False
        with self.assertRaisesRegex(ValidationError, "without validation"):
            invoice.check_print_out_invoice()

    def test_21_wizard_serial_and_number_of_the_reading(self):
        """El documento solo pudo salir en la máquina de la foto y después de su número."""
        self._flag()
        for serial in ("Z7C7O46254", "Z7C0000001"):
            with self.assertRaisesRegex(UserError, "Z7C7046254"):
                self._wizard(
                    result="printed", mf_invoice_number="505", fiscal_machine=serial
                ).action_confirm()
        for number in ("50", "504", "00000504"):
            with self.assertRaisesRegex(UserError, "504"):
                self._wizard(
                    result="printed", mf_invoice_number=number, fiscal_machine="Z7C7046254"
                ).action_confirm()
        self.assertFalse(self.order.mf_invoice_number)
        self.assertTrue(self.order.mf_print_verification)

    def test_22_chatter_with_kept_number(self):
        """El chatter no contradice al pedido que ya tenía número."""
        Order = self.env["pos.order"]
        # La máquina dice "no emitido", pero otra caja ya le había puesto número.
        self.order.write_mf_invoice_data("504", "Z7C7046254", "138")
        self._flag()
        Order.mf_resolve_print_verification(self.order.uuid, {"printed": False})
        body = self.order.message_ids[:1].body
        self.assertIn("keeps the fiscal number 504", body)
        self.assertNotIn("pending", body)
        self.assertEqual(self.order.mf_invoice_number, "504")

        # El mismo número por su valor: el mensaje normal de emitido.
        self.order.write({"mf_invoice_number": "00000505"})
        self._flag()
        resolved = {"printed": True, "invoiceNumber": "505", "serial": "Z7C7046254", "reportZ": 138}
        Order.mf_resolve_print_verification(self.order.uuid, resolved)
        body = self.order.message_ids[:1].body
        self.assertIn("printed it as number 505", body)
        self.assertNotIn("keeps", body)
