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
        # Combo choice fixture: every product.template with type='combo' requires
        # at least 1 combo_ids -> combo_item_ids (core constraint, unrelated to taxes).
        self.combo_component = self.env["product.product"].create({
            "name": "Combo Component",
            "type": "consu",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        self.combo = self.env["product.combo"].create({
            "name": "Test Combo Choice",
            "combo_item_ids": [(0, 0, {"product_id": self.combo_component.id})],
        })

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
    # Combo products — exempt from single-tax validation
    # ═══════════════════════════════════════════════════════════════

    def test_14_create_combo_without_taxes_no_default(self):
        """Crear producto combo sin taxes y sin defaults de compañía -> OK"""
        self.company.write({
            "account_sale_tax_id": False,
            "account_purchase_tax_id": False,
        })
        product = self.env["product.template"].create({
            "name": "Test Combo No Taxes",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
        })
        self.assertFalse(product.taxes_id)
        self.assertFalse(product.supplier_taxes_id)

    def test_15_create_combo_with_two_sale_taxes(self):
        """Crear producto combo con 2 sale taxes -> OK, la regla no aplica a combo"""
        product = self.env["product.template"].create({
            "name": "Test Combo Two Taxes",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
            "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
        })
        self.assertEqual(len(product.taxes_id), 2)

    def test_16_write_existing_combo_without_resending_type(self):
        """Write sobre combo existente sin reenviar 'type', taxes invalidos -> OK"""
        self.company.write({
            "account_sale_tax_id": False,
        })
        product = self.env["product.template"].create({
            "name": "Test Combo Write",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
        })
        # create() leaves skip_tax_validation_on_write=True on the returned
        # recordset's context; reset it so this write() is validated for real.
        product = product.with_context(skip_tax_validation_on_write=False)
        product.write({"taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])]})
        self.assertEqual(len(product.taxes_id), 2)

    def test_17_write_change_type_consu_to_combo(self):
        """Write que cambia type de consu a combo junto con taxes invalidos -> OK"""
        product = self.env["product.template"].create({
            "name": "Test Consu To Combo",
            "type": "consu",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        product = product.with_context(skip_tax_validation_on_write=False)
        product.write({
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
            "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
        })
        self.assertEqual(product.type, "combo")
        self.assertEqual(len(product.taxes_id), 2)

    def test_18_write_change_type_combo_to_consu(self):
        """Write que cambia type de combo a consu junto con taxes invalidos -> UserError"""
        product = self.env["product.template"].create({
            "name": "Test Combo To Consu",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
            "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
        })
        product = product.with_context(skip_tax_validation_on_write=False)
        with self.assertRaises(UserError):
            product.write({
                "type": "consu",
                "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
            })

    def test_19_write_mixed_recordset_combo_and_non_combo(self):
        """Write sobre recordset mixto (combo + no-combo) -> valida solo el no-combo"""
        combo_product = self.env["product.template"].create({
            "name": "Test Mixed Combo",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
        })
        regular_product = self.env["product.template"].create({
            "name": "Test Mixed Regular",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        mixed = (combo_product + regular_product).with_context(skip_tax_validation_on_write=False)
        with self.assertRaises(UserError):
            mixed.write({"taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])]})
