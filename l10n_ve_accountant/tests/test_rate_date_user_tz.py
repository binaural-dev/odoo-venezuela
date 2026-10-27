from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, freeze_time, tagged


@tagged("post_install", "-at_install", "l10n_ve_accountant_rate_tz")
class TestRateDateUserTz(TransactionCase):
    """
    A partir de las 8 pm en Venezuela (UTC-4) la fecha UTC ya es la del día siguiente:
    la tasa de respaldo "de hoy" debe buscarse con la fecha local del usuario.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.usd = cls.env.ref("base.USD")
        cls.company.write(
            {
                "currency_id": cls.env.ref("base.VEF").id,
                "foreign_currency_id": cls.usd.id,
            }
        )
        cls.env.user.tz = "America/Caracas"
        cls.env = cls.env(context=dict(cls.env.context, tz="America/Caracas"))
        # Solo existe la tasa del día local (26); la del 27 aún no se ha cargado.
        cls.env["res.currency.rate"].create(
            {
                "name": date(2026, 10, 26),
                "currency_id": cls.usd.id,
                "company_id": cls.company.id,
                "company_rate": 1.0 / 40.0,
                "inverse_company_rate": 40.0,
            }
        )
        cls.partner = cls.env["res.partner"].create({"name": "Partner TZ"})
        cls.product = cls.env["product.product"].create(
            {"name": "Service TZ", "type": "service", "list_price": 100.0}
        )

    # 2026-10-27 01:00 UTC = 2026-10-26 21:00 en Caracas
    @freeze_time("2026-10-27 01:00:00")
    def test_draft_invoice_without_date_uses_local_day_rate(self):
        """Una factura en borrador sin fecha, a las 9 pm, toma la tasa del día local."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "price_unit": 100.0})],
            }
        )
        invoice.foreign_rate = 0.0
        # Sin invoice_date la tasa se busca con la fecha de respaldo "de hoy".
        invoice.invoice_date = False
        self.assertAlmostEqual(invoice.foreign_rate, 40.0)

    @freeze_time("2026-10-27 01:00:00")
    def test_explicit_document_date_is_not_shifted(self):
        """Una fecha de documento explícita no se corrige: el 27 sigue buscando la tasa del 27."""
        with self.assertRaisesRegex(UserError, "There is no rate assigned"):
            self.env["account.move"].create(
                {
                    "move_type": "out_invoice",
                    "partner_id": self.partner.id,
                    "invoice_date": date(2026, 10, 27),
                    "invoice_line_ids": [(0, 0, {"product_id": self.product.id, "price_unit": 100.0})],
                }
            )
