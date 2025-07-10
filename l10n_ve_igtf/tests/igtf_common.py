from odoo.tests.common import TransactionCase
from odoo import fields, Command
import logging

_logger = logging.getLogger(__name__)


class IGTFTestCommon(TransactionCase):
    def setUp(self):
        super().setUp()
        Account = self.env["account.account"]
        Journal = self.env["account.journal"]

        self.company = self.env.ref("base.main_company")
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")

        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "currency_foreign_id": self.currency_vef.id,
            }
        )

        def account(code, ttype, name, recon=False):
            """auxiliar function whhich creates an account if it does not exist,avoiding duplicates."""
            account_founded = Account.search(
                [("code", "=", code), ("company_id", "=", self.company.id)], limit=1
            )
            if not account_founded:
                new_account = Account.create(
                    {
                        "name": name,
                        "code": code,
                        "account_type": ttype,
                        "reconcile": recon,
                        "company_id": self.company.id,
                    }
                )
            return new_account

        self.acc_receivable = account(
            "1101", "asset_receivable", "CxC", recon=True)
        self.acc_income = account("4001", "income", "Ingresos")
        self.acc_igtf_cli = account("236IGTF", "expense", "IGTF Clientes")

        self.company.write(
            {
                "igtf_percentage": 3.0,
                "customer_account_igtf_id": self.acc_igtf_cli.id,
            }
        )

        # -------- igtf_journal_id -------------------
        self.bank_journal_usd = self.env["account.journal"].search(
            [("type", "=", "bank"), ("currency_id", "=", self.currency_usd.id)], limit=1
        ) or self.env["account.journal"].create(
            {
                "name": "Banco USD",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
            }
        )
        self.bank_journal_usd.write({"is_igtf": True})

        def get_or_create(code, acc_type, name, reconcile=False):
            acc = Account.search(
                [("code", "=", code), ("company_id", "=", self.company.id)], limit=1
            )
            if not acc:
                acc = Account.create(
                    {
                        "name": name,
                        "code": code,
                        "account_type": acc_type,
                        "reconcile": reconcile,
                        "company_id": self.company.id,
                    }
                )
            return acc

        self.receivable_acc = get_or_create(
            "1101", "asset_receivable", "CxC Clientes", True
        )
        self.income_acc = get_or_create("4001", "income", "Ingresos Ventas")

        # advance liability account for customers (Venezuela ≃ "to be collected" → liability account)

        self.advance_cust_acc = get_or_create(
            "21600", "liability_current", "Anticipo Clientes", reconcile=True
        )
        self.advance_supp_acc = get_or_create(
            "13600", "asset_current", "Anticipo Proveedores", reconcile=True
        )

        self.company.write(
            {
                "advance_customer_account_id": self.advance_cust_acc.id,
                "advance_supplier_account_id": self.advance_supp_acc.id,
            }
        )

        # -------- Método de pago manual inbound -----------------------
        manual_in = self.env.ref("account.account_payment_method_manual_in")
        self.pm_line_in_usd = self.env["account.payment.method.line"].search(
            [
                ("journal_id", "=", self.bank_journal_usd.id),
                ("payment_method_id", "=", manual_in.id),
                ("payment_type", "=", "inbound"),
            ],
            limit=1,
        ) or self.env["account.payment.method.line"].create(
            {
                "name": "Manual Inbound USD",
                "journal_id": self.bank_journal_usd.id,
                "payment_method_id": manual_in.id,
                "payment_type": "inbound",
            }
        )

        # -------- Partner, producto y factura -------------------------
        self.partner = self.env["res.partner"].create(
            {"name": "Cliente IGTF", "vat": "J123"}
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Servicio",
                "list_price": 100,
                "property_account_income_id": self.acc_income.id,
            }
        )

        self.invoice = self._create_invoice_usd(1000.0)

    # ------------------------------------------------------------------
    # UTILITY: creates a customer invoice in USD for the given amount

    # ------------------------------------------------------------------
    def _create_invoice_usd(self, amount):
        line = Command.create(
            {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": amount,
            }
        )
        inv = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "currency_id": self.currency_usd.id,
                "journal_id": self.env["account.journal"]
                .search([("type", "=", "sale")], limit=1)
                .id,
                "invoice_line_ids": [line],
            }
        )
        inv.action_post()
        return inv

    def _create_payment(
        self,
        amount,
        *,
        currency=None,
        journal=None,
        is_igtf_on_foreign_exchange=False,
        fx_rate=None,
        fx_rate_inv=None,
        pm_line=None,
    ):
        currency = currency or self.currency_usd
        journal = journal or self.bank_journal_usd
        pm_line = pm_line or self.pm_line_in_usd
        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": amount,
            "currency_id": currency.id,
            "journal_id": journal.id,
            "payment_method_line_id": pm_line.id,
            "is_igtf_on_foreign_exchange": is_igtf_on_foreign_exchange,
            "date": fields.Date.today(),
        }
        if fx_rate:
            vals.update({"foreign_rate": fx_rate,
                        "foreign_inverse_rate": fx_rate_inv})

        pay = self.env["account.payment"].create(vals)
        pay.action_post()
        return pay
