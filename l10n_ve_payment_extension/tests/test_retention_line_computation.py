from odoo.tests import TransactionCase, tagged, Form
from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
import logging, random

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "retention_line_computation")
class TestRetentionLineComputation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestRetentionLineComputation, cls).setUpClass()
        cls.company = cls.env.company
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.currency_usd = cls.env.ref("base.USD")
        cls.company.write({
            "currency_id": cls.currency_vef.id,
            "foreign_currency_id": cls.currency_usd.id,
            "country_id": 28,
        })

        def get_or_create_account(code, ttype, name, recon=False):
            account = cls.env["account.account"].search([("code", "=", code)], limit=1)
            vals = {"name": name, "code": code, "account_type": ttype, "reconcile": recon}
            if account:
                account.write(vals)
                return account
            return cls.env["account.account"].create(vals)

        cls.acc_receivable = get_or_create_account("1101", "asset_receivable", "Cuentas por Cobrar", recon=True)
        cls.acc_payable = get_or_create_account("2101", "liability_payable", "Cuentas por Pagar", recon=True)
        cls.acc_income = get_or_create_account("4001", "income", "Ingresos")
        cls.acc_expense = get_or_create_account("5001", "asset_current", "Costo/Gasto")
        cls.acc_bank = get_or_create_account("1001", "asset_cash", "Banco VEF")

        manual_in = cls.env.ref("account.account_payment_method_manual_in")
        manual_out = cls.env.ref("account.account_payment_method_manual_out")

        cls.pm_in = cls.env["account.payment.method.line"].create({
            "name": "Manual In",
            "payment_method_id": manual_in.id,
            "payment_type": "inbound",
            "payment_account_id": cls.acc_bank.id,
        })
        cls.pm_out = cls.env["account.payment.method.line"].create({
            "name": "Manual Out",
            "payment_method_id": manual_out.id,
            "payment_type": "outbound",
            "payment_account_id": cls.acc_bank.id,
        })

        cls.bank_journal = cls.env["account.journal"].create({
            "name": "Banco Test",
            "code": "BNKT",
            "type": "bank",
            "company_id": cls.company.id,
            "currency_id": cls.currency_vef.id,
            "default_account_id": cls.acc_bank.id,
            "inbound_payment_method_line_ids": [Command.set(cls.pm_in.ids)],
            "outbound_payment_method_line_ids": [Command.set(cls.pm_out.ids)],
        })

        seq_purchase = cls.env["ir.sequence"].create({
            "name": "Secuencia Compra", "code": "account.move",
            "prefix": "PUR/", "padding": 8, "number_next_actual": 2,
        })
        cls.purchase_journal = cls.env["account.journal"].create({
            "name": "Compra Test", "type": "purchase", "code": "PURT",
            "company_id": cls.company.id, "currency_id": cls.currency_vef.id,
            "sequence_id": seq_purchase.id,
        })

        tax_group = cls.env["account.tax.group"].create({
            "name": "IVA Test", "company_id": cls.company.id, "country_id": 28,
        })
        cls.tax_iva_16 = cls.env["account.tax"].create({
            "name": "IVA 16% Compra", "amount_type": "percent", "amount": 16.0,
            "type_tax_use": "purchase", "company_id": cls.company.id,
            "tax_group_id": tax_group.id, "country_id": 28,
        })

        cls.partner = cls.env["res.partner"].create({
            "name": "Proveedor Test",
            "vat": "J123456789",
            "property_account_receivable_id": cls.acc_receivable.id,
            "property_account_payable_id": cls.acc_payable.id,
            "taxpayer_type": "formal",
        })

        cls.product = cls.env["product.product"].create({
            "name": "Producto Test",
            "list_price": 100,
            "property_account_income_id": cls.acc_income.id,
            "supplier_taxes_id": [Command.set(cls.tax_iva_16.ids)],
        })

        country = cls.env["res.country"].search([], limit=1) or cls.env["res.country"].create({"name": "Test", "code": "T1"})
        state = cls.env["res.country.state"].search([], limit=1) or cls.env["res.country.state"].create({"name": "TS", "code": "TS", "country_id": country.id})
        cls.municipality = cls.env["res.country.municipality"].create({
            "name": "Municipio Test", "code": "MUN-T",
            "country_id": country.id, "state_id": [Command.set(state.ids)],
        })
        cls.branch = cls.env["economic.branch"].create({
            "name": "Rama Test", "status": "active",
        })
        cls.economic_activity = cls.env["economic.activity"].create({
            "name": "Actividad Test", "aliquot": 5.0,
            "municipality_id": cls.municipality.id,
            "branch_id": cls.branch.id,
            "description": "Test", "minimum_monthly": 0, "minimum_annual": 0,
        })

        cls.tax_unit = cls.env["tax.unit"].create({
            "name": "UT Test", "value": 100.0,
            "available_date": fields.Date.today(), "status": True,
        })

        cls.person_type = cls.env["type.person"].search([], limit=1) or cls.env["type.person"].create({"name": "Persona Test"})

        cls.non_accumulated_tariff = cls.env["fees.retention"].create({
            "name": "Tarifa 3%", "percentage": 3.0, "accumulated_rate": False,
            "tax_unit_ids": cls.tax_unit.id, "status": True,
        })

        cls.company.write({
            "iva_supplier_retention_journal_id": cls.bank_journal.id,
            "iva_customer_retention_journal_id": cls.bank_journal.id,
            "islr_supplier_retention_journal_id": cls.bank_journal.id,
            "municipal_supplier_retention_journal_id": cls.bank_journal.id,
        })

    def _create_simple_invoice(self, amount=200):
        with Form(self.env["account.move"].with_context(
            default_move_type="in_invoice", default_journal_id=self.purchase_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = fields.Date.today()
            inv_form.correlative = str(random.randint(10000000000000, 99999999999999))
        inv = inv_form.save()
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product
                line.quantity = 1
                line.price_unit = amount
        inv = inv_form_edit.save()
        inv.write({"foreign_rate": 1.0, "foreign_inverse_rate": 1.0})
        return inv

    def test_01_onchange_move_id_iva_supplier(self):
        invoice = self._create_simple_invoice(200)
        line = self.env["account.retention.line"].new({
            "move_id": invoice.id,
            "retention_id": self.env["account.retention"].new({
                "type_retention": "iva",
                "partner_id": self.partner.id,
            }),
        })
        line._onchange_move_id()
        self.assertTrue(line.invoice_amount > 0)
        self.assertTrue(line.iva_amount > 0)
        self.assertEqual(line.aliquot, 16.0)
        _logger.info("========= test_01_onchange_move_id_iva_supplier passed =========")

    def test_02_onchange_move_id_no_tax_warning(self):
        product_no_tax = self.env["product.product"].create({
            "name": "Sin IVA",
            "property_account_income_id": self.acc_income.id,
            "supplier_taxes_id": [Command.clear()],
        })
        with Form(self.env["account.move"].with_context(
            default_move_type="in_invoice", default_journal_id=self.purchase_journal.id,
        )) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = fields.Date.today()
            inv_form.correlative = str(random.randint(10000000000000, 99999999999999))
        inv = inv_form.save()
        with Form(inv) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = product_no_tax
                line.quantity = 1
                line.price_unit = 100
        inv = inv_form_edit.save()

        line = self.env["account.retention.line"].new({
            "move_id": inv.id,
            "retention_id": self.env["account.retention"].new({
                "type_retention": "iva",
                "partner_id": self.partner.id,
            }),
        })
        result = line._onchange_move_id()
        self.assertIn("warning", result or {})
        _logger.info("========= test_02_onchange_move_id_no_tax_warning passed =========")

    def test_03_compute_economic_activity_id(self):
        self.partner.write({"economic_activity_id": self.economic_activity.id})
        retention = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].create({
            "move_id": self._create_simple_invoice(200).id,
            "retention_id": retention.id,
        })
        line._compute_economic_activity_id()
        self.assertEqual(line.economic_activity_id, self.economic_activity)
        _logger.info("========= test_03_compute_economic_activity_id passed =========")

    def test_04_compute_related_fields_non_accumulated(self):
        invoice = self._create_simple_invoice(500)
        retention = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        payment_concept = self.env["payment.concept"].create({
            "name": "Concepto ISLR Test",
            "line_payment_concept_ids": [Command.create({
                "code": "ISLR-T", "type_person_id": self.person_type.id,
                "percentage_tax_base": 100.0, "tariff_id": self.non_accumulated_tariff.id,
            })],
        })
        line = self.env["account.retention.line"].create({
            "move_id": invoice.id,
            "retention_id": retention.id,
            "payment_concept_id": payment_concept.id,
            "invoice_total": 500.0,
            "invoice_amount": 500.0,
            "retention_amount": 5.0,
            "foreign_invoice_amount": 500.0,
            "foreign_retention_amount": 5.0,
        })
        self.partner.write({"type_person_id": self.person_type.id})
        line._compute_related_fields()
        self.assertEqual(line.related_percentage_fees, 3.0)
        _logger.info("========= test_04_compute_related_fields_non_accumulated passed =========")

    def test_05_compute_retention_amount(self):
        invoice = self._create_simple_invoice(500)
        retention = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        payment_concept = self.env["payment.concept"].create({
            "name": "Concepto ISLR",
            "line_payment_concept_ids": [Command.create({
                "code": "ISLR-T2", "type_person_id": self.person_type.id,
                "percentage_tax_base": 80.0, "tariff_id": self.non_accumulated_tariff.id,
            })],
        })
        line = self.env["account.retention.line"].create({
            "move_id": invoice.id,
            "retention_id": retention.id,
            "payment_concept_id": payment_concept.id,
            "invoice_total": 500.0,
            "invoice_amount": 500.0,
            "retention_amount": 5.0,
            "foreign_invoice_amount": 500.0,
            "foreign_retention_amount": 5.0,
            "related_percentage_tax_base": 80.0,
            "related_percentage_fees": 3.0,
        })
        self.partner.write({"type_person_id": self.person_type.id})
        line._compute_retention_amount()
        expected = abs(500.0 * (80.0 / 100.0) * (3.0 / 100.0))
        self.assertAlmostEqual(line.retention_amount, expected, places=2)
        _logger.info("========= test_05_compute_retention_amount passed =========")

    def test_06_onchange_economic_activity_id(self):
        invoice = self._create_simple_invoice(200)
        line = self.env["account.retention.line"].new({
            "move_id": invoice.id,
            "economic_activity_id": self.economic_activity.id,
        })
        line.onchange_economic_activity_id()
        self.assertEqual(line.aliquot, self.economic_activity.aliquot)
        _logger.info("========= test_06_onchange_economic_activity_id passed =========")

    def test_07_onchange_municipal_invoice_amount(self):
        line = self.env["account.retention.line"].new({
            "invoice_amount": 1000.0,
            "aliquot": 5.0,
            "economic_activity_id": self.economic_activity.id,
        })
        line.onchange_municipal_invoice_amount()
        self.assertAlmostEqual(line.retention_amount, 50.0, places=2)
        _logger.info("========= test_07_onchange_municipal_invoice_amount passed =========")

    def test_08_onchange_retention_amount(self):
        invoice = self._create_simple_invoice(200)
        invoice.write({"foreign_inverse_rate": 2.5})
        line = self.env["account.retention.line"].new({
            "move_id": invoice.id,
            "invoice_amount": 1000.0,
            "retention_amount": 50.0,
        })
        line.onchange_retention_amount()
        expected_foreign = 50.0 * 2.5
        self.assertAlmostEqual(line.foreign_retention_amount, expected_foreign, places=2)
        _logger.info("========= test_08_onchange_retention_amount passed =========")

    def test_09_check_retention_amount_validation(self):
        invoice = self._create_simple_invoice(200)
        invoice.action_post()
        line = self.env["account.retention.line"].create({
            "move_id": invoice.id,
            "invoice_total": 200.0,
            "invoice_amount": 200.0,
            "retention_amount": 5000.0,
            "foreign_invoice_amount": 200.0,
            "foreign_retention_amount": 5000.0,
            "retention_id": self.env["account.retention"].create({
                "type_retention": "iva",
                "type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": self.partner.id,
                "date": fields.Date.today(),
                "date_accounting": fields.Date.today(),
            }).id,
        })
        with self.assertRaises(ValidationError):
            line.check_retention_amount()
        _logger.info("========= test_09_check_retention_amount_validation passed =========")

    def test_10_constraint_amounts_in_zero(self):
        invoice = self._create_simple_invoice(200)
        invoice.action_post()
        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        retention.write({"state": "emitted"})
        with self.assertRaises(ValidationError):
            self.env["account.retention.line"].create({
                "move_id": invoice.id,
                "retention_id": retention.id,
                "invoice_total": 0.0,
                "invoice_amount": 0.0,
                "retention_amount": 0.0,
            })
        _logger.info("========= test_10_constraint_amounts_in_zero passed =========")

    def test_11_get_code_of_retention(self):
        payment_concept = self.env["payment.concept"].create({
            "name": "Concepto Code Test",
            "line_payment_concept_ids": [Command.create({
                "code": "CODE-123", "type_person_id": self.person_type.id,
                "percentage_tax_base": 100.0, "tariff_id": self.non_accumulated_tariff.id,
            })],
        })
        self.partner.write({"type_person_id": self.person_type.id})
        retention = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "date": fields.Date.today(),
            "date_accounting": fields.Date.today(),
        })
        line = self.env["account.retention.line"].create({
            "move_id": self._create_simple_invoice(200).id,
            "retention_id": retention.id,
            "payment_concept_id": payment_concept.id,
            "invoice_total": 200.0, "invoice_amount": 200.0,
            "retention_amount": 10.0, "foreign_invoice_amount": 200.0,
            "foreign_retention_amount": 10.0,
        })
        code = line._get_code_of_retention()
        self.assertEqual(code, "CODE-123")
        _logger.info("========= test_11_get_code_of_retention passed =========")

    def test_12_get_islr_type_person_id_fallback(self):
        line = self.env["account.retention.line"].new({
            "move_id": self._create_simple_invoice(200).id,
        })
        result = line._get_islr_type_person_id()
        self.assertEqual(result, self.env["type.person"])
        _logger.info("========= test_12_get_islr_type_person_id_fallback passed =========")
