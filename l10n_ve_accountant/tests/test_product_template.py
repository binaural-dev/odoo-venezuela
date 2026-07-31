import logging
from odoo.tests import TransactionCase, tagged
from odoo import fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_accountant_core")
class TestProductTemplate(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.ref("base.main_company")
        self.tax_group = self.env['account.tax.group'].create({
            'name': 'Test Tax Group', 'company_id': self.company.id,
        })
        self.tax_sale_1 = self.env["account.tax"].with_company(self.company).create({
            "name": "Sale Tax 16%", "amount": 16, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
        })
        self.tax_sale_2 = self.env["account.tax"].with_company(self.company).create({
            "name": "Sale Tax 8%", "amount": 8, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
        })
        self.tax_purchase = self.env["account.tax"].with_company(self.company).create({
            "name": "Purchase Tax 8%", "amount": 8, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
        })
        # The "more than one tax" rule only applies to companies that opted
        # into it; the "zero taxes with no default" rule is unconditional.
        self.company.unique_tax = True

    # ═══════════════════════════════════════════════════════════════
    # Positive tests — product creation / write should succeed
    # ═══════════════════════════════════════════════════════════════

    def test_01_create_one_sale_tax(self):
        """Crear producto con 1 sale tax -> OK"""
        product = self.env["product.product"].create({
            "name": "Test Sale Only",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        self.assertEqual(len(product.taxes_id), 1)
        self.assertEqual(product.taxes_id.id, self.tax_sale_1.id)

    def test_02_create_one_purchase_tax(self):
        """Crear producto con 1 purchase tax -> OK"""
        product = self.env["product.product"].create({
            "name": "Test Purchase Only",
            "type": "service",
            "taxes_id": [(6, 0, [])],
            "supplier_taxes_id": [(6, 0, [self.tax_purchase.id])],
        })
        self.assertEqual(len(product.supplier_taxes_id), 1)
        self.assertEqual(product.supplier_taxes_id.id, self.tax_purchase.id)

    def test_03_create_one_sale_one_purchase(self):
        """Crear producto con 1 sale + 1 purchase tax -> OK"""
        product = self.env["product.product"].create({
            "name": "Test Both",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [self.tax_purchase.id])],
        })
        self.assertEqual(len(product.taxes_id), 1)
        self.assertEqual(len(product.supplier_taxes_id), 1)

    def test_04_create_with_company_defaults(self):
        """Company tiene defaults, producto sin taxes -> se asignan automáticamente"""
        self.company.write({
            "account_sale_tax_id": self.tax_sale_1.id,
            "account_purchase_tax_id": self.tax_purchase.id,
        })
        product = self.env["product.product"].create({
            "name": "Test Defaults",
            "type": "service",
            "taxes_id": [(5, 0, 0)],
            "supplier_taxes_id": [(5, 0, 0)],
        })
        self.assertEqual(len(product.taxes_id), 1)
        self.assertEqual(product.taxes_id.id, self.tax_sale_1.id)
        self.assertEqual(len(product.supplier_taxes_id), 1)
        self.assertEqual(product.supplier_taxes_id.id, self.tax_purchase.id)

    def test_05_write_sale_tax(self):
        """Write con 1 sale tax sobre producto existente -> OK"""
        product = self.env["product.product"].create({
            "name": "Test Write",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        product.write({"taxes_id": [(6, 0, [self.tax_sale_1.id])]})
        self.assertEqual(len(product.taxes_id), 1)

    def test_06_write_non_tax_field(self):
        """Write solo de name -> no ejecuta validacion -> OK"""
        product = self.env["product.product"].create({
            "name": "Original Name",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        product.write({"name": "Updated Name"})
        self.assertEqual(product.name, "Updated Name")

    def test_07_write_command_6_replace_one(self):
        """Command 6 reemplaza con 1 tax -> OK"""
        product = self.env["product.product"].create({
            "name": "Test Cmd6",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        product.write({"taxes_id": [(6, 0, [self.tax_sale_1.id])]})
        self.assertEqual(product.taxes_id.id, self.tax_sale_1.id)

    def test_08_write_command_5_clear_then_4_one(self):
        """Command 5 + Command 4 con company defaults -> net 1 -> OK"""
        self.company.write({
            "account_sale_tax_id": self.tax_sale_1.id,
        })
        product = self.env["product.product"].create({
            "name": "Test Cmd5and4",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        product.write({
            "taxes_id": [
                (5, 0, 0),
                (4, self.tax_sale_1.id),
            ]
        })
        self.assertEqual(len(product.taxes_id), 1)

    # ═══════════════════════════════════════════════════════════════
    # Negative tests — product creation / write should raise UserError
    # ═══════════════════════════════════════════════════════════════

    def test_09_create_two_sale_taxes(self):
        """2 sale taxes distintos -> UserError"""
        with self.assertRaises(UserError):
            self.env["product.product"].create({
                "name": "Test Two Sale Taxes",
                "type": "service",
                "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
                "supplier_taxes_id": [(6, 0, [])],
            })

    def test_10_create_no_taxes_no_default(self):
        """Sin taxes, company sin defaults -> UserError"""
        self.company.write({
            "account_sale_tax_id": False,
            "account_purchase_tax_id": False,
        })
        with self.assertRaises(UserError):
            self.env["product.product"].create({
                "name": "Test No Tax",
                "type": "service",
                "taxes_id": [(5, 0, 0)],
                "supplier_taxes_id": [(5, 0, 0)],
            })

    def test_11_write_two_sale_taxes(self):
        """Escribir 2 sale taxes distintos -> UserError"""
        product = self.env["product.product"].create({
            "name": "Test Write Two",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        with self.assertRaises(UserError):
            product.write({
                "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
            })

    def test_12_write_command_4_add_second(self):
        """Command 4 agrega segundo tax distinto -> UserError"""
        product = self.env["product.product"].create({
            "name": "Test Cmd4 Second",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        with self.assertRaises(UserError):
            product.write({"taxes_id": [(4, self.tax_sale_2.id)]})

    def test_13_write_command_3_to_zero_no_default(self):
        """Command 3 remueve ultimo tax, no hay default -> UserError"""
        self.company.write({
            "account_sale_tax_id": False,
        })
        product = self.env["product.product"].create({
            "name": "Test Cmd3 To Zero",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        with self.assertRaises(UserError):
            product.write({"taxes_id": [(3, self.tax_sale_1.id)]})

    # ═══════════════════════════════════════════════════════════════
    # Regression tests — unique_tax gating and False/None write bypass
    # ═══════════════════════════════════════════════════════════════

    def test_14_two_sale_taxes_allowed_when_unique_tax_disabled(self):
        """Sin unique_tax, 2 sale taxes distintos -> OK (no bloquea a companias que no usan la opcion)"""
        self.company.unique_tax = False
        product = self.env["product.product"].create({
            "name": "Test Two Sale Taxes Allowed",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
            "supplier_taxes_id": [(6, 0, [self.tax_purchase.id])],
        })
        self.assertEqual(len(product.taxes_id), 2)

    def test_15_write_false_does_not_bypass_validation(self):
        """write({'taxes_id': False}) debe re-evaluarse contra el estado vacio resultante, no contra el estado previo"""
        self.company.write({
            "account_sale_tax_id": self.tax_sale_1.id,
        })
        product = self.env["product.product"].create({
            "name": "Test Write False",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        product.write({"taxes_id": False})
        # With a company default configured, clearing the field auto-fills it
        # instead of silently leaving the product without a sales tax.
        self.assertEqual(len(product.taxes_id), 1)
        self.assertEqual(product.taxes_id.id, self.tax_sale_1.id)

        self.company.write({"account_sale_tax_id": False})
        with self.assertRaises(UserError):
            product.write({"taxes_id": False})
