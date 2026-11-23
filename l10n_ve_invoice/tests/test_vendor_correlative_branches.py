from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestVendorCorrelativeBranches(TransactionCase):
    """The vendor control number rule with native Odoo branches (child
    companies): it applies inside each branch and across the branches of the
    same main company, because the vendor numbers its invoices regardless of
    the branch that receives them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env.ref("base.main_company")
        cls.parent.currency_id = cls.env.ref("base.VEF")
        cls.parent.foreign_currency_id = cls.env.ref("base.USD")
        cls.branch_a = cls._create_branch("Sucursal A", "BRA")
        cls.branch_b = cls._create_branch("Sucursal B", "BRB")
        cls.env.user.company_ids |= cls.branch_a | cls.branch_b
        Account = cls.env["account.account"]
        cls.expense = Account.create(
            {"name": "Gasto sucursales", "code": "992003", "account_type": "expense",
             "company_ids": [(6, 0, [cls.parent.id])]}
        )
        cls.payable = Account.create(
            {"name": "Por pagar sucursales", "code": "992004",
             "account_type": "liability_payable", "reconcile": True,
             "company_ids": [(6, 0, [cls.parent.id])]}
        )
        cls.vendor = cls.env["res.partner"].create({"name": "Proveedor sucursales"})
        for company in (cls.parent, cls.branch_a, cls.branch_b):
            cls.vendor.with_company(company).property_account_payable_id = cls.payable
        # Rates only exist on the main company; branches use the parent's.
        usd = cls.env.ref("base.USD")
        Rate = cls.env["res.currency.rate"]
        if not Rate.search_count(
            [("name", "=", fields.Date.today()), ("currency_id", "=", usd.id),
             ("company_id", "=", cls.parent.id)]
        ):
            Rate.create(
                {"name": fields.Date.today(), "currency_id": usd.id,
                 "inverse_company_rate": 500.0, "company_id": cls.parent.id}
            )
        cls.tax = {}
        cls.product = {}
        cls.journal = {}
        for company in (cls.branch_a, cls.branch_b):
            tax_group = cls.env["account.tax.group"].create(
                {"name": f"IVA {company.name}", "company_id": company.id}
            )
            cls.tax[company.id] = cls.env["account.tax"].create(
                {"name": f"IVA {company.name}", "amount": 16, "amount_type": "percent",
                 "type_tax_use": "purchase", "company_id": company.id,
                 "tax_group_id": tax_group.id}
            )
            cls.product[company.id] = cls.env["product.product"].with_company(company).create(
                {"name": f"Servicio {company.name}", "type": "service", "company_id": company.id,
                 "property_account_expense_id": cls.expense.id,
                 "supplier_taxes_id": [(6, 0, [cls.tax[company.id].id])]}
            )
            cls.journal[company.id] = cls.env["account.journal"].create(
                {"name": f"Compras {company.name}", "type": "purchase",
                 "code": f"P{company.id}", "company_id": company.id,
                 "default_account_id": cls.expense.id}
            )

    @classmethod
    def _create_branch(cls, name, code):
        return cls.env["res.company"].create(
            {"name": name, "parent_id": cls.parent.id,
             "currency_id": cls.env.ref("base.VEF").id,
             "foreign_currency_id": cls.env.ref("base.USD").id}
        )

    def _bill(self, company, number, correlative, post=False):
        Move = self.env["account.move"].with_company(company).with_context(
            allowed_company_ids=[company.id],
            default_move_type="in_invoice",
            default_journal_id=self.journal[company.id].id,
        )
        with Form(Move) as form:
            form.partner_id = self.vendor
            form.name = number
            form.correlative = correlative
            form.invoice_date = fields.Date.today()
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product[company.id]
                line.quantity = 1
                line.price_unit = 100
        move = form.save()
        self.assertEqual(move.company_id, company)
        if post:
            move.action_post()
            self.env.flush_all()
        return move

    def test_same_control_with_another_bill_number_inside_a_branch(self):
        self._bill(self.branch_a, "0001", "00001", post=True)
        second = self._bill(self.branch_a, "0002", "00001", post=True)
        self.assertEqual(second.state, "posted")

    def test_exact_duplicate_inside_a_branch_is_blocked(self):
        first = self._bill(self.branch_a, "0001", "00001", post=True)
        with self.assertRaises(ValidationError) as caught:
            self._bill(self.branch_a, "0001", "00001", post=True)
        self.assertIn(first.name, str(caught.exception))

    def test_drafts_inside_a_branch_are_blocked_when_confirmed(self):
        first = self._bill(self.branch_a, "0001", "00001")
        second = self._bill(self.branch_a, "0001", "00001")
        first.action_post()
        with self.assertRaises(ValidationError):
            second.action_post()

    def test_same_bill_in_another_branch_is_blocked(self):
        """The vendor numbers its invoices regardless of the branch that
        receives them: the same invoice loaded in two branches is a duplicate."""
        first = self._bill(self.branch_a, "0001", "00001", post=True)
        with self.assertRaises(ValidationError) as caught:
            self._bill(self.branch_b, "0001", "00001", post=True)
        self.assertIn(first.name, str(caught.exception))

    def test_drafts_in_different_branches_are_blocked_when_confirmed(self):
        first = self._bill(self.branch_a, "0001", "00001")
        second = self._bill(self.branch_b, "0001", "00001")
        first.action_post()
        with self.assertRaises(ValidationError):
            second.action_post()

    def test_drafts_in_different_branches_confirmed_together_are_blocked(self):
        first = self._bill(self.branch_a, "0001", "00001")
        second = self._bill(self.branch_b, "0001", "00001")
        with self.assertRaises(ValidationError):
            (first | second).action_post()

    def test_other_bill_number_or_other_vendor_in_another_branch_is_allowed(self):
        self._bill(self.branch_a, "0001", "00001", post=True)
        other_number = self._bill(self.branch_b, "0002", "00001", post=True)
        self.assertEqual(other_number.state, "posted")
        other_vendor = self.env["res.partner"].create({"name": "Otro proveedor"})
        for company in (self.parent, self.branch_a, self.branch_b):
            other_vendor.with_company(company).property_account_payable_id = self.payable
        Move = self.env["account.move"].with_company(self.branch_b).with_context(
            allowed_company_ids=[self.branch_b.id], default_move_type="in_invoice",
            default_journal_id=self.journal[self.branch_b.id].id,
        )
        with Form(Move) as form:
            form.partner_id = other_vendor
            form.name = "0001"
            form.correlative = "00001"
            form.invoice_date = fields.Date.today()
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product[self.branch_b.id]
                line.quantity = 1
                line.price_unit = 100
        other = form.save()
        other.action_post()
        self.assertEqual(other.state, "posted")

    def test_user_restricted_to_one_branch_still_detects_the_duplicate(self):
        """A user that only sees its own branch cannot read the bills of the
        others, so the search must not depend on the user's access."""
        first = self._bill(self.branch_a, "0001", "00001")
        second = self._bill(self.branch_b, "0001", "00001")
        first.action_post()
        user = self.env["res.users"].create(
            {"name": "Contador sucursal B", "login": "contador_sucursal_b",
             "company_id": self.branch_b.id, "company_ids": [(6, 0, [self.branch_b.id])],
             "group_ids": [(6, 0, [self.env.ref("account.group_account_invoice").id])]}
        )
        as_user = self.env["account.move"].with_user(user).with_context(
            allowed_company_ids=[self.branch_b.id]
        )
        self.assertFalse(
            as_user.search([("id", "=", first.id)]),
            "Precondition: the user cannot see the other branch's bill",
        )
        repeated = second.with_user(user).with_context(
            allowed_company_ids=[self.branch_b.id]
        )._get_repeated_vendor_bill()
        self.assertEqual(repeated.id, first.id)
