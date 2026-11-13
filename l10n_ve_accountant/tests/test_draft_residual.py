from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_draft_residual")
class TestDraftResidual(TransactionCase):
    """A draft invoice saved in steps (the empty draft first, the lines in a
    later write: what the form does) must keep its residual. Computing the
    totals used to read `amount_total_signed`, whose compute reads `tax_totals`
    -- the field being computed -- and got False back: the residual was stored
    as 0 and the draft showed as "Paid"."""

    def setUp(self):
        super().setUp()
        usd = self.env.ref("base.USD")
        vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        ve = self.env.ref("base.ve")
        self.company.write(
            {
                "currency_id": vef.id,
                "foreign_currency_id": usd.id,
                "account_fiscal_country_id": ve.id,
                "country_id": ve.id,
            }
        )
        today = fields.Date.today()
        self.env["res.currency.rate"].create(
            {"name": today, "currency_id": vef.id, "inverse_company_rate": 1.0, "company_id": self.company.id}
        )
        self.env["res.currency.rate"].create(
            {"name": today, "currency_id": usd.id, "inverse_company_rate": 40.0, "company_id": self.company.id}
        )
        self.acc_rec = self._account("120000", "Receivable", "asset_receivable", reconcile=True)
        self.acc_inc = self._account("400000", "Income", "income")
        self.acc_tax = self._account("200000", "Tax Payable", "liability_current", reconcile=True)
        tax_group = self.env["account.tax.group"].create(
            {"name": "IVA", "company_id": self.company.id, "country_id": ve.id}
        )
        repartition = lambda: [  # noqa: E731
            (0, 0, {"repartition_type": "base", "factor_percent": 100.0}),
            (0, 0, {"repartition_type": "tax", "factor_percent": 100.0, "account_id": self.acc_tax.id}),
        ]
        self.tax_16 = self.env["account.tax"].with_company(self.company).create(
            {
                "name": "IVA 16%",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": tax_group.id,
                "invoice_repartition_line_ids": repartition(),
                "refund_repartition_line_ids": repartition(),
            }
        )
        self.partner = self.env["res.partner"].with_company(self.company).create(
            {"name": "Test Partner", "property_account_receivable_id": self.acc_rec.id}
        )
        self.product = self.env["product.product"].with_company(self.company).create(
            {
                "name": "Test Product",
                "type": "consu",
                "list_price": 100.0,
                "property_account_income_id": self.acc_inc.id,
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
            }
        )

    def _account(self, code, name, account_type, reconcile=False):
        account = self.env["account.account"].with_company(self.company).search(
            [("code", "=", code), ("company_ids", "in", [self.company.id])], limit=1
        )
        return account or self.env["account.account"].with_company(self.company).create(
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "reconcile": reconcile,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )

    def _line(self, price=100.0):
        return Command.create(
            {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": price,
                "tax_ids": [Command.set(self.tax_16.ids)],
            }
        )

    def _draft_by_steps(self, prices=(100.0, 200.0)):
        move = self.env["account.move"].with_context(default_move_type="out_invoice").create({})
        move.write({"partner_id": self.partner.id})
        move.write({"invoice_line_ids": [self._line(price) for price in prices]})
        self.env.flush_all()
        self.env.invalidate_all()
        return move

    def test_residual_of_a_draft_created_by_steps(self):
        move = self._draft_by_steps()
        self.assertAlmostEqual(move.amount_total, 348.0, 2)
        self.assertAlmostEqual(move.amount_residual, 348.0, 2)
        self.assertEqual(move.payment_state, "not_paid")

    def test_residual_follows_a_later_change_of_the_lines(self):
        move = self._draft_by_steps()
        move.invoice_line_ids[:1].write({"price_unit": 400.0})
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertAlmostEqual(move.amount_total, 696.0, 2)
        self.assertAlmostEqual(move.amount_residual, 696.0, 2)
        self.assertEqual(move.payment_state, "not_paid")

    def test_residual_of_a_draft_created_with_its_lines(self):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [self._line(100.0), self._line(200.0)],
            }
        )
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertAlmostEqual(move.amount_residual, 348.0, 2)
        self.assertEqual(move.payment_state, "not_paid")

    def test_posted_invoice_residual_and_company_total(self):
        move = self._draft_by_steps()
        move.with_context(move_action_post_alert=True).action_post()
        self.assertAlmostEqual(move.amount_residual, 348.0, 2)
        self.assertAlmostEqual(abs(move.amount_total_signed), 348.0, 2)
        self.assertEqual(move.payment_state, "not_paid")

    def test_company_total_of_the_widget_in_draft_and_posted(self):
        move = self._draft_by_steps()
        draft_total = move.tax_totals["formatted_total_amount_currency_ves"]
        move.with_context(move_action_post_alert=True).action_post()
        move.invalidate_recordset(["tax_totals"])
        self.assertEqual(draft_total, move.tax_totals["formatted_total_amount_currency_ves"])
