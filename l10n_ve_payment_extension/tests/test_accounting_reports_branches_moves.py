from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "accounting_reports_branches_moves")
class TestAccountingReportsBranchesMoves(TransactionCase):
    """Libros de ventas/compras con sucursales nativas de Odoo y documentos reales.

    Estructura: matriz (RIF X) con dos sucursales del mismo RIF y una compañía
    hija con otro RIF que no debe consolidarse.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.main = env.ref("base.main_company")
        cls.vef = env.ref("base.VEF")
        cls.usd = env.ref("base.USD")
        cls.main.write(
            {"currency_id": cls.vef.id, "foreign_currency_id": cls.usd.id, "vat": "J085025545"}
        )
        Company = env["res.company"]
        vals = {
            "currency_id": cls.vef.id,
            "foreign_currency_id": cls.usd.id,
            "country_id": cls.main.country_id.id,
            "account_fiscal_country_id": cls.main.account_fiscal_country_id.id,
        }
        cls.branch_a = Company.create(
            {"name": "Sucursal Carucieña", "parent_id": cls.main.id, "vat": "J-085025545", **vals}
        )
        cls.branch_b = Company.create(
            {"name": "Sucursal Cal", "parent_id": cls.main.id, "vat": "J085025545", **vals}
        )
        cls.other = Company.create(
            {"name": "Otro RIF", "parent_id": cls.main.id, "vat": "J999999999", **vals}
        )
        cls.companies = cls.main | cls.branch_a | cls.branch_b | cls.other
        env.user.company_ids |= cls.companies
        cls.env = env(context=dict(env.context, allowed_company_ids=cls.companies.ids))
        env = cls.env

        cls.tax_group = env["account.tax.group"].create({"name": "IVA 16% Branch TG"})
        cls.tax_sale = env["account.tax"].create(
            {
                "name": "IVA 16% Sale Branch",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.main.id,
                "tax_group_id": cls.tax_group.id,
            }
        )
        cls.tax_purchase = env["account.tax"].create(
            {
                "name": "IVA 16% Purchase Branch",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": cls.main.id,
                "tax_group_id": cls.tax_group.id,
            }
        )
        Account = env["account.account"]
        cls.account_revenue = Account.create(
            {"name": "Rev Branch", "code": "992001", "account_type": "income",
             "company_ids": [Command.set(cls.companies.ids)]}
        )
        cls.account_expense = Account.create(
            {"name": "Exp Branch", "code": "992002", "account_type": "expense",
             "company_ids": [Command.set(cls.companies.ids)]}
        )
        cls.account_receivable = Account.create(
            {"name": "Rec Branch", "code": "992003", "account_type": "asset_receivable",
             "reconcile": True, "company_ids": [Command.set(cls.companies.ids)]}
        )
        cls.account_payable = Account.create(
            {"name": "Pay Branch", "code": "992004", "account_type": "liability_payable",
             "reconcile": True, "company_ids": [Command.set(cls.companies.ids)]}
        )
        cls.partner = env["res.partner"].create({"name": "Cliente Branch", "vat": "V12345678"})
        for company in cls.companies:
            cls.partner.with_company(company).write(
                {
                    "property_account_receivable_id": cls.account_receivable.id,
                    "property_account_payable_id": cls.account_payable.id,
                }
            )
        cls.journals = {}
        for company in cls.companies:
            code = "B%d" % company.id
            cls.journals[company] = {
                "sale": env["account.journal"].create(
                    {"name": "Ventas %s" % company.name, "type": "sale", "code": code + "S",
                     "company_id": company.id, "default_account_id": cls.account_revenue.id}
                ),
                "purchase": env["account.journal"].create(
                    {"name": "Compras %s" % company.name, "type": "purchase", "code": code + "P",
                     "company_id": company.id, "default_account_id": cls.account_expense.id}
                ),
            }
        cls.product = env["product.product"].create(
            {"name": "Producto Branch", "type": "service", "list_price": 100}
        )

    def _post_move(self, company, move_type, correlative, days_ago=0, price=100):
        date = fields.Date.today() - timedelta(days=days_ago)
        journal = self.journals[company]["sale" if move_type.startswith("out") else "purchase"]
        tax = self.tax_sale if move_type.startswith("out") else self.tax_purchase
        move = self.env["account.move"].with_company(company).create(
            {
                "move_type": move_type,
                "partner_id": self.partner.id,
                "journal_id": journal.id,
                "correlative": correlative,
                "invoice_date": date,
                "date": date,
                "invoice_date_display": date,
                "currency_id": self.usd.id,
                "foreign_currency_id": self.vef.id,
                "foreign_rate": 38.0,
                "foreign_inverse_rate": 38.0,
                "manually_set_rate": True,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": price,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                ],
            }
        )
        move.with_context(move_action_post_alert=True).action_post()
        return move

    def _wizard(self, report, company=None, **kwargs):
        today = fields.Date.today()
        vals = {
            "report": report,
            "company_id": (company or self.main).id,
            "date_from": today - timedelta(days=30),
            "date_to": today,
        }
        vals.update(kwargs)
        return self.env["wizard.accounting.reports"].create(vals)

    def _create_sale_documents(self):
        self.m_main = self._post_move(self.main, "out_invoice", "00-0015559", days_ago=3)
        self.m_a = self._post_move(self.branch_a, "out_invoice", "CR-0000001", days_ago=2)
        self.m_b = self._post_move(self.branch_b, "out_invoice", "CL-0000001", days_ago=1)
        self.m_other = self._post_move(self.other, "out_invoice", "XX-0000001", days_ago=1)

    def _controls(self, wizard, parse):
        return [line["correlative"] for line in getattr(wizard, parse)()]

    def test_sale_book_consolidated(self):
        self._create_sale_documents()
        wizard = self._wizard("sale", branch_scope="all")
        self.assertTrue(wizard.has_branches)
        lines = wizard.parse_sale_book_data()
        self.assertEqual(
            [line["correlative"] for line in lines],
            ["00-0015559", "CR-0000001", "CL-0000001"],
            "Documentos de la matriz y las sucursales, ordenados por fecha y sin los de otro RIF",
        )

    def test_sale_book_main_only(self):
        self._create_sale_documents()
        wizard = self._wizard("sale", branch_scope="main")
        self.assertEqual(self._controls(wizard, "parse_sale_book_data"), ["00-0015559"])

    def test_sale_book_single_branch(self):
        self._create_sale_documents()
        wizard = self._wizard("sale", branch_scope="branch", branch_company_id=self.branch_a.id)
        self.assertEqual(self._controls(wizard, "parse_sale_book_data"), ["CR-0000001"])

    def test_sale_book_with_branch_as_active_company(self):
        self._create_sale_documents()
        wizard = self._wizard("sale", company=self.branch_a)
        self.assertFalse(wizard.has_branches)
        self.assertEqual(self._controls(wizard, "parse_sale_book_data"), ["CR-0000001"])

    def test_sale_book_resume_totals_are_consolidated(self):
        self._create_sale_documents()
        consolidated = self._wizard("sale", branch_scope="all")
        main_only = self._wizard("sale", branch_scope="main")
        moves = consolidated.search_moves()
        self.assertEqual(moves, self.m_main | self.m_a | self.m_b)
        total = sum(line["total_sales"] for line in consolidated.parse_sale_book_data())
        total_main = sum(line["total_sales"] for line in main_only.parse_sale_book_data())
        self.assertAlmostEqual(total, total_main * 3, places=2)

    def test_sale_book_includes_credit_note_of_branch(self):
        self._create_sale_documents()
        credit_note = self._post_move(self.branch_b, "out_refund", "CL-0000002", days_ago=0)
        wizard = self._wizard("sale", branch_scope="all")
        self.assertIn(credit_note, wizard.search_moves())

    def test_purchase_book_consolidated(self):
        self._post_move(self.main, "in_invoice", "00-99999900", days_ago=3)
        self._post_move(self.branch_a, "in_invoice", "00-99999901", days_ago=2)
        self._post_move(self.branch_b, "in_invoice", "00-99999902", days_ago=1)
        self._post_move(self.other, "in_invoice", "00-99999903", days_ago=1)
        wizard = self._wizard("purchase", branch_scope="all")
        self.assertEqual(
            self._controls(wizard, "parse_purchase_book_data"),
            ["00-99999900", "00-99999901", "00-99999902"],
        )
        main_only = self._wizard("purchase", branch_scope="main")
        self.assertEqual(self._controls(main_only, "parse_purchase_book_data"), ["00-99999900"])

    def test_sale_retention_of_branch_is_consolidated(self):
        self._create_sale_documents()
        today = fields.Date.today()
        retention = self.env["account.retention"].with_company(self.branch_a).create(
            {
                "type_retention": "iva",
                "type": "out_invoice",
                "company_id": self.branch_a.id,
                "partner_id": self.partner.id,
                "date": today,
                "date_accounting": today,
                "state": "emitted",
                "retention_line_ids": [
                    Command.create(
                        {
                            "move_id": self.m_a.id,
                            "name": "IVA Retention Line",
                            "invoice_total": self.m_a.amount_total,
                            "invoice_amount": self.m_a.amount_untaxed,
                            "retention_amount": self.m_a.amount_untaxed * 0.75,
                            "foreign_currency_rate": 1.0,
                            "foreign_invoice_amount": self.m_a.amount_untaxed,
                            "foreign_retention_amount": self.m_a.amount_untaxed * 0.75,
                        }
                    )
                ],
            }
        )
        consolidated = self._wizard("sale", branch_scope="all")
        self.assertIn(retention, consolidated._search_sale_retention_lines().mapped("retention_id"))
        main_only = self._wizard("sale", branch_scope="main")
        self.assertFalse(main_only._search_sale_retention_lines())
        branch_only = self._wizard(
            "sale", branch_scope="branch", branch_company_id=self.branch_a.id
        )
        self.assertTrue(branch_only._search_sale_retention_lines())

    def test_generate_xlsx_for_every_scope(self):
        self._create_sale_documents()
        self._post_move(self.main, "in_invoice", "00-99999900", days_ago=3)
        self._post_move(self.branch_a, "in_invoice", "00-99999901", days_ago=2)
        for scope, extra in (
            ("all", {}),
            ("main", {}),
            ("branch", {"branch_company_id": self.branch_a.id}),
        ):
            for report in ("sale", "purchase"):
                wizard = self._wizard(report, branch_scope=scope, **extra)
                generate = (
                    wizard.generate_sales_book if report == "sale" else wizard.generate_purchases_book
                )
                content = generate(wizard.company_id.id)
                self.assertTrue(content.startswith(b"PK"), (scope, report))
