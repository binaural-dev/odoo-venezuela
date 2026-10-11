from odoo import fields
from odoo.tests import TransactionCase, tagged

RATE = 803.34  # Bs por USD


@tagged("post_install", "-at_install")
class TestMfInvoiceCurrency(TransactionCase):
    """Payload de la máquina fiscal para facturas en una moneda distinta a la
    de la compañía (compañía en Bs, factura en USD): líneas y pagos en Bs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.usd.active = True
        cls.company = cls.env.ref("base.main_company")
        ve = cls.env.ref("base.ve")
        wanted = {
            "currency_id": cls.vef,
            "foreign_currency_id": cls.usd,
            "country_id": ve,
            "account_fiscal_country_id": ve,
        }
        # Solo lo que difiere: en una BD con movimientos no se puede reescribir
        # la moneda alterna aunque sea la misma.
        vals = {name: rec.id for name, rec in wanted.items() if cls.company[name] != rec}
        if cls.company.tax_calculation_rounding_method != "round_globally":
            vals["tax_calculation_rounding_method"] = "round_globally"
        if vals:
            cls.company.write(vals)
        today = fields.Date.today()
        Rate = cls.env["res.currency.rate"]
        for currency, value in ((cls.vef, 1.0), (cls.usd, RATE)):
            Rate.search(
                [
                    ("currency_id", "=", currency.id),
                    ("company_id", "=", cls.company.id),
                    ("name", ">=", today),
                ]
            ).unlink()
            Rate.create(
                {
                    "name": today,
                    "currency_id": currency.id,
                    "inverse_company_rate": value,
                    "company_id": cls.company.id,
                }
            )

        cls.acc_rec = cls._account("129900", "MF Receivable", "asset_receivable", True)
        cls.acc_inc = cls._account("409900", "MF Income", "income")
        cls.acc_tax = cls._account("209900", "MF Tax", "liability_current", True)
        cls.acc_bank = cls._account("109900", "MF Bank USD", "asset_cash")

        tax_group = cls.env["account.tax.group"].create(
            {
                "name": "IVA MF",
                "company_id": cls.company.id,
                "country_id": ve.id,
            }
        )
        cls.tax_excluded = cls._tax("IVA 16 MF excluido", tax_group, "tax_excluded")
        cls.tax_included = cls._tax("IVA 16 MF incluido", tax_group, "tax_included")

        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.sale_journal:
            # BD sin plan contable (CI): no hay diario de ventas.
            cls.sale_journal = cls.env["account.journal"].create(
                {
                    "name": "Ventas MF",
                    "code": "VMF",
                    "type": "sale",
                    "company_id": cls.company.id,
                    "default_account_id": cls.acc_inc.id,
                }
            )
        lines = cls.env["account.payment.method.line"]
        for xmlid, payment_type in (
            ("account.account_payment_method_manual_in", "inbound"),
            ("account.account_payment_method_manual_out", "outbound"),
        ):
            lines |= lines.create(
                {
                    "name": f"MF USD {payment_type}",
                    "payment_method_id": cls.env.ref(xmlid).id,
                    "payment_type": payment_type,
                    "payment_account_id": cls.acc_bank.id,
                }
            )
        cls.bank_usd = cls.env["account.journal"].create(
            {
                "name": "Banco USD MF",
                "code": "BUMF",
                "type": "bank",
                "currency_id": cls.usd.id,
                "default_account_id": cls.acc_bank.id,
                "company_id": cls.company.id,
                "payment_method": "20",
                "inbound_payment_method_line_ids": [
                    (6, 0, lines.filtered(lambda l: l.payment_type == "inbound").ids)
                ],
                "outbound_payment_method_line_ids": [
                    (6, 0, lines.filtered(lambda l: l.payment_type == "outbound").ids)
                ],
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto MF",
                "type": "service",
                "property_account_income_id": cls.acc_inc.id,
                "taxes_id": [(5, 0, 0)],
            }
        )
        cls.pricelist_usd = cls.env["product.pricelist"].create(
            {"name": "USD MF", "currency_id": cls.usd.id, "company_id": cls.company.id}
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Cliente MF",
                "property_account_receivable_id": cls.acc_rec.id,
            }
        )

    @classmethod
    def _account(cls, code, name, account_type, reconcile=False):
        account = cls.env["account.account"].search(
            [("code", "=", code), ("company_ids", "in", cls.company.id)], limit=1
        )
        return account or cls.env["account.account"].create(
            {
                "code": code,
                "name": name,
                "account_type": account_type,
                "company_ids": [(6, 0, cls.company.ids)],
                "reconcile": reconcile,
            }
        )

    @classmethod
    def _tax(cls, name, tax_group, price_include):
        repartition = [
            (0, 0, {"repartition_type": "base", "factor_percent": 100.0}),
            (
                0,
                0,
                {
                    "repartition_type": "tax",
                    "factor_percent": 100.0,
                    "account_id": cls.acc_tax.id,
                },
            ),
        ]
        return (
            cls.env["account.tax"]
            .with_company(cls.company)
            .create(
                {
                    "name": name,
                    "amount": 16.0,
                    "amount_type": "percent",
                    "type_tax_use": "sale",
                    "company_id": cls.company.id,
                    "tax_group_id": tax_group.id,
                    "price_include_override": price_include,
                    "fiscal_code": 1,
                    "invoice_repartition_line_ids": repartition,
                    "refund_repartition_line_ids": repartition,
                }
            )
        )

    def _invoice(self, currency, lines):
        in_usd = currency == self.usd
        move = (
            self.env["account.move"]
            .with_context(check_move_validity=False)
            .create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "currency_id": currency.id,
                    "journal_id": self.sale_journal.id,
                    "invoice_date": fields.Date.today(),
                    "company_id": self.company.id,
                    "pricelist_id": self.pricelist_usd.id if in_usd else False,
                    "invoice_line_ids": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.product.id,
                                "name": "L",
                                "quantity": quantity,
                                "price_unit": price,
                                "discount": discount,
                                "account_id": self.acc_inc.id,
                                "tax_ids": [(6, 0, tax.ids)],
                            },
                        )
                        for quantity, price, tax, discount in lines
                    ],
                }
            )
        )
        move.action_post()
        return move

    # ---- Ítem en Bs -------------------------------------------------------

    def test_company_item_rounds_unit_up_and_discounts_the_excess(self):
        item = self.env["account.move"]._mf_company_item
        self.assertEqual(item(10403.25, 1), {"price_unit": 10403.25, "discount_amount": 0.0})
        self.assertEqual(item(9318.74, 5), {"price_unit": 1863.75, "discount_amount": 0.01})
        self.assertEqual(item(9318.75, 5), {"price_unit": 1863.75, "discount_amount": 0.0})
        self.assertEqual(item(0.3, 3), {"price_unit": 0.1, "discount_amount": 0.0})
        self.assertEqual(item(8.03, 1000), {"price_unit": 0.01, "discount_amount": 1.97})
        self.assertEqual(item(0, 2), {"price_unit": 0.0, "discount_amount": 0.0})

    # ---- Líneas -----------------------------------------------------------

    def test_usd_invoice_excluded_tax_sends_company_base(self):
        """5 × $ 2,32 a 803,34: base del asiento Bs 9.318,74 → 5 × 1.863,75 − 0,01."""
        move = self._invoice(self.usd, [(5, 2.32, self.tax_excluded, 0)])
        line = move.invoice_line_ids
        self.assertAlmostEqual(abs(line.balance), 9318.74, places=2)
        (payload,) = move._mf_build_invoice_lines()
        self.assertEqual(payload["price_unit"], 1863.75)
        self.assertEqual(payload["discount_amount"], 0.01)
        self.assertEqual(payload["quantity"], 5)
        self.assertEqual(payload["tax"], 1)

    def test_usd_invoice_included_tax_sends_company_total(self):
        """IVA incluido (MF con tasa incluida): va el total con IVA, no la base."""
        move = self._invoice(self.usd, [(1, 12.45, self.tax_included, 0)])
        total = abs(move.amount_total_signed)
        self.assertAlmostEqual(total, 10001.58, places=2)
        (payload,) = move._mf_build_invoice_lines()
        self.assertEqual(payload["price_unit"], total)
        self.assertNotIn("discount_amount", payload)

    def test_usd_invoice_included_tax_lines_add_up_to_the_total(self):
        move = self._invoice(
            self.usd,
            [(3, 1.13, self.tax_included, 0), (7, 0.37, self.tax_included, 0)],
        )
        amount = sum(
            round(vals["price_unit"] * vals["quantity"], 2) - vals.get("discount_amount", 0.0)
            for vals in move._mf_build_invoice_lines()
        )
        self.assertAlmostEqual(amount, abs(move.amount_total_signed), places=2)

    def test_usd_invoice_discount_is_not_applied_twice(self):
        move = self._invoice(self.usd, [(2, 10.0, self.tax_excluded, 50)])
        (payload,) = move._mf_build_invoice_lines()
        # 2 × $ 10 − 50 % = $ 10 → Bs 8.033,40.
        self.assertEqual(payload["price_unit"], 4016.7)
        self.assertNotIn("discount_amount", payload)

    def test_company_currency_invoice_is_unchanged(self):
        move = self._invoice(self.vef, [(5, 1863.75, self.tax_excluded, 0)])
        (payload,) = move._mf_build_invoice_lines()
        self.assertEqual(payload["price_unit"], 1863.75)
        self.assertNotIn("discount_amount", payload)

    # ---- Pagos ------------------------------------------------------------

    def test_usd_invoice_payment_in_company_currency(self):
        move = self._invoice(self.usd, [(5, 2.32, self.tax_excluded, 0)])
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=move.ids
        ).create(
            {"journal_id": self.bank_usd.id, "payment_date": fields.Date.today()}
        )._create_payments()
        move.invalidate_recordset()
        payments = move._mf_build_payment_lines()
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0]["payment_method"], "20")
        self.assertAlmostEqual(payments[0]["amount"], abs(move.amount_total_signed), places=2)

    def test_usd_invoice_without_payments(self):
        move = self._invoice(self.usd, [(1, 1.0, self.tax_excluded, 0)])
        self.assertEqual(move._mf_build_payment_lines(), [{"amount": 0, "payment_method": "01"}])
