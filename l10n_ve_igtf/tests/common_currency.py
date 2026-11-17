from odoo import Command, fields
from odoo.tests import Form, TransactionCase

from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate


class CurrencyFixtureCommon(TransactionCase):
    """Fixture sin tests para facturas y pagos en varias monedas: compañía en VEF (USD alterna), cuentas,
    impuestos exentos, diarios de ventas/compras y de banco por moneda, y helpers de factura y pago.
    Tasas VEF por unidad (2026-01-01 / 2026-08-01): USD 40 / 36, EUR 50 / 45, JPY 0,27 / 0,25, KWD 130 / 120."""

    _bill_counter = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.ref("base.main_company")
        cls.vef = env.ref("base.VEF")
        cls.usd = env.ref("base.USD")
        cls.eur = env.ref("base.EUR")
        cls.jpy = env.ref("base.JPY")
        cls.kwd = env.ref("base.KWD")
        cls.company.write({
            "currency_id": cls.vef.id,
            "foreign_currency_id": cls.usd.id,
            "country_id": cls.company.country_id.id or env.ref("base.ve").id,
        })
        for currency, jan, aug in (
            (cls.usd, 40.0, 36.0), (cls.eur, 50.0, 45.0),
            (cls.jpy, 0.27, 0.25), (cls.kwd, 130.0, 120.0),
        ):
            currency.write({
                "active": True,
                "rate_ids": [
                    Command.create({"name": "2026-01-01", "company_rate": 1 / jan}),
                    Command.create({"name": "2026-08-01", "company_rate": 1 / aug}),
                ],
            })
            # Posting a payment/entry looks up the rate of the day it runs
            set_rate(env, currency, fields.Date.today(), cls.company, aug)

        Account = env["account.account"]
        company_ids = [Command.set([cls.company.id])]
        cls.acc_receivable = Account.create({
            "name": "CxC Prueba Widget", "code": "1101WGT",
            "account_type": "asset_receivable", "reconcile": True, "company_ids": company_ids,
        })
        cls.acc_payable = Account.create({
            "name": "CxP Prueba Widget", "code": "2101WGT",
            "account_type": "liability_payable", "reconcile": True, "company_ids": company_ids,
        })
        acc_income = Account.create({
            "name": "Ingresos Prueba Widget", "code": "4001WGT",
            "account_type": "income", "company_ids": company_ids,
        })
        acc_expense = Account.create({
            "name": "Gastos Prueba Widget", "code": "5001WGT",
            "account_type": "expense", "company_ids": company_ids,
        })
        acc_gain = Account.create({
            "name": "Ganancia Cambiaria Prueba Widget", "code": "7601WGT",
            "account_type": "income_other", "company_ids": company_ids,
        })
        acc_loss = Account.create({
            "name": "Pérdida Cambiaria Prueba Widget", "code": "6601WGT",
            "account_type": "expense", "company_ids": company_ids,
        })
        exchange_journal = env["account.journal"].create({
            "name": "Diferencial Cambiario Prueba Widget", "type": "general",
            "code": "EXCHW", "company_id": cls.company.id,
        })
        cls.company.write({
            "income_currency_exchange_account_id": acc_gain.id,
            "expense_currency_exchange_account_id": acc_loss.id,
            "currency_exchange_journal_id": exchange_journal.id,
        })

        tax_group = env["account.tax.group"].create({
            "name": "IVA Prueba Widget", "country_id": cls.company.country_id.id,
        })
        sale_tax = env["account.tax"].create({
            "name": "IVA exento venta (Prueba Widget)", "amount": 0, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": cls.company.id,
            "tax_group_id": tax_group.id, "country_id": cls.company.country_id.id,
        })
        purchase_tax = env["account.tax"].create({
            "name": "IVA exento compra (Prueba Widget)", "amount": 0, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": cls.company.id,
            "tax_group_id": tax_group.id, "country_id": cls.company.country_id.id,
        })
        cls.company.exent_aliquot_sale = sale_tax.id
        cls.product = env["product.product"].create({
            "name": "Servicio Prueba Widget", "type": "service",
            "taxes_id": [Command.set(sale_tax.ids)],
            "supplier_taxes_id": [Command.set(purchase_tax.ids)],
            "property_account_income_id": acc_income.id,
            "property_account_expense_id": acc_expense.id,
        })
        cls.partner = env["res.partner"].create({"name": "Cliente Prueba Widget"})
        cls.partner.property_product_pricelist = False
        cls.partner.property_account_receivable_id = cls.acc_receivable.id
        cls.partner.property_account_payable_id = cls.acc_payable.id

        cls.sale_journal = env["account.journal"].create({
            "name": "Ventas Prueba Widget", "type": "sale", "code": "VWGT",
            "company_id": cls.company.id, "refund_sequence": True,
        })
        cls.purchase_journal = env["account.journal"].create({
            "name": "Compras Prueba Widget", "type": "purchase", "code": "CWGT",
            "company_id": cls.company.id,
        })
        cls.bank = {
            currency.name: cls._create_bank_journal(currency, f"B{currency.name}W")
            for currency in (cls.vef, cls.usd, cls.eur, cls.jpy, cls.kwd)
        }

    @classmethod
    def _create_bank_journal(cls, currency, code):
        account = cls.env["account.account"].create({
            "name": f"Banco {currency.name} Prueba Widget",
            "code": f"{code}01",
            "account_type": "asset_cash",
            "currency_id": currency.id if currency != cls.vef else False,
        })
        values = {
            "name": f"Banco {currency.name} Prueba Widget",
            "type": "bank", "code": code, "company_id": cls.company.id,
            "default_account_id": account.id,
            "inbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                "name": "Manual",
                "payment_method_id": cls.env.ref("account.account_payment_method_manual_in").id,
                "payment_account_id": account.id,
            })],
            "outbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                "name": "Manual",
                "payment_method_id": cls.env.ref("account.account_payment_method_manual_out").id,
                "payment_account_id": account.id,
            })],
        }
        if currency != cls.vef:
            values["currency_id"] = currency.id
        return cls.env["account.journal"].create(values)


    def _invoice(self, date, price, currency=None, move_type="out_invoice", term=None):
        """Factura o bono posteado, en moneda de la compañía si `currency` es None.
        Fija el diario antes de la moneda y el nombre del proveedor después del diario:
        su onchange reasigna ambos."""
        journal = self.sale_journal if move_type == "out_invoice" else self.purchase_journal
        with Form(self.env["account.move"].with_context(default_move_type=move_type)) as form:
            form.partner_id = self.partner
            form.invoice_date = date
            form.journal_id = journal
            if currency:
                form.currency_id = currency
            if move_type == "in_invoice":
                type(self)._bill_counter += 1
                form.name = f"PROV-WGT-{self._bill_counter:04d}"
        move = form.save()
        with Form(move) as form:
            if term:
                form.invoice_payment_term_id = term
            with form.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = price
        move = form.save()
        move.with_context(move_action_post_alert=True).action_post()
        return move

    def _outstanding_line(self, journal, amount, currency, date, payment_type="inbound"):
        """Pago posteado SIN conciliar; devuelve su línea por cobrar/pagar."""
        payment = self.env["account.payment"].create({
            "payment_type": payment_type,
            "partner_type": "customer" if payment_type == "inbound" else "supplier",
            "partner_id": self.partner.id,
            "amount": amount,
            "currency_id": currency.id,
            "journal_id": journal.id,
            "date": date,
        })
        payment.action_post()
        return payment.move_id.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable")
        )
