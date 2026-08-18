import logging

from odoo.tests import tagged, Form
from odoo import fields

from .test_withholding_common_VEF import RetentionTestCommon

_logger = logging.getLogger(__name__)


@tagged("iva_retention_usd_bug", "-at_install", "post_install")
class TestRetentionIvaUsdExchangeRateBug(RetentionTestCommon):
    """
    TDD (fase RED) - Bug de conciliación de retención de IVA sobre facturas
    en moneda extranjera USD (multi-currency nativo de Odoo).

    Escenario:
    - Factura de venta en USD real, fechada AYER (tasa 380.0000 Bs/USD).
      Base 100 USD + IVA 16% = 116 USD.
    - Retención de IVA (75%) generada automáticamente HOY (tasa 390.2944
      Bs/USD).
    - La retención en Bs es: 16 USD * 380.0000 * 75% = 4560.00 Bs.

    Comportamiento CORRECTO esperado: al reconciliar la retención contra la
    factura, el monto en Bs (4560.00) debe reconvertirse a USD usando la
    tasa de la FACTURA ORIGINAL (380.0000), es decir 4560.00 / 380.0000 =
    12.00 USD exactos. Esto debe dejar un residual de 116.00 - 12.00 =
    104.00 USD pendientes en la factura.

    Comportamiento CON BUG (actual): el sistema reconvierte 4560.00 Bs a
    USD usando la tasa del DÍA DE LA RETENCIÓN (390.2944), es decir
    4560.00 / 390.2944 ~= 11.6852 USD, dejando un residual incorrecto de
    ~104.3148 USD en lugar de 104.00 USD.

    Este test debe FALLAR mientras el bug no esté corregido (fase RED).
    """

    def _create_invoice_usd_reten_iva(self, amount, partner, journal):
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        with Form(
            self.env["account.move"].with_context(
                default_move_type="out_invoice", default_journal_id=journal.id
            )
        ) as inv_form:
            inv_form.partner_id = partner
            inv_form.invoice_date = yesterday
            inv_form.currency_id = self.currency_usd

        invoice = inv_form.save()
        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_iva
                line.quantity = 1
                line.price_unit = amount

        invoice = inv_form_edit.save()
        return invoice

    def test_retention_iva_usd_invoice_uses_invoice_exchange_rate(self):
        self.company.auto_fill_retention_amount_iva = True

        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        # El fixture compartido crea las tasas históricas usando
        # company_rate/inverse_company_rate antes de que la moneda de la
        # compañía quede fijada en VEF, lo que corrompe el valor calculado
        # del campo `rate`. Se recrean aquí explícitamente con `rate` para
        # este test.
        self.currency_usd.rate_ids.filtered(
            lambda r: r.name in (fields.Date.today(), yesterday)
        ).unlink()
        self.env["res.currency.rate"].create(
            [
                {
                    "currency_id": self.currency_usd.id,
                    "name": yesterday,
                    "rate": 1 / 380.0,
                },
                {
                    "currency_id": self.currency_usd.id,
                    "name": fields.Date.today(),
                    "rate": 1 / self.rate,
                },
            ]
        )

        invoice = self._create_invoice_usd_reten_iva(
            amount=100.0, partner=self.partner_pnr_75, journal=self.sale_journal
        )

        self.assertEqual(invoice.currency_id, self.currency_usd)
        self.assertAlmostEqual(invoice.amount_total, 116.0, places=2)

        iva_lines = invoice.line_ids.filtered(lambda l: l.tax_ids)
        self.assertAlmostEqual(sum(iva_lines.mapped("price_total")) - sum(iva_lines.mapped("price_subtotal")), 16.0, places=2)

        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id
        # La retención de cliente queda en borrador hasta postearla; se
        # postea explícitamente para forzar la reconciliación en este test.
        ret.number = ret.number or "12345678901234"
        ret.action_post()

        receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        self.assertEqual(len(receivable_line), 1)

        # Comportamiento CORRECTO esperado: la retención debe cancelar
        # exactamente $12.00 USD (75% de $16 de IVA), usando la tasa de la
        # factura original (380.0000) y no la tasa del día de la retención
        # (390.2944). Con el bug actual el residual queda en ~104.3148.
        self.assertAlmostEqual(
            receivable_line.amount_residual_currency,
            104.00,
            places=2,
            msg=(
                "La retención debería cancelar exactamente $12.00 USD (75%"
                " de $16 de IVA), dejando $104.00 pendientes, usando la tasa"
                " de la factura original (380.0000) y no la tasa del día de"
                " la retención (390.2944)."
            ),
        )

        pay = ret.payment_ids[0]
        self.assertAlmostEqual(
            pay.retention_foreign_amount,
            12.00,
            places=2,
            msg=(
                "El monto en moneda extranjera (USD) de la retención debe"
                " ser $12.00, calculado con la tasa de la factura original"
                " (380.0000) y no con la tasa del día de la retención"
                " (390.2944)."
            ),
        )

    def test_retention_iva_usd_invoice_uses_invoice_exchange_rate_bidirectional(self):
        """
        Prueba de bidireccionalidad pedida explícitamente por el ticket 14574:
        factura emitida a tasa ALTA (764,3486 Bs/USD) y retención registrada
        al día siguiente a tasa MENOR (761,2167 Bs/USD), por 9.172,19 Bs (75%
        del IVA calculado con la tasa de la factura).

        Con el bug: 9.172,19 / 761,2167 ~= $12,05 (abono de más), dejando la
        factura en $103,95 en vez de $104,00.

        Comportamiento correcto esperado (igual que en el caso de tasa al
        alza): la retención cancela $12,00 USD exactos, dejando $104,00
        pendientes, sin importar si la tasa subió o bajó entre la fecha de
        la factura y la fecha de la retención.
        """
        self.company.auto_fill_retention_amount_iva = True

        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        self.currency_usd.rate_ids.filtered(
            lambda r: r.name in (fields.Date.today(), yesterday)
        ).unlink()
        self.env["res.currency.rate"].create(
            [
                {
                    "currency_id": self.currency_usd.id,
                    "name": yesterday,
                    "rate": 1 / 764.3486,
                },
                {
                    "currency_id": self.currency_usd.id,
                    "name": fields.Date.today(),
                    "rate": 1 / 761.2167,
                },
            ]
        )

        invoice = self._create_invoice_usd_reten_iva(
            amount=100.0, partner=self.partner_pnr_75, journal=self.sale_journal
        )

        self.assertEqual(invoice.currency_id, self.currency_usd)
        self.assertAlmostEqual(invoice.amount_total, 116.0, places=2)

        invoice.generate_iva_retention = True
        invoice.with_context(move_action_post_alert=True).action_post()

        ret = invoice.retention_iva_line_ids[0].retention_id
        ret.number = ret.number or "12345678901235"
        ret.action_post()

        receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        self.assertEqual(len(receivable_line), 1)

        self.assertAlmostEqual(
            receivable_line.amount_residual_currency,
            104.00,
            places=2,
            msg=(
                "Con tasa a la baja, la retención debería seguir cancelando"
                " exactamente $12.00 USD (75% de $16 de IVA), dejando $104.00"
                " pendientes, en vez del abono excedente de ~$12.05 que"
                " produce el bug (usando la tasa de la retención en vez de"
                " la tasa de la factura)."
            ),
        )

        pay = ret.payment_ids[0]
        self.assertAlmostEqual(
            pay.retention_foreign_amount,
            12.00,
            places=2,
            msg=(
                "El monto en USD de la retención debe ser $12.00 exactos"
                " también cuando la tasa baja entre la fecha de la factura y"
                " la fecha de la retención."
            ),
        )
