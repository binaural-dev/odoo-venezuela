from odoo import Command, fields
from odoo.tests import tagged

from .test_retention_payment_foreign_amount_rate_date import (
    TestRetentionPaymentForeignAmountRateDate as _Flow,
)
from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_cash_basis_foreign")
class TestRetentionCashBasisForeign(RetentionTestCommon):
    """Ticket #16240: al cobrar con una retencion de IVA una factura con
    impuesto exigible "al pagar", el asiento de base efectivo (IMBEF) debe
    traer el monto alterno en todas sus lineas, incluidas las de impuesto.

    La factura se crea en bolivares (moneda de la compania), asi que las lineas
    del IMBEF se valoran por la tasa y no por `amount_currency`.

    Se reutilizan los helpers de TestRetentionPaymentForeignAmountRateDate
    (documento y retencion creados con `Form`) sin heredar sus pruebas."""

    RATE_DOC_DATE = _Flow.RATE_DOC_DATE
    RATE_ACCOUNTING_DATE = _Flow.RATE_ACCOUNTING_DATE
    AMOUNT = _Flow.AMOUNT
    CUSTOMER_RETENTION_AMOUNT = _Flow.CUSTOMER_RETENTION_AMOUNT

    _set_rates = _Flow._set_rates
    _form_document = _Flow._form_document
    _document = _Flow._document
    _retention_from_form = _Flow._retention_from_form
    _economic_activity = _Flow._economic_activity

    def setUp(self):
        super().setUp()
        self.accounting_date = fields.Date.today()
        self.doc_date = fields.Date.subtract(self.accounting_date, days=3)
        self._set_rates(self.RATE_DOC_DATE, self.RATE_ACCOUNTING_DATE)

        Account = self.env["account.account"]

        def account(code, name, reconcile=False):
            return Account.create({
                "code": code, "name": name, "account_type": "liability_current",
                "reconcile": reconcile,
                "company_ids": [Command.set(self.company.ids)],
            })

        self.acc_transition = account("CB2101", "CB IVA por declarar", True)
        self.acc_final = account("CB2102", "CB Debito fiscal")
        self.acc_base = account("CB2103", "CB Transitoria base", True)
        self.company.write({
            "tax_exigibility": True,
            "account_fiscal_country_id": self.company.country_id.id,
            "account_cash_basis_base_account_id": self.acc_base.id,
        })
        if not self.company.tax_cash_basis_journal_id:
            self.company.tax_cash_basis_journal_id = self.env["account.journal"].create({
                "name": "CB Cash Basis", "code": "CBIMB", "type": "general",
                "company_id": self.company.id,
            })
        self.tax_iva_16.write({
            "tax_exigibility": "on_payment",
            "cash_basis_transition_account_id": self.acc_transition.id,
        })
        self.tax_iva_16.invoice_repartition_line_ids.filtered(
            lambda r: r.repartition_type == "tax"
        ).account_id = self.acc_final

    def test_iva_retention_on_cash_basis_invoice(self):
        document = self._document("out_invoice", "iva")
        self.assertEqual(document.currency_id, self.currency_vef)
        tax_line = document.line_ids.filtered(lambda l: l.display_type == "tax")
        self.assertEqual(tax_line.account_id, self.acc_transition)

        retention = self._retention_from_form("iva", document)
        retention.action_post()

        caba = self.env["account.move"].search(
            [("tax_cash_basis_origin_move_id", "=", document.id)]
        )
        self.assertTrue(caba, "La retencion debe generar el asiento de base efectivo.")
        rate = self.RATE_ACCOUNTING_DATE if all(
            m.date == self.accounting_date for m in caba
        ) else self.RATE_DOC_DATE
        for move in caba:
            self.assertEqual(len(move.line_ids), 4)
            tax_lines = move.line_ids.filtered(
                lambda l: l.account_id in (self.acc_transition, self.acc_final)
            )
            self.assertEqual(len(tax_lines), 2)
            for line in move.line_ids:
                self.assertTrue(
                    line.foreign_balance,
                    f"Linea {line.account_id.code} del IMBEF sin monto alterno",
                )
            for line in tax_lines:
                self.assertAlmostEqual(
                    abs(line.foreign_balance),
                    self.currency_usd.round(abs(line.balance) / rate),
                    places=2,
                )
            self.assertAlmostEqual(sum(move.line_ids.mapped("foreign_balance")), 0.0, 2)
            self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, 2)
