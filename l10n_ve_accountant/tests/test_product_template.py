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

    def test_15_write_existing_combo_taxes_exempt(self):
        """Combo existente recibe 2 taxes por write -> OK, la regla no aplica a combo"""
        self.company.write({
            "account_sale_tax_id": False,
        })
        product = self.env["product.template"].create({
            "name": "Test Combo Write",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
        })
        # FIX-062: No need to reset context — create() no longer sets
        # skip_tax_validation_on_write. Combo is exempt regardless.
        product.write({"taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])]})
        self.assertEqual(len(product.taxes_id), 2)

    def test_16_write_change_type_consu_to_combo(self):
        """Write que cambia type de consu a combo junto con taxes invalidos -> OK"""
        product = self.env["product.template"].create({
            "name": "Test Consu To Combo",
            "type": "consu",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        # FIX-062: No need to reset context — create() no longer sets
        # skip_tax_validation_on_write.
        product.write({
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
            "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
        })
        self.assertEqual(product.type, "combo")
        self.assertEqual(len(product.taxes_id), 2)

    def test_17_write_change_type_combo_to_consu(self):
        """Write que cambia type de combo a consu junto con taxes invalidos -> UserError"""
        product = self.env["product.template"].create({
            "name": "Test Combo To Consu",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
            "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
        })
        # FIX-062: No need to reset context.
        with self.assertRaises(UserError):
            product.write({
                "type": "consu",
                "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
            })

    def test_18_write_mixed_recordset_combo_and_non_combo(self):
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
        # FIX-062: No need to reset context.
        mixed = combo_product + regular_product
        with self.assertRaises(UserError):
            mixed.write({"taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])]})

    # ═══════════════════════════════════════════════════════════════
    # FIX-060: vals mutation isolation
    # ═══════════════════════════════════════════════════════════════

    def test_19_default_injection_does_not_leak_to_combo(self):
        """FIX-060: When a non-combo product triggers default injection, the
        default tax must NOT be applied to excluded combo products in the
        same recordset."""
        self.company.write({
            "account_sale_tax_id": self.tax_sale_1.id,
        })
        combo_product = self.env["product.template"].create({
            "name": "Test Leak Combo",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
        })
        regular_product = self.env["product.template"].create({
            "name": "Test Leak Regular",
            "type": "service",
            "taxes_id": [(5, 0, 0)],  # empty → will trigger default injection
            "supplier_taxes_id": [(6, 0, [])],
        })
        mixed = combo_product + regular_product
        # Writing taxes_id empty on both: non-combo gets default, combo stays empty.
        mixed.write({"taxes_id": [(5, 0, 0)]})
        # The combo product must NOT have received the default tax.
        self.assertFalse(combo_product.taxes_id,
                         "Combo product must not receive default tax from non-combo validation")
        # The regular product gets the company default.
        self.assertEqual(regular_product.taxes_id.id, self.tax_sale_1.id)

    # ═══════════════════════════════════════════════════════════════
    # FIX-061: trigger completeness — type change without taxes
    # ═══════════════════════════════════════════════════════════════

    def test_20_write_combo_to_consu_without_taxes_no_default(self):
        """FIX-061: Changing type from combo to consu WITHOUT touching taxes
        must trigger validation. Combo had 2 taxes → error on consu."""
        self.company.write({
            "account_sale_tax_id": False,
        })
        product = self.env["product.template"].create({
            "name": "Test Combo To Consu No Tax",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
            "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
        })
        with self.assertRaises(UserError):
            product.write({"type": "consu"})  # no taxes in vals

    def test_21_write_combo_to_consu_without_taxes_with_default(self):
        """FIX-061: Changing combo→consu without taxes: if combo had 1 tax,
        it's valid for consu too → OK."""
        product = self.env["product.template"].create({
            "name": "Test Combo To Consu Valid",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
        })
        product.write({"type": "consu"})
        self.assertEqual(product.type, "consu")
        self.assertEqual(product.taxes_id.id, self.tax_sale_1.id)

    def test_22_write_combo_to_consu_empty_taxes_with_default(self):
        """FIX-061: Changing combo→consu when combo had no taxes:
        company default is injected → OK."""
        self.company.write({
            "account_sale_tax_id": self.tax_sale_1.id,
        })
        product = self.env["product.template"].create({
            "name": "Test Combo Empty To Consu",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
        })
        product.write({"type": "consu"})
        self.assertEqual(product.type, "consu")
        self.assertEqual(product.taxes_id.id, self.tax_sale_1.id)

    def test_23_write_combo_to_consu_empty_taxes_no_default(self):
        """FIX-061: Changing combo→consu when combo had no taxes and
        no company default → UserError."""
        self.company.write({
            "account_sale_tax_id": False,
            "account_purchase_tax_id": False,
        })
        product = self.env["product.template"].create({
            "name": "Test Combo Empty No Default",
            "type": "combo",
            "combo_ids": [(6, 0, [self.combo.id])],
        })
        with self.assertRaises(UserError):
            product.write({"type": "consu"})

    # ═══════════════════════════════════════════════════════════════
    # TI-15065: batch write on 2+ records must not crash with ensure_one,
    # and must validate EACH product individually, not the union of taxes
    # across the whole recordset (deuda técnica: test_18/test_19 always
    # collapse to a single non-combo record after filtered(), so they
    # never exercised a real multi-record batch — these do).
    # ═══════════════════════════════════════════════════════════════

    def test_24_write_batch_multi_record_error_no_ensure_one_crash(self):
        """TI-15065: A single write() on a product.template RECORDSET of 2+
        records (not through the product.product _inherits delegation,
        which splits the write per template) that ends up in a fiscal error
        state must raise a UserError listing every affected product — not
        crash with `ValueError: Expected singleton` when the error branch
        reads records.name/records.company_id on a multi-record recordset.
        Reproduces the real scenario from
        account.chart.template._post_load_data, which calls
        product.template(id1, id2, ...).write({'taxes_id': ...}) directly
        on a multi-record product.template recordset."""
        product_a = self.env["product.template"].create({
            "name": "Test Batch Error A",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        product_b = self.env["product.template"].create({
            "name": "Test Batch Error B",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        batch = product_a + product_b
        with self.assertRaises(UserError) as cm:
            batch.write({
                "taxes_id": [(6, 0, [self.tax_sale_1.id, self.tax_sale_2.id])],
            })
        message = str(cm.exception)
        self.assertIn(product_a.name, message)
        self.assertIn(product_b.name, message)

    def test_25_write_batch_untouched_field_not_validated(self):
        """TI-15065: account._force_default_sale_tax only ever writes
        `taxes_id` (never `supplier_taxes_id`) in a single batch write. A
        previous version of this method always validated BOTH fields on
        every write, using the union of supplier_taxes_id across every
        record in the batch as a baseline — so two products that each had
        their own different, individually-valid purchase tax would falsely
        raise "Purchase Taxes: Has 2 taxes assigned", even though the write
        never touched that field at all. Only fields actually present in
        vals must be validated."""
        other_purchase_tax = self.env["account.tax"].with_company(self.company).create({
            "name": "Purchase Tax 16%", "amount": 16, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": self.company.id,
            "tax_group_id": self.tax_group.id,
        })
        product_a = self.env["product.template"].create({
            "name": "Test Untouched Field A",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [self.tax_purchase.id])],
        })
        product_b = self.env["product.template"].create({
            "name": "Test Untouched Field B",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [other_purchase_tax.id])],
        })
        batch = product_a + product_b
        # Only touches taxes_id (redundant link, both already have
        # tax_sale_1) -> supplier_taxes_id (different per record) must be
        # left out of validation entirely.
        batch.write({"taxes_id": [(4, self.tax_sale_1.id)]})
        self.assertEqual(product_a.taxes_id.ids, [self.tax_sale_1.id])
        self.assertEqual(product_b.taxes_id.ids, [self.tax_sale_1.id])
        self.assertEqual(product_a.supplier_taxes_id.id, self.tax_purchase.id)
        self.assertEqual(product_b.supplier_taxes_id.id, other_purchase_tax.id)

    def test_26_write_batch_only_offending_record_raises(self):
        """TI-15065: When a batch write() leaves exactly one product with
        2+ taxes (a genuine violation) while others stay valid, the
        UserError must name only the offending product — not conflate it
        with unrelated products in the same recordset (the old aggregated-
        union bug would report every distinct tax across the whole batch,
        regardless of which product actually held it)."""
        product_ok = self.env["product.template"].create({
            "name": "Test Batch Only Offender OK",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_1.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        product_offender = self.env["product.template"].create({
            "name": "Test Batch Only Offender BAD",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_sale_2.id])],
            "supplier_taxes_id": [(6, 0, [])],
        })
        batch = product_ok + product_offender
        with self.assertRaises(UserError) as cm:
            batch.write({"taxes_id": [(4, self.tax_sale_1.id)]})
        message = str(cm.exception)
        self.assertIn(product_offender.name, message)
        self.assertNotIn(product_ok.name, message)

    def test_27_write_batch_shared_product_ignores_other_company_taxes(self):
        """TI-15065: account.tax.company_id is mandatory and NOT
        company_dependent, and taxes_id/supplier_taxes_id on
        product.template carry no company domain either — so a product
        shared across companies/branches (no company_id, common for base
        products) can legitimately carry a tax from a company OTHER than
        the one whose default is being forced onto it. This is exactly
        what happens when creating a new company/branch:
        account._force_default_sale_tax links the NEW company's default
        tax onto every product, including shared ones that already carry
        a DIFFERENT (unrelated) company's own valid tax. That must not be
        reported as "2 taxes assigned" — only taxes actually usable by the
        company doing the write (itself, or an ancestor in the branch
        hierarchy) count towards the rule."""
        other_company = self.env["res.company"].create({"name": "Unrelated Company TI-15065"})
        other_tax_group = self.env["account.tax.group"].create({
            "name": "Other Company Tax Group", "company_id": other_company.id,
        })
        other_company_tax = self.env["account.tax"].with_company(other_company).create({
            "name": "Other Company Sale Tax", "amount": 12, "amount_type": "percent",
            "type_tax_use": "sale", "company_id": other_company.id,
            "tax_group_id": other_tax_group.id,
        })
        other_company_purchase_tax = self.env["account.tax"].with_company(other_company).create({
            "name": "Other Company Purchase Tax", "amount": 5, "amount_type": "percent",
            "type_tax_use": "purchase", "company_id": other_company.id,
            "tax_group_id": other_tax_group.id,
        })
        shared_product = self.env["product.template"].create({
            "name": "Test Shared Product",
            "type": "service",
            "company_id": other_company.id,
            "taxes_id": [(6, 0, [other_company_tax.id])],
            "supplier_taxes_id": [(6, 0, [other_company_purchase_tax.id])],
        })
        # Only touches company_id (not taxes_id/supplier_taxes_id), so the
        # write() override's validation isn't triggered by this — simulates
        # the product becoming shared/company-independent, as base/demo
        # products commonly are.
        shared_product.write({"company_id": False})

        # Simulates account._force_default_sale_tax linking self.company's
        # default tax onto this shared product during self.company's own
        # creation — must not raise, since only self.company's own tax
        # counts for self.company's validation.
        shared_product.write({"taxes_id": [(4, self.tax_sale_1.id)]})
        self.assertEqual(
            set(shared_product.taxes_id.ids),
            {other_company_tax.id, self.tax_sale_1.id},
        )
