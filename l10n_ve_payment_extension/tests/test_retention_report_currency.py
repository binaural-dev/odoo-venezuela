from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "retention_report_currency")
class TestRetentionLineReportCurrency(TransactionCase):
    """Los importes del reporte dicen en que moneda estan.

    La vista SQL mete en las MISMAS columnas los importes en moneda de
    compania o los de divisa segun `use_foreign_currency`, y los campos eran
    `Float` pelados. Un usuario leia un numero sin saber su moneda, y la
    moneda cambiaba segun la compania desde la que se mirara.
    """

    def test_amount_fields_are_monetary_and_anchored(self):
        fields_def = self.env["retention.line.report"]._fields
        self.assertIn("currency_id", fields_def)
        for name in ("iva_amount", "invoice_amount", "retention_amount"):
            self.assertEqual(
                fields_def[name].type, "monetary",
                "%s es un importe monetario del reporte" % name,
            )
            self.assertEqual(fields_def[name].currency_field, "currency_id")

    def test_query_selects_a_currency_next_to_the_amounts(self):
        """La moneda y los importes se deciden en el mismo sitio.

        Si alguien cambia las columnas de importe sin tocar la moneda, la
        vista volveria a mostrar cifras sin moneda o con la equivocada.
        """
        select = self.env["retention.line.report"]._select()
        self.assertIn("AS currency_id", select)
        # Las dos ramas -compañía y divisa- tienen que traer su moneda.
        self.assertEqual(select.count("AS currency_id"), 1)

    def test_report_rows_carry_a_currency(self):
        rows = self.env["retention.line.report"].search([], limit=5)
        for row in rows:
            self.assertTrue(
                row.currency_id,
                "una fila del reporte no puede venir sin moneda",
            )
