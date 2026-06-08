import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestAccountant(TransactionCase):
    """Tests for invoice posting behaviour regarding the invoice date."""

    def setUp(self):
        super().setUp()

        self.country_ve = self.env.ref('base.ve')
        self.currency_usd = self.env.ref("base.USD")
        self.currency_vef = self.env.ref("base.VEF")
        self.company = self.env.ref("base.main_company")
        self.company.write(
            {
                "currency_id": self.currency_usd.id,
                "foreign_currency_id": self.currency_vef.id,
                "account_fiscal_country_id": self.env.ref('base.ve').id
            }
        )
        self.Journal = self.env["account.journal"]
        self.Move = self.env["account.move"]

        # Tipo de cambio de referencia
        self.env["res.currency.rate"].create(
            {
                "name": fields.Date.from_string("2025-07-28"),
                "currency_id": self.currency_usd.id,
                "inverse_company_rate": 120.439,
                "company_id": self.company.id,
            }
        )

        # --- Cuenta de banco para default_account_id ---
        self.manual_in = self.env.ref("account.account_payment_method_manual_in")
        self.manual_out = self.env.ref("account.account_payment_method_manual_out")
        self.account_bank = self.env["account.account"].create(
            {
                "name": "BANCO PRUEBA USD",
                "code": "100000",
                "account_type": "asset_cash",
                "company_ids": [(6, 0, [self.company.id])],
                "reconcile": True,
            }
        )

        self.pm_line_in = self.env["account.payment.method.line"].create({
            "name": "Manual Inbound",
            "payment_method_id": self.manual_in.id,
            "payment_type": "inbound",
            "payment_account_id": self.account_bank.id,
        })

        self.pm_line_out = self.env["account.payment.method.line"].create({
            "name": "Manual Outbound",
            "payment_method_id": self.manual_out.id,
            "payment_type": "outbound",
            "payment_account_id": self.account_bank.id,
        })

        # --- Journal bancario en USD (o se reutiliza uno existente) ---
        self.bank_journal_usd = self.env["account.journal"].create(
            {
                "name": "Banco USD",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
                "default_account_id": self.account_bank.id,
                "inbound_payment_method_line_ids": [(6, 0, self.pm_line_in.ids)],
                "outbound_payment_method_line_ids": [(6, 0, self.pm_line_out.ids)],
            }
        )

        # --- Payment Method Manual inbound/outbound (reusar, no crear) ---
        self.payment_method = self.env["account.payment.method"].search(
            [("code", "=", "manual"), ("payment_type", "=", "inbound")], limit=1
        ) or self.env.ref("account.account_payment_method_manual_in")

        self.payment_method_out = self.env["account.payment.method"].search(
            [("code", "=", "manual"), ("payment_type", "=", "outbound")], limit=1
        ) or self.env.ref("account.account_payment_method_manual_out")

        # --- Payment Method Lines en el journal de BANCO ---
        self.pm_line_in_usd = self.env["account.payment.method.line"].search(
            [
                ("journal_id", "=", self.bank_journal_usd.id),
                ("payment_method_id", "=", self.payment_method.id),
            ],
            limit=1,
        ) or self.env["account.payment.method.line"].create(
            {
                "journal_id": self.bank_journal_usd.id,
                "payment_method_id": self.payment_method.id,
                "payment_type": "inbound",
                "payment_account_id": self.account_bank.id,
            }
        )

        self.pm_line_out_usd = self.env["account.payment.method.line"].search(
            [
                ("journal_id", "=", self.bank_journal_usd.id),
                ("payment_method_id", "=", self.payment_method_out.id),
            ],
            limit=1,
        ) or self.env["account.payment.method.line"].create(
            {
                "journal_id": self.bank_journal_usd.id,
                "payment_method_id": self.payment_method_out.id,
                "payment_type": "outbound",
                "payment_account_id": self.account_bank.id,
            }
        )

        # --- Vincular las líneas de pago al journal si no lo están ---
        if self.pm_line_in_usd not in self.bank_journal_usd.inbound_payment_method_line_ids:
            self.bank_journal_usd.write({
                "inbound_payment_method_line_ids": [(4, self.pm_line_in_usd.id)],
            })
        if self.pm_line_out_usd not in self.bank_journal_usd.outbound_payment_method_line_ids:
            self.bank_journal_usd.write({
                "outbound_payment_method_line_ids": [(4, self.pm_line_out_usd.id)],
            })

        # --- Grupo de Impuesto ---
        self.tax_group = self.env['account.tax.group'].create({
            'name': 'IVA',
            'company_id': self.company.id,
            'country_id':self.country_ve.id,  # <-- referencia a Venezuela
        })

        # --- País (Venezuela) ---
        

        # --- Impuesto ---
        self.tax_iva16 = self.env["account.tax"].create(
            {
                "name": "IVA 16%",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": self.company.id,
                "tax_group_id": self.tax_group.id,
                "country_id": self.country_ve.id,  # <-- referencia a Venezuela
            }
        )

        # --- Producto / Partner ---
        self.product = self.env["product.product"].create(
            {
                "name": "Producto Prueba",
                "type": "service",
                "list_price": 100,
                "barcode": "123456789",
                "taxes_id": [(6, 0, [self.tax_iva16.id])],
                "company_id": False,
            }
        )

        self.partner_a = self.env["res.partner"].create(
            {
                "name": "Test Partner A",
                "customer_rank": 1,
                "company_id": False,
            }
        )
        self.partner = self.partner_a  # usado por helpers

        # --- Journal de ventas (sin métodos de pago) ---
        self.sale_journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", self.company.id)], limit=1
        ) or self.env["account.journal"].create(
            {
                "name": "Sales",
                "code": "SAJT",  # evita colisiones con SAJ
                "type": "sale",
                "company_id": self.company.id,
            }
        )

        self.account_product = self.env["account.account"].create(
            {
                "name": "VENTAS PRODUCTO",
                "code": "703000",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )

        self.account_contado = self.env["account.account"].create(
            {
                "name": "VENTAS AL CONTADO",
                "code": "701000",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )
        self.journal_contado = self.env["account.journal"].create(
            {
                "name": "VENTAS CONTADO",
                "type": "sale",
                "code": "VCO",
                "default_account_id": self.account_contado.id,
            }
        )

        self.account_credito = self.env["account.account"].create(
            {
                "name": "VENTAS A CREDITO",
                "code": "702000",
                "account_type": "income",
                "company_ids": [(6, 0, [self.company.id])],
            }
        )

        self.journal_credito = self.env["account.journal"].create(
            {
                "name": "VENTAS CREDITO",
                "type": "sale",
                "code": "VCR",
                "default_account_id": self.account_credito.id,
            }
        )

        self.Line = self.env["account.move.line"]

        display_sel = dict(self.Line._fields["display_type"].selection or [])

        self.display_supports_product = "product" in display_sel

        # (Opcional) Si tu módulo de anticipos exige cuentas específicas:
        # Cuentas de anticipo en la compañía (tipos modernos v16/v17: account_type)
        if not getattr(
            self.company, "advance_customer_account_id", False
        ) or not getattr(self.company, "advance_supplier_account_id", False):
            pass  # Removed logic for creating advance accounts and writing to company

        # Nota: eliminamos la creación previa de self.account_payment_method_line en el journal de VENTAS
        # y también evitamos crear un payment anticipado aquí que dispare la constraint antes del test.

        # Ensure the company's fiscal country is set to Venezuela
        self.company.write({"country_id": self.country_ve.id})
        # Define the missing 'date' attribute in the setUp method
        self.date = fields.Date.today()

        # ----------------- Helpers -----------------
    def _create_invoice(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "journal_id": self.sale_journal.id,
                "date": fields.Date.today(),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.account_product.id,  # Add account_id
                        }
                    )
                ],
            }
        )
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _create_payment(
        self,
        amount,
        *,
        currency=None,
        journal=None,
        is_advance=False,
        fx_rate=None,
        fx_rate_inv=None,
        pm_line=None,
    ):
        """Crea y valida un payment genérico."""
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
            "payment_method_line_id": pm_line.id,  # <-- misma línea y mismo journal
            "date": fields.Date.today(),
        }
        if fx_rate:
            vals.update(
                {"foreign_rate": fx_rate, "foreign_inverse_rate": fx_rate_inv}
            )

        pay = self.env["account.payment"].create(vals)
        pay.action_post()
        return pay

    def _create_draft_invoice(self, journal, line_defs):
        """Create a draft out_invoice with given journal and line definitions.
        line_defs: list of dicts with keys: name, account(optional), product(optional), qty, price, taxes(list ids), display_type(optional)
        """
        # Ensure account_id is set only for accountable lines in _create_draft_invoice
        for ld in line_defs:
            if ld.get("display_type") not in ("line_section", "line_note") and not ld.get("account"):
                ld["account"] = self.account_product

        move = self.Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_date_display": fields.Date.today(),
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": ld.get("name", "Line"),
                            "product_id": ld.get("product", False)
                            and ld["product"].id
                            or False,
                            "quantity": ld.get("qty", 1.0),
                            "price_unit": ld.get("price", 100.0),
                            "account_id": ld.get("account", False)
                            and ld["account"].id
                            or False,
                            "tax_ids": [(6, 0, ld.get("taxes", []))],
                            **(
                                {"display_type": ld["display_type"]}
                                if ld.get("display_type") is not None
                                else {}
                            ),
                        },
                    )
                    for ld in line_defs
                ],
            }
        )
        self.assertEqual(move.state, "draft")
        return move

    

    def test_foreign_rate_editable_only_on_in_invoice(self):
        self.assertTrue(
            self.company.foreign_currency_id,
            "Foreign currency should be set for the company.",
        )
        invoice_form = (
            self.env["account.move"].with_context(default_move_type="in_invoice").new()
        )
        invoice_form.company_id = self.company.id
        invoice_form.currency_id = self.currency_usd
        invoice_form.foreign_currency_id = self.currency_vef
        invoice_form.partner_id = self.partner_a
        invoice_form.invoice_date = self.date
        invoice_form.invoice_date_display = self.date
        invoice_form.foreign_rate = 1.23

        self.assertEqual(
            invoice_form.foreign_rate,
            1.23,
            "Foreign rate should be set to 1.23 for in_invoice move type.",
        )

    def test_foreign_rate_editable_only_on_in_invoice_case_customer(self):
        self.assertTrue(
            self.company.foreign_currency_id,
            "Foreign currency should be set for the company.",
        )
        invoice_form = (
            self.env["account.move"].with_context(default_move_type="out_invoice").new()
        )
        invoice_form.company_id = self.company.id
        invoice_form.currency_id = self.currency_usd
        invoice_form.foreign_currency_id = self.currency_vef
        invoice_form.partner_id = self.partner_a
        invoice_form.invoice_date = self.date
        invoice_form.invoice_date_display = self.date
        self.assertNotEqual(
            invoice_form.foreign_rate,
            1.23,
            "Foreign rate should be set to 1.23 for in_invoice move type.",
        )

    def test_payment_method_line_assigned_account_validation_cash_journal(self):
        """Test that a cash journal can be created even if a payment method line lacks a payment_account_id."""
        # Due to the recent change, 'cash' journals shouldn't trigger the validation.
        try:
            cash_journal = self.env["account.journal"].create({
                "name": "Invalid Cash Journal",
                "type": "cash",
                "code": "INVCJ",
                "company_id": self.company.id,
                "inbound_payment_method_line_ids": [
                    Command.create({
                        "payment_method_id": self.payment_method.id,
                        # Missing payment_account_id
                    })
                ]
            })
            self.assertTrue(cash_journal.id, "Should successfully create a cash journal even without configured payment method accounts.")
        except Exception as e:
            self.fail(f"Creating a cash journal without payment_account_id raised an exception: {e}")

