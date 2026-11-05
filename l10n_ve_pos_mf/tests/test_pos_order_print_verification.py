from odoo.exceptions import AccessError, UserError
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
        self.assertTrue(Order.mf_resolve_print_verification(self.order.uuid, resolved))
        self.assertEqual(self.order.mf_invoice_number, "505")
        self.assertFalse(self.order.mf_print_verification)

    def test_13_read_only_user_cannot_flag(self):
        user = new_test_user(self.env, login="mf_internal_user", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.env["pos.order"].with_user(user).mf_set_print_verification(
                self.order.uuid, self.verification
            )
