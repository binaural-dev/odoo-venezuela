from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_pos_mf.models.pos_payment_method import (
    is_foreign_currency_fiscal_code,
)


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestPosPaymentMethodFiscalCode(TransactionCase):
    """Un código fiscal de divisa (20-24) exige ``apply_igtf`` activo.

    ``apply_igtf`` vive en ``l10n_ve_pos_igtf``, del que ``l10n_ve_pos_mf`` no
    depende. Las pruebas que necesitan el campo se saltan sin ese módulo y la
    que prueba su ausencia se salta con él: para cubrir todo hay que correrlas
    con y sin ``l10n_ve_pos_igtf`` instalado. Tarea 85447.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_igtf_field = "apply_igtf" in cls.env["pos.payment.method"]._fields
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "MF Fiscal Code Cash",
                "type": "cash",
                "code": "MFFC",
                "company_id": cls.env.company.id,
            }
        )

    def _create_method(self, name, code, **values):
        return self.env["pos.payment.method"].create(
            {
                "name": name,
                "journal_id": self.journal.id,
                "company_id": self.env.company.id,
                "code_fiscal_printer": code,
                **values,
            }
        )

    def _skip_without_igtf_field(self):
        if not self.has_igtf_field:
            self.skipTest("Requiere l10n_ve_pos_igtf (campo apply_igtf).")

    def test_01_foreign_code_helper(self):
        """Solo cuentan los dígitos, igual que el driver TFHKA."""
        for code in ("20", "21", "22", "23", "24", " 20", "20 "):
            self.assertTrue(is_foreign_currency_fiscal_code(code), code)
        for code in ("01", "2", "02", "15", "19", "25", "99", "", False, None, "ab"):
            self.assertFalse(is_foreign_currency_fiscal_code(code), code)

    def test_02_foreign_code_without_igtf_raises(self):
        self._skip_without_igtf_field()
        with self.assertRaisesRegex(ValidationError, r"EFECTIVO USD.*\b20\b"):
            self._create_method("EFECTIVO USD", "20", apply_igtf=False)

    def test_03_foreign_code_with_igtf_saves(self):
        self._skip_without_igtf_field()
        method = self._create_method("ZELLE", "22", apply_igtf=True)
        self.assertEqual(method.code_fiscal_printer, "22")

    def test_04_disable_igtf_on_foreign_code_raises(self):
        self._skip_without_igtf_field()
        method = self._create_method("EFECTIVO EUR", "21", apply_igtf=True)
        with self.assertRaises(ValidationError):
            method.apply_igtf = False

    def test_05_set_foreign_code_on_method_without_igtf_raises(self):
        self._skip_without_igtf_field()
        method = self._create_method("EFECTIVO USD", "01", apply_igtf=False)
        with self.assertRaises(ValidationError):
            method.code_fiscal_printer = "24"

    def test_06_local_code_without_igtf_saves(self):
        """Los códigos 01-19 no se ven afectados, aunque el método sea en USD."""
        values = {"apply_igtf": False} if self.has_igtf_field else {}
        method = self._create_method("EFECTIVO USD", "15", **values)
        self.assertEqual(method.code_fiscal_printer, "15")

    def test_07_single_digit_code_is_local(self):
        """El código "2" sin cero a la izquierda es el 02, no un 20."""
        values = {"apply_igtf": False} if self.has_igtf_field else {}
        method = self._create_method("CHEQUE", "2", **values)
        self.assertEqual(method.code_fiscal_printer, "2")

    def test_08_foreign_code_without_igtf_module_raises(self):
        """Sin l10n_ve_pos_igtf el PdV nunca cobra IGTF: 20-24 nunca es válido."""
        if self.has_igtf_field:
            self.skipTest("Solo aplica sin l10n_ve_pos_igtf instalado.")
        with self.assertRaises(ValidationError):
            self._create_method("EFECTIVO USD", "20")
