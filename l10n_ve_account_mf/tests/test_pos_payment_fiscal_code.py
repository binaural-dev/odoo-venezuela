from types import SimpleNamespace

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_account_mf")
class TestPosPaymentFiscalCode(TransactionCase):
    """Code sent to the fiscal machine for each payment of the POS order a
    credit note comes from (``_mf_pos_payment_fiscal_code``)."""

    def _payment(self, method_code=False, journal_code=False, own=None):
        method = SimpleNamespace(
            code_fiscal_printer=method_code,
            journal_id=SimpleNamespace(payment_method=journal_code),
        )
        payment = SimpleNamespace(payment_method_id=method)
        if own is not None:
            payment._get_fiscal_code = lambda: own
        return payment

    def test_01_code_of_the_payment_method(self):
        payment = self._payment(method_code="03", journal_code="06")
        self.assertEqual(self.env["account.move"]._mf_pos_payment_fiscal_code(payment), "03")

    def test_02_journal_code_without_method_code(self):
        payment = self._payment(journal_code="06")
        self.assertEqual(self.env["account.move"]._mf_pos_payment_fiscal_code(payment), "06")

    def test_03_default_code(self):
        payment = self._payment()
        self.assertEqual(self.env["account.move"]._mf_pos_payment_fiscal_code(payment), "01")

    def test_04_payment_that_knows_its_own_code(self):
        payment = self._payment(method_code="01", own="20")
        self.assertEqual(self.env["account.move"]._mf_pos_payment_fiscal_code(payment), "20")

    def test_05_payment_without_own_code_falls_back(self):
        payment = self._payment(method_code="05", own=False)
        self.assertEqual(self.env["account.move"]._mf_pos_payment_fiscal_code(payment), "05")
