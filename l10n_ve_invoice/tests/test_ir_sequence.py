from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_invoice")
class TestIrSequence(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.other_company = self.env["res.company"].create(
            {
                "name": "Other Sequence Company",
                "currency_id": self.env.ref("base.USD").id,
            }
        )

    def test_01_duplicate_sequence_code_same_company_raises_on_create(self):
        # La secuencia 'invoice.correlative' ya existe por la instalación del módulo.
        # Intentar crear otra con el mismo código debe fallar.
        with self.assertRaises(ValidationError):
            self.env["ir.sequence"].create(
                {
                    "name": "Duplicated Sequence",
                    "code": "invoice.correlative",
                    "padding": 4,
                    "number_next_actual": 1,
                    "company_id": self.company.id,
                }
            )

    def test_02_duplicate_sequence_code_in_other_company_is_allowed(self):
        self.env["ir.sequence"].create(
            {
                "name": "Company One Sequence",
                "code": "test.sequence.other.company",
                "padding": 4,
                "number_next_actual": 1,
                "company_id": self.company.id,
            }
        )

        sequence = self.env["ir.sequence"].create(
            {
                "name": "Company Two Sequence",
                "code": "test.sequence.other.company",
                "padding": 4,
                "number_next_actual": 1,
                "company_id": self.other_company.id,
            }
        )

        self.assertTrue(sequence)
        self.assertEqual(sequence.company_id, self.other_company)

    def test_03_write_duplicate_sequence_code_same_company_raises(self):
        # Intentar cambiar el código de una secuencia a 'invoice.correlative' (que ya existe)
        sequence_to_update = self.env["ir.sequence"].create(
            {
                "name": "Sequence To Update",
                "code": "test.sequence.write.target",
                "padding": 4,
                "number_next_actual": 1,
                "company_id": self.company.id,
            }
        )

        with self.assertRaises(ValidationError):
            sequence_to_update.write({"code": "invoice.correlative"})

    def test_04_write_same_code_without_duplicates_is_allowed(self):
        sequence = self.env["ir.sequence"].create(
            {
                "name": "Single Sequence",
                "code": "test.sequence.single.write",
                "padding": 4,
                "number_next_actual": 1,
                "company_id": self.company.id,
            }
        )

        sequence.write({"name": "Single Sequence Updated"})

        self.assertEqual(sequence.name, "Single Sequence Updated")

    def test_05_duplicate_generic_sequence_code_is_allowed(self):
        """Test that duplicate codes are allowed if they are NOT 'invoice.correlative'."""
        code = "test.sequence.duplicate.allowed"
        self.env["ir.sequence"].create(
            {
                "name": "First Sequence",
                "code": code,
                "padding": 4,
                "number_next_actual": 1,
                "company_id": self.company.id,
            }
        )

        # This should NOT raise ValidationError now
        second_sequence = self.env["ir.sequence"].create(
            {
                "name": "Second Sequence",
                "code": code,
                "padding": 4,
                "number_next_actual": 1,
                "company_id": self.company.id,
            }
        )
        self.assertTrue(second_sequence)
        self.assertEqual(second_sequence.code, code)