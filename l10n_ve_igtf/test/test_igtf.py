from .igtf_common import IGTFTestCommon
from odoo.tests import Form
from odoo.tools import float_compare
from odoo.tests import Form
from odoo.tools import float_compare
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo import Command, fields
import datetime
import logging

_logger = logging.getLogger(__name__)


@tagged("igtf", "igtf_run", "-at_install", "post_install")
class TestIGTFBasic(IGTFTestCommon):

    def test01_basic_igtf_flow(self):
        invoice = self._create_invoice_usd(1000)

        ig_tf = round(invoice.amount_total *
                      self.company.igtf_percentage / 100, 2)
        pay1 = self._create_payment(amount=invoice.amount_total, is_igtf=True)

        line_to_match = pay1.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(line_to_match.id)

        self.assertAlmostEqual(invoice.amount_residual, ig_tf, 2)

        usd_to_bsf = 35
        pay2 = self._create_payment(
            amount=ig_tf * usd_to_bsf,
            currency=self.currency_vef,
            journal=self.bank_journal_usd,  # o uno en BsF
            fx_rate=usd_to_bsf,
            fx_rate_inv=1 / usd_to_bsf,
        )
        bs_line = pay2.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(bs_line.id)

        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))

        _logger.info("test01_basic_igtf_flow superado")

    def test_02_igtf_decimal_amount(self):
        """Factura USD 1 234.56 – IGTF 3 % (37.04) pagado en dos tiempos con redondeos exactos."""
        # ──────────────────────────────
        # 1) Factura con decimales
        # ──────────────────────────────
        invoice = self._create_invoice_usd(1234.56)
        pct = self.company.igtf_percentage  # 3 %
        ig_tf = round(invoice.amount_total * pct / 100, 2)  # 37.04 USD

        # ──────────────────────────────
        # 2) Pago principal (USD) con IGTF activado
        #    Monto = neto, NO incluye IGTF
        # ──────────────────────────────
        pay_usd = self._create_payment(
            amount=invoice.amount_total,
            is_igtf=True,
        )

        # Conciliar contra la factura
        receivable_usd = pay_usd.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(receivable_usd.id)

        # Validaciones de redondeo IGTF
        self.assertAlmostEqual(
            pay_usd.igtf_amount,
            ig_tf,
            places=2,
            msg="IGTF debe ser 3 % redondeado a 2 decimales",
        )
        igtf_line = pay_usd.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_igtf_cli
        )
        self.assertTrue(
            igtf_line, "Debe existir la línea IGTF en el asiento de pago")
        self.assertAlmostEqual(abs(igtf_line.amount_currency), ig_tf, places=2)
        # Tras la conciliación, el residual debe ser exactamente IGTF
        self.assertAlmostEqual(
            invoice.amount_residual,
            ig_tf,
            places=2,
            msg="El residual debe ser igual al importe del IGTF",
        )

        # ------------------------------------------------------------------
        # 3) Segundo pago en BsF para liquidar el IGTF
        # ------------------------------------------------------------------
        usd_to_bsf = 35.0
        bsf_to_usd = round(1 / usd_to_bsf, 8)

        bank_journal_bs = self.env["account.journal"].search(
            [
                ("type", "=", "bank"),
                ("currency_id", "=", self.currency_vef.id),
            ],
            limit=1,
        ) or self.env["account.journal"].create(
            {
                "name": "Banco Bs",
                "code": "BNKBS",
                "type": "bank",
                "currency_id": self.currency_vef.id,
                "company_id": self.company.id,
            }
        )

        pm_line_bs = self.env["account.payment.method.line"].search(
            [
                ("journal_id", "=", bank_journal_bs.id),
                (
                    "payment_method_id",
                    "=",
                    self.env.ref(
                        "account.account_payment_method_manual_in").id,
                ),
                ("payment_type", "=", "inbound"),
            ],
            limit=1,
        ) or self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound Bs",
                "journal_id": bank_journal_bs.id,
                "payment_method_id": self.env.ref(
                    "account.account_payment_method_manual_in"
                ).id,
                "payment_type": "inbound",
            }
        )

        pay_bsf = self._create_payment(
            amount=round(ig_tf * usd_to_bsf, 2),
            currency=self.currency_vef,
            journal=bank_journal_bs,
            fx_rate=usd_to_bsf,
            fx_rate_inv=bsf_to_usd,
            is_igtf=False,
            pm_line=pm_line_bs,
        )

        receivable_bsf = pay_bsf.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(receivable_bsf.id)

        self.assertTrue(
            invoice.currency_id.is_zero(invoice.amount_residual),
            "La factura debe quedar sin residual",
        )
        self.assertIn(
            invoice.payment_state,
            ("paid", "in_payment"),
            "Estado de pago debe ser 'paid' o 'in_payment'",
        )

        _logger.info("-----test_02_igtf_decimal_amount superado.-----------")

    def test_03_igtf_zero_amount(self):
        """
        Pago IGTF con monto cero:

        • Debe crearse (no se considera error en Odoo)
        • No debe calcular IGTF ni crear la línea 236IGTF
        • La factura permanece sin saldar
        """

        invoice = self._create_invoice_usd(500)

        pay_zero = self._create_payment(amount=0.0, is_igtf=True)
        self.assertEqual(pay_zero.igtf_amount, 0.0)

        igtf_line = pay_zero.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_igtf_cli
        )

        self.assertFalse(igtf_line, "Con monto 0 no debe generarse línea IGTF")

        self.assertAlmostEqual(invoice.amount_residual,
                               invoice.amount_total, 2)
        self.assertEqual(invoice.payment_state, "not_paid")

        _logger.info("-----test_03_igtf_zero_amount superado.-----------")

    def test_04_igtf_negative_amount(self):
        """
        Intentar registrar un pago IGTF con monto negativo debe fallar.

        • Debe lanzarse ValidationError / UserError (según llegue desde ORM/SQL)
        • No debe crearse ninguna entrada contable asociada al pago
        """

        initial_moves = self.env["account.move"].search_count([])

        with self.assertRaises(Exception):
            self.env["account.payment"].create(
                {
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "partner_id": self.partner.id,
                    "amount": -50.0,
                    "currency_id": self.currency_usd.id,
                    "journal_id": self.bank_journal.id,
                    "payment_method_line_id": self.pm_line_in_usd.id,
                    "is_igtf": True,
                    "date": fields.Date.today(),
                }
            )

        # Confirm that no additional journal entry was created
        final_moves = self.env["account.move"].search_count([])
        self.assertEqual(
            initial_moves, final_moves, "No deberían haberse creado asientos contables"
        )

        _logger.info("-----test_04_igtf_negative_amount superado.-----------")

    def test_05_multiple_partial_igtf_payments(self):
        """La factura se liquida con dos pagos parciales que incluyen IGTF."""
        invoice = self._create_invoice_usd(1000.00)
        pct = self.company.igtf_percentage
        rate_factor = 1 - pct / 100

        pay1_amount = 300.00
        pay1 = self._create_payment(amount=pay1_amount, is_igtf=True)

        line1 = pay1.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(line1.id)

        expected_residual1 = round(
            invoice.amount_total - pay1_amount * rate_factor, 2)
        self.assertAlmostEqual(
            invoice.amount_residual,
            expected_residual1,
            2,
            "Residual tras primer pago incorrecto",
        )
        self.assertAlmostEqual(pay1.igtf_amount, round(
            pay1_amount * pct / 100, 2), 2)

        pay2_amount = round(invoice.amount_residual / rate_factor, 2)
        pay2 = self._create_payment(amount=pay2_amount, is_igtf=True)

        line2 = pay2.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(line2.id)

        self.assertTrue(
            invoice.currency_id.is_zero(invoice.amount_residual),
            "La factura debería quedar con residual = 0",
        )
        self.assertIn(
            invoice.payment_state,
            ("paid", "in_payment"),
            "Estado de pago final inesperado",
        )
        self.assertTrue(
            invoice.currency_id.is_zero(invoice.amount_residual),
            "La factura debería quedar con residual = 0",
        )

        self.assertIn(
            invoice.payment_state,
            ("paid", "in_payment"),
            "Estado de pago final inesperado",
        )

        self.assertGreater(invoice.bi_igtf, 0)
        self.assertLessEqual(invoice.bi_igtf, invoice.amount_total)

        _logger.info(
            "-----test_05_multiple_partial_igtf_payments superado.-----------")

    def test_06_remove_partial_igtf_conciliation(self):
        """
        Crea un pago IGTF parcial, lo concilia con la factura y luego
        elimina la conciliación desde el widget.  Se espera que la
        factura vuelva a su residual original y que el IGTF acumulado
        (bi_igtf) quede en cero.
        """
        invoice = self._create_invoice_usd(1000)

        pay = self._create_payment(amount=500, is_igtf=True)

        pay_line = pay.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        self.assertTrue(pay_line, "No se halló la línea a conciliar")

        invoice.js_assign_outstanding_line(pay_line.id)
        partial = pay_line.matched_debit_ids or pay_line.matched_credit_ids
        self.assertTrue(partial, "No se creó conciliación parcial IGTF")

        # --- Eliminar conciliación desde el widget ----------------
        invoice.js_remove_outstanding_partial(partial.id)

        self.assertTrue(
            invoice.currency_id.is_zero(
                invoice.amount_residual - invoice.amount_total),
            "La factura debe volver a residual completo tras des-conciliar",
        )
        self.assertIn(
            invoice.payment_state,
            ("not_paid", "partial"),
            "El estado debe reflejar factura no pagada tras remover IGTF",
        )
        self.assertFalse(
            pay_line.reconciled, "La línea de pago debe quedar sin conciliación"
        )
        self.assertAlmostEqual(
            invoice.bi_igtf, 0.0, 2, "bi_igtf debe volver a cero tras eliminar IGTF"
        )

        _logger.info(
            "-----test_06_remove_partial_igtf_conciliation superado.-----------"
        )

    def test_07_cancel_igtf_payment(self):
        """
        Se crea un pago IGTF, se concilia con la factura y luego
        se revierte (draft + unlink).  La factura debe volver al
        estado original (sin pagos, bi_igtf = 0).
        """
        invoice = self._create_invoice_usd(1000)

        pay = self._create_payment(amount=1000, is_igtf=True)

        pay_line = pay.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(pay_line.id)

        ig_tf = round(invoice.amount_total *
                      self.company.igtf_percentage / 100, 2)
        self.assertAlmostEqual(invoice.amount_residual, ig_tf, 2)

        # --- 2️⃣ Revertir pago ----------------------------------------
        pay.action_draft()
        pay.unlink()

        self.assertAlmostEqual(
            invoice.amount_residual,
            invoice.amount_total,
            2,
            "La factura debe volver a residual completo",
        )

        self.assertIn(
            invoice.payment_state,
            ("not_paid", "partial"),
            "Estado de pago debe reflejar factura sin saldar",
        )

        self.assertAlmostEqual(
            invoice.bi_igtf, 0.0, 2, "bi_igtf debe quedar en cero tras anular pago"
        )

        _logger.info("-----test_07_cancel_igtf_payment superado.-----------")

    def test_08_two_usd_payments(self):
        """La factura recibe dos pagos en USD con IGTF."""
        invoice = self._create_invoice_usd(1000.0)
        pct = self.company.igtf_percentage
        rate_factor = 1 - pct / 100

        pay1_amount = 600.0
        pay1 = self._create_payment(amount=pay1_amount, is_igtf=True)

        line1 = pay1.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(line1.id)

        expected_residual1 = round(invoice.amount_total - pay1_amount * rate_factor, 2)
        self.assertAlmostEqual(invoice.amount_residual, expected_residual1, 2)
        self.assertAlmostEqual(pay1.igtf_amount, round(pay1_amount * pct / 100, 2), 2)

        pay2_amount = round(invoice.amount_residual / rate_factor, 2)
        pay2 = self._create_payment(amount=pay2_amount, is_igtf=True)

        line2 = pay2.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        invoice.js_assign_outstanding_line(line2.id)

        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))

        _logger.info("-----test_08_two_usd_payments superado.-----------")
