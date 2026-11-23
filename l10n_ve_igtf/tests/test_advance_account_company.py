from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "l10n_ve_igtf_advance_account_company")
class TestAdvanceAccountCompany(TransactionCase):
    """La cuenta de anticipos sale de la compañía del documento, no de la que el contacto
    compartido tenga guardada (default_advance_*_account_id no depende de la compañía)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vef = cls.env.ref("base.VEF")
        cls.usd = cls.env.ref("base.USD")
        cls.vef.active = True
        cls.usd.active = True
        companies = cls.env["res.company"]
        for name in ("Compania A", "Compania B"):
            companies |= companies.create({
                "name": name,
                "currency_id": cls.vef.id,
                "foreign_currency_id": cls.usd.id,
            })
        cls.company_a, cls.company_b = companies
        cls.env.user.company_ids |= companies
        today = fields.Date.context_today(cls.env.user)
        for company in companies:
            for currency, rate in ((cls.usd, 1.0 / 40.0), (cls.vef, 1.0)):
                cls.env["res.currency.rate"].create({
                    "currency_id": currency.id,
                    "company_id": company.id,
                    "name": today,
                    "rate": rate,
                })
        cls.accounts = {}
        for company in companies:
            cls.accounts[company] = {
                "customer": cls._account(company, "liability_current", "ANTCLI"),
                "supplier": cls._account(company, "asset_current", "ANTPRO"),
            }
            company.write({
                "advance_customer_account_id": cls.accounts[company]["customer"].id,
                "advance_supplier_account_id": cls.accounts[company]["supplier"].id,
            })
        # contacto compartido con las cuentas de A (lo que dejó la migración / el default)
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente compartido",
            "company_id": False,
            "default_advance_customer_account_id": cls.accounts[cls.company_a]["customer"].id,
            "default_advance_supplier_account_id": cls.accounts[cls.company_a]["supplier"].id,
        })
        bank_account = cls._account(cls.company_b, "asset_cash", "BANCO")
        cls.journal_b = cls.env["account.journal"].create({
            "name": "Banco B",
            "code": "BNKB",
            "type": "bank",
            "company_id": cls.company_b.id,
            "default_account_id": bank_account.id,
        })
        cls.user_b = new_test_user(
            cls.env,
            login="usuario_solo_b",
            groups="account.group_account_manager",
            company_id=cls.company_b.id,
            company_ids=[(6, 0, cls.company_b.ids)],
        )

    @classmethod
    def _account(cls, company, account_type, code):
        return cls.env["account.account"].with_company(company).create({
            "name": f"{code} {company.name}",
            "code": f"{code}{company.id}",
            "account_type": account_type,
            "company_ids": [(6, 0, company.ids)],
            "reconcile": account_type != "asset_cash",
            "is_advance_account": account_type != "asset_cash",
        })

    def _advance_payment(self, env, partner_type="customer"):
        return env["account.payment"].create({
            "payment_type": "inbound" if partner_type == "customer" else "outbound",
            "partner_type": partner_type,
            "partner_id": self.partner.id,
            "amount": 100.0,
            "journal_id": self.journal_b.id,
            "is_advance_payment": True,
        })

    def test_partner_account_of_other_company_uses_document_company(self):
        for partner_type in ("customer", "supplier"):
            account = self.partner._l10n_ve_get_advance_account(self.company_b, partner_type)
            self.assertEqual(account, self.accounts[self.company_b][partner_type])

    def test_partner_account_of_same_company_is_kept(self):
        account = self.partner._l10n_ve_get_advance_account(self.company_a, "customer")
        self.assertEqual(account, self.accounts[self.company_a]["customer"])

    def test_partner_without_account_uses_company(self):
        partner = self.env["res.partner"].create({"name": "Sin cuenta", "company_id": False})
        partner.default_advance_customer_account_id = False
        account = partner._l10n_ve_get_advance_account(self.company_b, "customer")
        self.assertEqual(account, self.accounts[self.company_b]["customer"])

    def test_advance_payment_without_access_to_partner_account_company(self):
        """Caso reportado: el usuario solo ve la compañía B y el contacto tiene la cuenta de A.
        Antes: error de acceso a account.account. Ahora: anticipo con la cuenta de B."""
        env_b = self.env(user=self.user_b, context={"allowed_company_ids": self.company_b.ids})
        payment = self._advance_payment(env_b)
        self.assertEqual(
            payment.sudo().destination_account_id, self.accounts[self.company_b]["customer"]
        )

    def test_several_advance_payments_all_computed(self):
        """_compute_destination_account_id salía del ciclo con return tras el primer anticipo."""
        payments = self._advance_payment(self.env) | self._advance_payment(self.env, "supplier")
        payments.invalidate_recordset(["destination_account_id"])
        payments._compute_destination_account_id()
        self.assertEqual(
            payments.mapped("destination_account_id"),
            self.accounts[self.company_b]["customer"] | self.accounts[self.company_b]["supplier"],
        )

    def test_igtf_apply_uses_document_company(self):
        self.company_b.taxpayer_type = "special"
        partner = self.env["res.partner"].create({"name": "Sin cuenta", "company_id": False})
        partner.default_advance_customer_account_id = False
        self.company_a.advance_customer_account_id = False
        self.assertFalse(partner._check_igtf_apply_improved("out_invoice", self.company_a))
        self.assertTrue(partner._check_igtf_apply_improved("out_invoice", self.company_b))
