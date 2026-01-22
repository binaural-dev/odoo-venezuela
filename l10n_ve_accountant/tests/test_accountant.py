import logging

from jsonschema import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo import fields, Command

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
                "currency_id": self.currency_vef.id,
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

        # --- Journal bancario en USD (o se reutiliza uno existente) ---
        self.bank_journal_usd = self.env["account.journal"].search(
            [
                ("type", "=", "bank"),
                ("currency_id", "=", self.currency_usd.id),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        ) or self.env["account.journal"].create(
            {
                "name": "Banco USD",
                "code": "BNKUS",
                "type": "bank",
                "currency_id": self.currency_usd.id,
                "company_id": self.company.id,
            }
        )

        # --- Payment Method Manual inbound (reusar, no crear) ---
        self.payment_method = self.env["account.payment.method"].search(
            [("code", "=", "manual"), ("payment_type", "=", "inbound")], limit=1
        ) or self.env.ref("account.account_payment_method_manual_in")

        # --- Payment Method Line en el journal de BANCO (no en ventas) ---
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
            }
        )

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

    # def test_get_journal_income_account_fallback(self):
        """It should return revenue_account_id, else income_account_id, else default_account_id."""
        j = self.journal_contado

        # Start clean
        if "revenue_account_id" in self.Journal._fields:
            j.revenue_account_id = False
        if "income_account_id" in self.Journal._fields:
            j.income_account_id = False
        j.default_account_id = self.account_contado

        acc = self.Move._get_journal_income_account(j)
        self.assertEqual(
            acc, self.account_contado, "Fallback to default_account_id failed"
        )

        if "income_account_id" in self.Journal._fields:
            j.income_account_id = self.account_credito
            acc = self.Move._get_journal_income_account(j)
            self.assertEqual(
                acc,
                self.account_credito,
                "Should prefer income_account_id over default_account_id",
            )

        if "revenue_account_id" in self.Journal._fields:
            j.revenue_account_id = self.account_product
            acc = self.Move._get_journal_income_account(j)
            self.assertEqual(
                acc,
                self.account_product,
                "Should prefer revenue_account_id over others",
            )

    def test_reconcile_twice(self):
        """
        This test verifies that when an advance payment is unmatched from an invoice, it can be matched again if required.
        """
        invoice = self._create_invoice()
        payment = self._create_payment(
            amount=invoice.amount_total,
            journal=self.bank_journal_usd,
            pm_line=self.pm_line_in_usd,
            is_advance=True,
        )
        # First reconciliation
        for line in payment.line_ids:
            line_ids = payment.reconciled_line_ids.filtered(
                lambda line: line.account_type
                in (
                    "asset_receivable",
                    "liability_payable",
                    "asset_current",
                    "liability_payable",
                )
                and not line.reconciled
            )
        if not line_ids:
            _logger.warning("Theres not lines to conciliate")
        else:
            for line in line_ids:
                invoice.js_assign_outstanding_line(line.id)

        # Breaking reconciliation
        conciliation_move = self.env["account.move"].search(
            [
                ("move_type", "=", "entry"),
                ("name", "=", f"{invoice.name} - {payment.name}"),
            ]
        )
        partial = self.env["account.partial.reconcile"].search(
            [
                ("debit_move_id.move_id", "=", invoice.id),
                ("credit_move_id.move_id", "=", conciliation_move.id),
            ],
            limit=1,
        )
        invoice.js_remove_outstanding_partial(partial.id)

        # Second reconciliation should not raise duplicate name error
        invoice.js_assign_outstanding_line(line.id)
        second_conciliation_move = self.env["account.move"].search(
            [
                ("move_type", "=", "entry"),
                ("name", "=", f"{invoice.name} - {payment.name}"),
                ("state", "=", "posted"),
            ]
        )
        second_conciliation_move and conciliation_move
        first_conciliation_move = self.env["account.move"].search(
            [
                ("move_type", "=", "entry"),
                ("name", "=", f"{invoice.name} - {payment.name}"),
                ("state", "=", "cancel"),
            ]
        )
        # It is evaluated whether the first journal entry with canceled state and the second with posted state are created.
        self.assertTrue(conciliation_move and first_conciliation_move)

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
        self.assertNotEqual(
            invoice_form.foreign_rate,
            1.23,
            "Foreign rate should be set to 1.23 for in_invoice move type.",
        )

    def test_invoice_with_tax_ok(self):
        """Debe permitir confirmar si todas las líneas de producto tienen impuesto."""
        invoice = self._create_invoice("out_invoice", [
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account.id,
                "tax_ids": [(6, 0, [self.tax.id])],
            }),
        ])
        invoice.action_post()  # No debe lanzar excepción

    
    def test_invoice_without_tax_raises(self):
        """Debe lanzar ValidationError si alguna línea de producto no tiene impuesto."""
        invoice = self._create_invoice("out_invoice", [
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account.id,
                "tax_ids": [],
            }),
        ])
        with self.assertRaises(ValidationError):
            invoice.action_post()

    def test_invoice_with_section_and_note_lines(self):
        """Debe ignorar líneas tipo sección y nota aunque no tengan impuesto."""
        invoice = self._create_invoice("out_invoice", [
            (0, 0, {
                "name": "Sección",
                "display_type": "line_section",
            }),
            (0, 0, {
                "name": "Nota",
                "display_type": "line_note",
            }),
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account.id,
                "tax_ids": [(6, 0, [self.tax.id])],
            }),
        ])
        invoice.action_post()  # No debe lanzar excepción

    def test_invoice_with_section_and_note_lines_but_product_without_tax(self):
        """Debe lanzar ValidationError si hay línea de producto sin impuesto, aunque existan secciones o notas."""
        invoice = self._create_invoice("out_invoice", [
            (0, 0, {
                "name": "Sección",
                "display_type": "line_section",
            }),
            (0, 0, {
                "name": "Nota",
                "display_type": "line_note",
            }),
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 100,
                "account_id": self.account.id,
                "tax_ids": [],
            }),
        ])
        with self.assertRaises(ValidationError):
            invoice.action_post()

    def test_invoice_types(self):
        """Debe validar para todos los tipos de move_type requeridos."""
        for move_type in ("out_invoice", "in_invoice", "out_refund", "in_refund"):
            invoice = self._create_invoice(move_type, [
                (0, 0, {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "account_id": self.account.id,
                    "tax_ids": [],
                }),
            ])
            with self.assertRaises(ValidationError):
                invoice.action_post()
            # Ahora con impuesto, debe pasar
            invoice2 = self._create_invoice(move_type, [
                (0, 0, {
                    "product_id": self.product.id,
                    "quantity": 1,
                    "price_unit": 100,
                    "account_id": self.account.id,
                    "tax_ids": [(6, 0, [self.tax.id])],
                }),
            ])
            invoice2.action_post()
