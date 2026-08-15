from odoo.tests import tagged, TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import Command


@tagged("post_install", "-at_install")
class TestIgtfNoteDebitConfig(TransactionCase):
    """Cobertura de los campos/computes de configuración por compañía
    (res.company, res.config.settings) del modo 'Nota de Débito'."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.currency_usd = cls.env.ref("base.USD")

        cls.exempt_sale_tax = cls.env["account.tax"].create({
            "name": "Exento Venta (config test)", "amount": 0.0,
            "amount_type": "percent", "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.exempt_purchase_tax = cls.env["account.tax"].create({
            "name": "Exento Compra (config test)", "amount": 0.0,
            "amount_type": "percent", "type_tax_use": "purchase",
            "company_id": cls.company.id,
        })
        cls.igtf_product = cls.env["product.product"].create({
            "name": "Percepción IGTF (config test)",
            "type": "service",
            "taxes_id": [(6, 0, [cls.exempt_sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [cls.exempt_purchase_tax.id])],
        })

    def test_check_config_requires_product_for_debit_note_mode(self):
        """No se puede activar 'debit_note' sin producto de IGTF configurado."""
        with self.assertRaises(UserError):
            self.company.write({
                "igtf_note_debit_mode": "debit_note",
                "igtf_note_debit_product_id": False,
            })

    def test_check_config_passes_with_product_configured(self):
        self.company.write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_product.id,
        })
        self.assertEqual(self.company.igtf_note_debit_mode, "debit_note")

    def test_check_config_skip_check_context_bypasses_constraint(self):
        """Con `skip_check` en el contexto, se puede guardar 'debit_note'
        sin producto (usado por scripts de migración/instalación)."""
        self.company.with_context(skip_check=True).write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": False,
        })
        self.assertEqual(self.company.igtf_note_debit_mode, "debit_note")

    def test_valid_journal_ids_matches_vef_bank_journals_not_igtf(self):
        """El compute de diarios válidos para IGTF debe incluir únicamente
        diarios banco/caja en VEF que no estén marcados `is_igtf`."""
        self.company.write({"currency_id": self.currency_vef.id})

        bank_account = self.env["account.account"].create({
            "name": "Banco (config test)", "code": "CFGBK1",
            "account_type": "asset_cash",
        })
        valid_journal = self.env["account.journal"].create({
            "name": "Banco VEF válido (config test)",
            "code": "CFGV1",
            "type": "cash",
            "currency_id": self.currency_vef.id,
            "company_id": self.company.id,
            "is_igtf": False,
            "default_account_id": bank_account.id,
        })
        igtf_journal = self.env["account.journal"].create({
            "name": "Banco VEF IGTF (config test)",
            "code": "CFGV2",
            "type": "cash",
            "currency_id": self.currency_vef.id,
            "company_id": self.company.id,
            "is_igtf": True,
            "default_account_id": bank_account.id,
        })
        usd_journal = self.env["account.journal"].create({
            "name": "Banco USD (config test)",
            "code": "CFGV3",
            "type": "cash",
            "currency_id": self.currency_usd.id,
            "company_id": self.company.id,
            "is_igtf": False,
            "default_account_id": bank_account.id,
        })

        valid_ids = self.company.igtf_note_debit_valid_journal_ids
        self.assertIn(valid_journal.id, valid_ids)
        self.assertNotIn(igtf_journal.id, valid_ids)
        self.assertNotIn(usd_journal.id, valid_ids)

    def test_valid_journal_ids_when_company_currency_is_vef_allows_no_currency(self):
        """Si la moneda de la compañía es VEF, un diario sin `currency_id`
        propia (VEF implícita) también debe contar como válido."""
        self.company.write({"currency_id": self.currency_vef.id})
        cash_account = self.env["account.account"].create({
            "name": "Caja (config test)", "code": "CFGBK2",
            "account_type": "asset_cash",
        })
        implicit_vef_journal = self.env["account.journal"].create({
            "name": "Banco sin moneda propia (config test)",
            "code": "CFGV4",
            "type": "cash",
            "currency_id": False,
            "company_id": self.company.id,
            "is_igtf": False,
            "default_account_id": cash_account.id,
        })
        self.assertIn(
            implicit_vef_journal.id, self.company.igtf_note_debit_valid_journal_ids
        )

    def test_valid_journal_ids_when_company_currency_is_not_vef_requires_explicit_vef(self):
        """Si la moneda de la compañía NO es VEF, un diario sin moneda
        propia ya NO cuenta como VEF implícita -- debe tener `currency_id`
        explícitamente en VEF para ser válido."""
        self.company.write({"currency_id": self.currency_usd.id})
        cash_account = self.env["account.account"].create({
            "name": "Caja (config test 2)", "code": "CFGBK3",
            "account_type": "asset_cash",
        })
        implicit_journal = self.env["account.journal"].create({
            "name": "Caja sin moneda propia (config test 2)",
            "code": "CFGV5",
            "type": "cash",
            "currency_id": False,
            "company_id": self.company.id,
            "is_igtf": False,
            "default_account_id": cash_account.id,
        })
        explicit_vef_journal = self.env["account.journal"].create({
            "name": "Caja VEF explícita (config test 2)",
            "code": "CFGV6",
            "type": "cash",
            "currency_id": self.currency_vef.id,
            "company_id": self.company.id,
            "is_igtf": False,
            "default_account_id": cash_account.id,
        })
        valid_ids = self.company.igtf_note_debit_valid_journal_ids
        self.assertNotIn(implicit_journal.id, valid_ids)
        self.assertIn(explicit_vef_journal.id, valid_ids)

    def test_valid_product_ids_empty_without_full_igtf_fiscal_config(self):
        """Sin cuentas de IGTF cliente/proveedor + impuestos exentos
        configurados, la lista de productos válidos debe quedar vacía."""
        self.company.write({
            "customer_account_igtf_id": False,
            "supplier_account_igtf_id": False,
        })
        self.assertFalse(self.company.igtf_note_debit_valid_product_ids)

    def test_valid_product_ids_matches_configured_accounts_and_taxes(self):
        acc_igtf_cli = self.env["account.account"].create({
            "name": "IGTF Cliente (config test)", "code": "CFGA1",
            "account_type": "liability_current",
        })
        acc_igtf_prov = self.env["account.account"].create({
            "name": "IGTF Proveedor (config test)", "code": "CFGA2",
            "account_type": "expense",
        })
        self.company.write({
            "customer_account_igtf_id": acc_igtf_cli.id,
            "supplier_account_igtf_id": acc_igtf_prov.id,
            "exent_aliquot_sale": self.exempt_sale_tax.id,
            "exent_aliquot_purchase": self.exempt_purchase_tax.id,
        })
        matching_product = self.env["product.product"].create({
            "name": "Producto IGTF válido (config test)",
            "type": "service",
            "property_account_income_id": acc_igtf_cli.id,
            "property_account_expense_id": acc_igtf_prov.id,
            "taxes_id": [(6, 0, [self.exempt_sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [self.exempt_purchase_tax.id])],
        })
        valid_ids = self.company.igtf_note_debit_valid_product_ids
        self.assertIn(matching_product.id, valid_ids)
        self.assertNotIn(self.igtf_product.id, valid_ids)


@tagged("post_install", "-at_install")
class TestIgtfNoteDebitResConfigSettings(TransactionCase):
    """`res.config.settings` es solo un espejo (compute/inverse) de los
    campos reales en `res.company` -- se valida el round-trip."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.exempt_sale_tax = cls.env["account.tax"].create({
            "name": "Exento Venta (settings test)", "amount": 0.0,
            "amount_type": "percent", "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.igtf_product = cls.env["product.product"].create({
            "name": "Percepción IGTF (settings test)",
            "type": "service",
            "taxes_id": [(6, 0, [cls.exempt_sale_tax.id])],
        })

    def test_compute_reads_current_company_values(self):
        self.company.write({"igtf_note_debit_mode": "inline"})
        settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
        })
        self.assertEqual(settings.igtf_note_debit_mode, "inline")
        self.assertFalse(settings.igtf_note_debit_product_id)

    def test_inverse_writes_back_to_company(self):
        settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_product.id,
        })
        settings.execute()
        self.assertEqual(self.company.igtf_note_debit_mode, "debit_note")
        self.assertEqual(self.company.igtf_note_debit_product_id, self.igtf_product)

    def test_related_fields_round_trip(self):
        journal = self.env["account.journal"].search(
            [("type", "in", ("bank", "cash")), ("company_id", "=", self.company.id)], limit=1
        )
        settings = self.env["res.config.settings"].create({
            "company_id": self.company.id,
            "igtf_note_debit_include_in_payment_default": False,
            "igtf_note_debit_vef_journal_id": journal.id,
        })
        settings.execute()
        self.assertFalse(self.company.igtf_note_debit_include_in_payment_default)
        self.assertEqual(self.company.igtf_note_debit_vef_journal_id, journal)
