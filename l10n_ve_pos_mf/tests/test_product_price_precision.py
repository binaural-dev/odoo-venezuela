"""Precisiones de precio para la máquina fiscal (ticket 16356).

La máquina fiscal solo admite 2 decimales en el precio unitario: el módulo
pone "Product Price" y "Foreign Product Price" en 2 al instalarse o
actualizarse. Se pueden cambiar, pero el formulario lo advierte y el chatter
de la precisión registra el cambio.
"""

from odoo.tests import TransactionCase, tagged

FISCAL_PRECISIONS = {
    "Product Price": "product.decimal_price",
    "Foreign Product Price": "l10n_ve_accountant.alternative_price_product",
}


@tagged("post_install", "-at_install", "l10n_ve_pos_mf")
class TestProductPricePrecision(TransactionCase):
    def _onchange_digits(self, precision, digits):
        draft = precision.new({"name": precision.name, "digits": digits}, origin=precision)
        return draft._onchange_digits_fiscal_price_warning()

    def test_price_precisions_have_two_digits(self):
        for name in FISCAL_PRECISIONS:
            with self.subTest(precision=name):
                self.assertEqual(self.env["decimal.precision"].precision_get(name), 2)

    def test_changing_price_precision_is_allowed_and_tracked(self):
        for name, xmlid in FISCAL_PRECISIONS.items():
            with self.subTest(precision=name):
                precision = self.env.ref(xmlid)
                previous_tracking = precision.message_ids.tracking_value_ids
                precision.digits = 4
                self.env.flush_all()
                self.env.cr.flush()

                self.assertEqual(self.env["decimal.precision"].precision_get(name), 4)
                tracking = (
                    precision.message_ids.tracking_value_ids - previous_tracking
                ).filtered(lambda value: value.field_id.name == "digits")
                self.assertEqual(len(tracking), 1)
                self.assertEqual(tracking.old_value_integer, 2)
                self.assertEqual(tracking.new_value_integer, 4)

    def test_onchange_warns_when_leaving_two_digits(self):
        for name, xmlid in FISCAL_PRECISIONS.items():
            with self.subTest(precision=name):
                result = self._onchange_digits(self.env.ref(xmlid), 6)
                self.assertIn(name, result["warning"]["message"])

    def test_onchange_does_not_warn_with_two_digits(self):
        for xmlid in FISCAL_PRECISIONS.values():
            with self.subTest(precision=xmlid):
                self.assertIsNone(self._onchange_digits(self.env.ref(xmlid), 2))

    def test_migration_sets_price_precisions_to_two_digits(self):
        """Bases donde el módulo ya estaba instalado (con 6 decimales)."""
        precisions = self.env["decimal.precision"].browse(
            [self.env.ref(xmlid).id for xmlid in FISCAL_PRECISIONS.values()]
        )
        precisions.digits = 6
        self.env["decimal.precision"]._set_fiscal_price_digits()
        for name in FISCAL_PRECISIONS:
            with self.subTest(precision=name):
                self.assertEqual(self.env["decimal.precision"].precision_get(name), 2)

    def test_onchange_does_not_warn_on_other_precisions(self):
        other = self.env["decimal.precision"].create(
            {"name": "Precisión de prueba 16356", "digits": 2}
        )
        self.assertIsNone(self._onchange_digits(other, 6))
