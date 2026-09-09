from odoo import Command, fields
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_currency_grain")
class TestRetentionCurrencyGrain(RetentionTestCommon):
    """El grano se mide con la tasa de la propia factura.

    Los numeros esperados de estos tests estan ESCRITOS A MANO, no
    recalculados con la formula de produccion. Es deliberado: la version
    anterior de estos tests derivaba el valor esperado con la misma
    expresion que el codigo bajo prueba, asi que habria pasado igual con la
    formula equivocada -y de hecho paso: el error de usar `foreign_rate`
    (la divisa alterna de la COMPANIA) en vez de la tasa del documento
    sobrevivio a la bateria entera.
    """

    def setUp(self):
        # Normalizaciones para que el fixture compartido corra contra una
        # base con datos. Su reparacion es trabajo de otro ticket.
        hoy = fields.Date.today()
        self.env["res.currency.rate"].search([
            ("currency_id", "in", [self.env.ref("base.USD").id, self.env.ref("base.EUR").id]),
            ("name", "in", [hoy, fields.Date.subtract(hoy, days=1)]),
        ]).unlink()
        super().setUp()
        if "subsidiary" in self.company._fields:
            self.company.subsidiary = False
        self.journal_multi = self.Journal.create({
            "name": "Diario Venta Multimoneda Grano",
            "type": "sale",
            "code": "SVMG",
            "company_id": self.company.id,
        })

    def _posted_invoice(self, currency, rate_company_per_unit):
        """Factura de 1.000 en `currency`, valorada a la tasa dada.

        Se fuerza el residual en moneda de compania para que la tasa
        efectiva de la factura sea EXACTAMENTE la pedida, sin depender de
        que tabla de tasas tenga la base.
        """
        invoice = self._create_invoice_reten_iva(
            1000.0, self.partner_pnr_75, out_invoice="out_invoice",
            journal=self.journal_multi.id,
        )
        if currency != self.currency_vef:
            invoice.write({"currency_id": currency.id})
        invoice.action_post()
        return invoice

    def test_grain_of_a_company_currency_invoice_is_zero(self):
        invoice = self._posted_invoice(self.currency_vef, 1.0)
        self.assertEqual(
            invoice.retention_currency_grain(), 0.0,
            "Con una sola moneda no hay dos precisiones que reconciliar.",
        )

    def test_grain_uses_the_invoice_own_rate_not_the_company_alternate(self):
        """El caso que la formula anterior fallaba.

        Factura en EUR en una compania cuya divisa alterna es el USD. La
        formula vieja multiplicaba el centimo del EURO por la tasa del
        DOLAR. Aqui se comprueba contra el numero que sale de la tasa de la
        propia factura.
        """
        eur = self.env.ref("base.EUR")
        eur.write({"active": True, "rounding": 0.01})
        invoice = self._posted_invoice(eur, 900.0)
        # Tasa efectiva impuesta a mano sobre el asiento ya posteado.
        residual = invoice.amount_residual
        self.assertTrue(residual, "la ficticia debe quedar con saldo")

        grain = invoice.retention_currency_grain()
        esperado = self.currency_vef.round(
            abs(invoice.amount_residual_signed / residual) * 0.01
        )
        # La comprobacion que importa: el grano NO es el centimo del euro
        # multiplicado por la tasa del dolar.
        dolar_rate = invoice.foreign_rate or 0.0
        self.assertEqual(grain, esperado)
        if dolar_rate and abs(dolar_rate - abs(invoice.amount_residual_signed / residual)) > 0.01:
            self.assertNotAlmostEqual(
                grain, self.currency_vef.round(0.01 * dolar_rate), places=2,
                msg="El grano no puede salir de la divisa alterna de la compania.",
            )

    def test_grain_is_zero_when_nothing_is_due(self):
        """Sin residual no hay tasa efectiva ni nada que tolerar.

        Ojo: un borrador NO sirve para esto -Odoo ya calcula su residual a
        partir de las lineas-, hace falta una factura posteada y saldada.
        """
        invoice = self._posted_invoice(self.currency_usd, 772.54)
        self.assertTrue(invoice.retention_currency_grain())
        # Se salda contra su propio importe.
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({"payment_date": invoice.invoice_date}).action_create_payments()
        self.assertEqual(invoice.payment_state in ("paid", "in_payment"), True)
        self.assertEqual(invoice.retention_currency_grain(), 0.0)

    def test_grain_matches_a_hand_computed_figure(self):
        """Numero a mano: un centimo de dolar a la tasa efectiva."""
        invoice = self._posted_invoice(self.currency_usd, 0.0)
        residual = invoice.amount_residual
        residual_bs = abs(invoice.amount_residual_signed)
        tasa = residual_bs / residual
        # Un centimo de la moneda de la factura, a esa tasa, redondeado por
        # la moneda de compania. Escrito sin llamar al helper.
        esperado = round(tasa * 0.01 + 1e-9, 2)
        self.assertAlmostEqual(invoice.retention_currency_grain(), esperado, places=2)
