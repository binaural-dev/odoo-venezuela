from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_reversal_pt_balance")
class TestReversalPaymentTermBalance(TransactionCase):
    """Ticket #16790: la nota de credito de una factura con terminos de pago de
    varias cuotas (p.ej. 30% / 70%) fallaba con "El asiento no esta balanceado".

    `_distribute_to_lines` (reparto de la porcion real en las lineas por cobrar)
    se ejecutaba mientras la nota de credito se estaba creando, con las lineas
    de producto aun sin balance, y repartia un monto enorme sobre las cuotas.
    Ese reparto solo debe absorber diferencias de redondeo.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.country_ve = self.env.ref("base.ve")
        self.currency_vef = self.env.ref("base.VEF")
        self.currency_usd = self.env.ref("base.USD")
        self.company.write(
            {
                "account_fiscal_country_id": self.country_ve.id,
                "country_id": self.country_ve.id,
            }
        )
        # Solo se configuran las monedas si la compania aun no tiene moneda
        # alterna: cambiarlas con movimientos contables existentes esta
        # bloqueado, y en ese caso se usan las ya configuradas.
        if not self.company.foreign_currency_id:
            self.company.write(
                {
                    "currency_id": self.currency_vef.id,
                    "foreign_currency_id": self.currency_usd.id,
                }
            )
        self.currency_vef = self.company.currency_id
        self.currency_usd = self.company.foreign_currency_id
        self.today = fields.Date.today()
        self._set_usd_rate(881.8769)

        self.acc_rec = self._get_or_create(
            "120000", "Receivable", "asset_receivable", reconcile=True
        )
        self.acc_inc = self._get_or_create("400000", "Income", "income")
        self.acc_exp = self._get_or_create("500000", "Expense", "expense")
        self.acc_pay = self._get_or_create(
            "210000", "Payable", "liability_payable", reconcile=True
        )
        self.acc_tax = self._get_or_create(
            "200000", "Tax Payable", "liability_current", reconcile=True
        )

        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create(
            {
                "name": "Sales Test",
                "code": "SLTST",
                "type": "sale",
                "company_id": self.company.id,
                "default_account_id": self.acc_inc.id,
            }
        )

        self.purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].sudo().create(
            {
                "name": "Purchases Test",
                "code": "PRTST",
                "type": "purchase",
                "company_id": self.company.id,
                "default_account_id": self.acc_exp.id,
            }
        )

        tax_group = self.env["account.tax.group"].create(
            {
                "name": "IVA",
                "company_id": self.company.id,
                "country_id": self.country_ve.id,
            }
        )
        self.tax_by_type = {
            "out_invoice": self._create_tax(tax_group, "sale"),
            "in_invoice": self._create_tax(tax_group, "purchase"),
        }
        self.product = self.env["product.product"].create(
            {
                "name": "Producto reverso",
                "type": "service",
                "list_price": 74.2,
                "property_account_income_id": self.acc_inc.id,
                "property_account_expense_id": self.acc_exp.id,
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
            }
        )
        self.partner = self.env["res.partner"].create(
            {
                "name": "Contacto reverso",
                "country_id": self.country_ve.id,
                "property_account_receivable_id": self.acc_rec.id,
                "property_account_payable_id": self.acc_pay.id,
            }
        )
        self.term_30_70 = self.env["account.payment.term"].create(
            {
                "name": "30% ahora, el resto en 60 dias",
                "line_ids": [
                    Command.create({"value": "percent", "value_amount": 30, "nb_days": 0}),
                    Command.create({"value": "percent", "value_amount": 70, "nb_days": 60}),
                ],
            }
        )

    # -- helpers -----------------------------------------------------------

    def _create_tax(self, tax_group, type_tax_use):
        repartition = [
            (0, 0, {"repartition_type": "base", "factor_percent": 100.0}),
            (
                0,
                0,
                {
                    "repartition_type": "tax",
                    "factor_percent": 100.0,
                    "account_id": self.acc_tax.id,
                },
            ),
        ]
        return (
            self.env["account.tax"]
            .with_company(self.company)
            .create(
                {
                    "name": f"IVA 16% reverso {type_tax_use}",
                    "amount": 16.0,
                    "amount_type": "percent",
                    "type_tax_use": type_tax_use,
                    "company_id": self.company.id,
                    "tax_group_id": tax_group.id,
                    "invoice_repartition_line_ids": repartition,
                    "refund_repartition_line_ids": repartition,
                }
            )
        )

    def _get_or_create(self, code, name, acc_type, reconcile=False):
        acc = self.env["account.account"].search(
            [("code", "=", code), ("company_ids", "in", self.company.id)], limit=1
        )
        if not acc:
            acc = self.env["account.account"].create(
                {
                    "code": code,
                    "name": name,
                    "account_type": acc_type,
                    "company_ids": [(6, 0, [self.company.id])],
                    "reconcile": reconcile,
                }
            )
        return acc

    def _set_usd_rate(self, vef_per_usd, date=None):
        date = date or self.today
        Rate = self.env["res.currency.rate"]
        rate = Rate.search(
            [
                ("name", "=", date),
                ("currency_id", "=", self.currency_usd.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if rate:
            rate.write({"inverse_company_rate": vef_per_usd})
        else:
            Rate.create(
                {
                    "name": date,
                    "currency_id": self.currency_usd.id,
                    "inverse_company_rate": vef_per_usd,
                    "company_id": self.company.id,
                }
            )

    def _create_invoice(self, move_type="out_invoice", post=True, invoice_date=None):
        is_sale = move_type == "out_invoice"
        lines = [
            (5.4, 74.2),
            (5.4, 74.2),
            (10.6, 74.2),
            (3.6, 74.2),
            (7.2, 74.2),
            (7.2, 61.0),
        ]
        invoice = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "journal_id": (
                    self.sale_journal if is_sale else self.purchase_journal
                ).id,
                "currency_id": self.currency_usd.id,
                "invoice_date": invoice_date or self.today,
                "ref": "REV-16790",
                "invoice_payment_term_id": self.term_30_70.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": qty,
                            "price_unit": price,
                            "account_id": (self.acc_inc if is_sale else self.acc_exp).id,
                            "tax_ids": [(6, 0, self.tax_by_type[move_type].ids)],
                        }
                    )
                    for qty, price in lines
                ],
            }
        )
        if post:
            invoice.with_context(move_action_post_alert=True).action_post()
            self.assertEqual(invoice.state, "posted")
        return invoice

    def _pt_lines(self, move):
        return move.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        ).sorted("date_maturity")

    def _assert_reversal_matches(self, invoice, credit_note, same_term_lines=True):
        self.assertEqual(
            round(sum(credit_note.line_ids.mapped("debit")), 2),
            round(sum(credit_note.line_ids.mapped("credit")), 2),
            "La nota de credito debe quedar balanceada",
        )
        original_pt = self._pt_lines(invoice)
        reversed_pt = self._pt_lines(credit_note)
        self.assertEqual(len(original_pt), 2)
        self.assertAlmostEqual(
            sum(reversed_pt.mapped("balance")),
            -sum(original_pt.mapped("balance")),
            places=2,
            msg="Las cuentas por cobrar revertidas deben sumar el inverso",
        )
        if same_term_lines:
            self.assertEqual(len(reversed_pt), len(original_pt))
            for original, reversed_line in zip(original_pt, reversed_pt):
                self.assertAlmostEqual(
                    reversed_line.balance, -original.balance, places=2,
                    msg="La cuota revertida debe ser el inverso de la original",
                )
                self.assertAlmostEqual(
                    reversed_line.amount_currency, -original.amount_currency, places=2
                )
        self.assertAlmostEqual(credit_note.amount_total, invoice.amount_total, places=2)

    # -- tests -------------------------------------------------------------
    # Todas las pruebas corren para facturas de venta y de compra.

    MOVE_TYPES = {"out_invoice": "out_refund", "in_invoice": "in_refund"}

    def test_01_reverse_moves_two_term_lines_is_balanced(self):
        """Revertir una factura (venta/compra) con terminos 30/70 no desbalancea."""
        for move_type, refund_type in self.MOVE_TYPES.items():
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(move_type)
                credit_note = invoice._reverse_moves(
                    [{"date": self.today, "journal_id": invoice.journal_id.id}],
                    cancel=False,
                )
                self.assertEqual(credit_note.move_type, refund_type)
                self._assert_reversal_matches(invoice, credit_note)

    def test_02_reversal_wizard_is_balanced(self):
        """El mismo caso desde el asistente de reversion de la factura."""
        for move_type, refund_type in self.MOVE_TYPES.items():
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(move_type)
                wizard = (
                    self.env["account.move.reversal"]
                    .with_context(active_model="account.move", active_ids=invoice.ids)
                    .create(
                        {
                            "move_ids": [Command.set(invoice.ids)],
                            "date": self.today,
                            "journal_id": invoice.journal_id.id,
                        }
                    )
                )
                action = wizard.refund_moves()
                credit_note = self.env["account.move"].browse(action["res_id"])
                self.assertEqual(credit_note.move_type, refund_type)
                # El asistente genera la nota con una sola linea por cobrar/pagar.
                self._assert_reversal_matches(
                    invoice, credit_note, same_term_lines=False
                )

    def test_03_reversal_with_different_date_is_balanced(self):
        """La fecha de reversion distinta a la de la factura tampoco desbalancea."""
        for move_type in self.MOVE_TYPES:
            with self.subTest(move_type=move_type):
                invoice_date = self.today - timedelta(days=5)
                self._set_usd_rate(881.8769, invoice_date)
                invoice = self._create_invoice(move_type, invoice_date=invoice_date)
                credit_note = invoice._reverse_moves(
                    [{"date": self.today, "journal_id": invoice.journal_id.id}],
                    cancel=False,
                )
                self._assert_reversal_matches(invoice, credit_note)

    def test_04_distribute_to_lines_ignores_non_rounding_amounts(self):
        """Un monto muy superior a un ajuste de redondeo no se reparte."""
        for move_type in self.MOVE_TYPES:
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(move_type, post=False)
                pt_lines = self._pt_lines(invoice)
                before = {line.id: line.balance for line in pt_lines}
                self.assertEqual(len(pt_lines), 2)

                invoice._distribute_to_lines(
                    pt_lines, -2494335.91, self.company.currency_id
                )

                self.assertEqual({line.id: line.balance for line in pt_lines}, before)

    def test_05_distribute_to_lines_still_absorbs_rounding(self):
        """Una diferencia de redondeo (centimos) si se sigue repartiendo."""
        for move_type in self.MOVE_TYPES:
            with self.subTest(move_type=move_type):
                invoice = self._create_invoice(move_type, post=False)
                pt_lines = self._pt_lines(invoice)
                total_before = sum(pt_lines.mapped("balance"))

                # El reparto mueve solo las cuotas, asi que el asiento queda
                # momentaneamente desbalanceado: se desactiva la validacion.
                invoice._distribute_to_lines(
                    pt_lines.with_context(check_move_validity=False),
                    0.02,
                    self.company.currency_id,
                )

                self.assertAlmostEqual(
                    sum(pt_lines.mapped("balance")), total_before + 0.02, places=2
                )
