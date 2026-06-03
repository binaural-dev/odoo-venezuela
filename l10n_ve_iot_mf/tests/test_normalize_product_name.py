from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestNormalizeProductName(TransactionCase):

    def setUp(self):
        super().setUp()
        self.move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.env["res.partner"].create({"name": "Test"}).id,
        })

    def _normalize(self, name):
        return self.move._normalize_product_name(name)

    def test_empty_string(self):
        self.assertEqual(self._normalize(""), "")

    def test_none(self):
        self.assertEqual(self._normalize(None), "")

    def test_no_change_needed(self):
        self.assertEqual(self._normalize("Product A"), "Product A")

    def test_remove_accents(self):
        """Los acentos deben eliminarse."""
        self.assertEqual(self._normalize("Café"), "Cafe")

    def test_remove_accents_multiple(self):
        self.assertEqual(self._normalize("Óptica Única"), "Optica Unica")

    def test_replace_special_chars_with_space(self):
        """Caracteres especiales deben reemplazarse por espacios."""
        self.assertEqual(self._normalize("Producto#1"), "Producto 1")

    def test_multiple_spaces_collapsed(self):
        """Múltiples espacios deben colapsarse a uno."""
        self.assertEqual(self._normalize("Product   A"), "Product A")

    def test_leading_trailing_spaces_trimmed(self):
        """Espacios al inicio/final deben recortarse."""
        self.assertEqual(self._normalize("  Product A  "), "Product A")

    def test_complex_normalization(self):
        """Caso complejo con acentos, símbolos y espacios."""
        result = self._normalize("   CAFÉ ESPECIAL%#   para\nti  ")
        self.assertEqual(result, "CAFE ESPECIAL para ti")

    def test_unicode_accents(self):
        self.assertEqual(self._normalize("ñandú"), "nandu")

    def test_numbers_and_letters(self):
        self.assertEqual(self._normalize("Ref-100/A"), "Ref 100 A")
