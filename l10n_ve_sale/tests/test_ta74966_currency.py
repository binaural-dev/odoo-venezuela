"""TA-74966: fecha de la tasa en ventas y unificacion del calculo alterno.

Cada test esta construido para FALLAR si se revierte el cambio que verifica.
"""

from datetime import timedelta
import logging

from odoo import fields
from odoo.tools import float_round
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestTa74966Currency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.eur = self.env.ref("base.EUR")
        self.eur.active = True

        self.company.write({
            "currency_id": self.ves.id,
            "foreign_currency_id": self.usd.id,
        })

        self.today = fields.Date.today()
        self.past = self.today - timedelta(days=30)

        # 1 USD = 50 VES hoy, 1 USD = 25 VES hace 30 dias
        self._set_rate(self.usd, self.today, 50.0)
        self._set_rate(self.usd, self.past, 25.0)

        self.partner = self.env["res.partner"].create({"name": "Partner TA74966"})
        self.product = self.env["product.product"].create({
            "name": "Producto TA74966",
            "list_price": 100.0,
        })

    def _set_rate(self, currency, date, ves_per_unit):
        rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", currency.id),
            ("company_id", "=", self.company.id),
            ("name", "=", date),
        ], limit=1)
        vals = {"inverse_company_rate": ves_per_unit}
        if rate:
            rate.write(vals)
            return rate
        vals.update({
            "currency_id": currency.id,
            "company_id": self.company.id,
            "name": date,
        })
        return self.env["res.currency.rate"].create(vals)

    def _pricelist(self, currency):
        """Pricelist en la moneda pedida.

        sale.order.currency_id sale del pricelist, asi que fijarlo en el
        create() no basta para garantizar la moneda de la orden.
        """
        return self.env["product.pricelist"].create({
            "name": f"PL TA74966 {currency.name}",
            "currency_id": currency.id,
            "company_id": self.company.id,
        })

    def _create_order(self, currency=None, date_order=None, price_unit=1000.0,
                      company=None):
        currency = currency or self.ves
        company = company or self.company
        order = self.env["sale.order"].with_company(company).create({
            "partner_id": self.partner.id,
            "pricelist_id": self._pricelist(currency).id,
            "company_id": company.id,
            "date_order": date_order or fields.Datetime.now(),
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": price_unit,
            })],
        })
        self.assertEqual(
            order.currency_id, currency,
            "El pricelist debe fijar la moneda de la orden"
        )
        return order

    # ── foreign_rate_date ────────────────────────────────────────────

    def test_01_foreign_rate_date_always_has_a_value(self):
        """foreign_rate_date nunca queda vacio.

        Al crear la orden el ORM aplica los defaults y NO ejecuta
        _compute_rate (foreign_rate tiene su propio default), asi que el campo
        depende de tener default propio.

        REVERSION: sin el default el campo nace vacio y todo lo que cuelga de
        el -- la conversion de las lineas y la fecha que hereda la factura --
        cae al respaldo de date_order.
        """
        self.company.update_sale_order_rate_using_date_order = False
        order = self._create_order()
        self.assertTrue(
            order.foreign_rate_date,
            "foreign_rate_date debe tener valor incluso con la tasa congelada, "
            "que es la configuracion por defecto"
        )

    def test_02_header_rate_and_line_use_the_same_rate(self):
        """La tasa que muestra la orden y la que aplican sus lineas deben ser
        la misma.

        Es el descuadre de fondo: al crear la orden, foreign_rate sale de su
        default (calculado con la fecha de HOY) mientras que la linea convertia
        con date_order. Con una orden fechada en el pasado, la cabecera decia
        una tasa y las lineas usaban otra.

        REVERSION: si la linea vuelve a convertir con date_order en vez de
        foreign_rate_date, este test falla con 40.0 != 20.0.
        """
        order = self._create_order(
            date_order=fields.Datetime.now() - timedelta(days=30)
        )
        # La cabecera toma la tasa de hoy (50) por su default
        self.assertAlmostEqual(order.foreign_rate, 50.0, places=2)
        # y la linea debe usar esa misma tasa: 1000 / 50 = 20 USD
        self.assertAlmostEqual(
            order.order_line.foreign_price, 20.0, places=2,
            msg=f"La linea uso otra tasa que la cabecera: "
                f"{order.order_line.foreign_price} (esperado 20.0 = 1000/50)"
        )
        self.assertAlmostEqual(
            order.order_line.foreign_price,
            order.order_line.price_unit / order.foreign_rate,
            places=4,
            msg="foreign_price de la linea no corresponde a foreign_rate de la orden"
        )

    def test_03_frozen_rate_and_date_survive_confirmation(self):
        """Con la tasa congelada, confirmar mueve date_order pero ni la tasa ni
        su fecha cambian, y las lineas siguen coherentes.

        El core reescribe date_order con la fecha de confirmacion
        (_prepare_confirmation_values).

        REVERSION: sin foreign_rate_date, al confirmar la linea se recalculaba
        con la fecha de confirmacion aunque la tasa de la orden siguiera
        congelada.
        """
        self.company.update_sale_order_rate_using_date_order = False

        order = self._create_order(
            date_order=fields.Datetime.now() - timedelta(days=30)
        )
        rate_before = order.foreign_rate
        rate_date_before = order.foreign_rate_date
        price_before = order.order_line.foreign_price

        order.action_confirm()

        self.assertEqual(
            order.date_order.date(), self.today,
            "El core debe haber movido date_order a la fecha de confirmacion"
        )
        self.assertEqual(
            order.foreign_rate_date, rate_date_before,
            "foreign_rate_date no debe moverse al confirmar con la tasa congelada"
        )
        self.assertAlmostEqual(order.foreign_rate, rate_before, places=4)
        self.assertAlmostEqual(
            order.order_line.foreign_price, price_before, places=6,
            msg="La linea se recalculo al confirmar pese a la tasa congelada"
        )

    def test_04_invoice_inherits_rate_date(self):
        """Con "usar la tasa de la orden en la factura", _prepare_invoice pasa
        foreign_rate_date como invoice_date.

        En esta localizacion invoice_date es la fecha de la TASA; la fecha
        visible del documento es invoice_date_display.

        REVERSION: si se pasa date_order, una orden confirmada dias despues
        factura con la tasa del dia de confirmacion en vez de la suya.
        """
        self.company.update_sale_order_rate_using_date_order = False
        self.company.use_invoice_rate_from_sale_order = True

        order = self._create_order(
            date_order=fields.Datetime.now() - timedelta(days=30)
        )
        # Se simula una orden creada hace 30 dias: su tasa se sello aquel dia.
        # El campo es readonly=False, asi que admite el valor y el compute no
        # lo pisa mientras la tasa siga congelada.
        order.foreign_rate_date = self.past
        rate_date = order.foreign_rate_date

        order.action_confirm()

        self.assertNotEqual(
            order.date_order.date(), rate_date,
            "El escenario exige que date_order y la fecha de la tasa difieran"
        )
        invoice_vals = order._prepare_invoice()
        self.assertEqual(
            invoice_vals.get("invoice_date"), rate_date,
            "La factura debe heredar la fecha de la tasa, no date_order"
        )

    def test_05_invoice_does_not_inherit_when_disabled(self):
        """Sin el flag, la factura no hereda fecha: usa la suya.

        REVERSION: pasar siempre la fecha de la orden romperia el caso normal,
        en el que la factura debe convertir a su propia tasa.
        """
        self.company.use_invoice_rate_from_sale_order = False

        order = self._create_order()
        order.action_confirm()

        invoice_vals = order._prepare_invoice()
        self.assertNotIn(
            "invoice_date", invoice_vals,
            "Sin el flag no se debe forzar la fecha de la tasa en la factura"
        )

    # ── totales en moneda de compania ────────────────────────────────

    def test_06_amount_signed_comes_from_tax_totals(self):
        """Los totales en moneda de compania se leen de tax_totals, no se
        vuelven a convertir con _convert().

        REVERSION: una segunda conversion puede diferir por redondeo del
        total que ya calculo el motor de impuestos.
        """
        order = self._create_order(currency=self.usd, price_unit=33.335)

        tax_totals = order.tax_totals if isinstance(order.tax_totals, dict) else {}
        self.assertAlmostEqual(
            order.amount_untaxed_total_signed,
            tax_totals.get("base_amount", 0),
            places=2,
            msg="amount_untaxed_total_signed no sale de tax_totals"
        )
        self.assertAlmostEqual(
            order.amount_total_signed,
            tax_totals.get("total_amount", 0),
            places=2,
            msg="amount_total_signed no sale de tax_totals"
        )

    def test_07_foreign_totals_come_from_tax_totals_in_third_currency(self):
        """En una tercera moneda los totales alternos tambien salen de
        tax_totals.

        REVERSION: la rama que convertia el total con _convert() daba un valor
        que no cuadraba con la suma de los foreign_subtotal de las lineas.
        """
        self._set_rate(self.eur, self.today, 55.0)   # 1 EUR = 55 VES
        order = self._create_order(currency=self.eur, price_unit=33.335)

        tax_totals = order.tax_totals if isinstance(order.tax_totals, dict) else {}
        self.assertAlmostEqual(
            order.foreign_untaxed_total,
            tax_totals.get("base_amount_foreign_currency", 0),
            places=2,
            msg="foreign_untaxed_total no sale de tax_totals"
        )
        self.assertAlmostEqual(
            order.foreign_total_billed,
            tax_totals.get("total_amount_foreign_currency", 0),
            places=2,
            msg="foreign_total_billed no sale de tax_totals"
        )

    # ── precision ────────────────────────────────────────────────────

    def test_08_foreign_price_keeps_field_precision(self):
        """foreign_price se redondea a "Foreign Product Price", cuya precision
        es configurable, y no a los decimales de la moneda destino.

        REVERSION: con el redondeo por defecto de _convert(), 0,0567 VES / 50
        = 0,001134 USD se guardaria como 0,00, y el valor de la orden dejaria
        de coincidir con el de la factura que salga de ella.
        """
        precision = self.env["decimal.precision"].precision_get(
            "Foreign Product Price"
        )
        self.assertGreater(precision, 2)

        order = self._create_order(price_unit=0.0567)
        # Esperado segun la precision configurada, no un valor con decimales fijos
        expected = float_round(0.0567 / 50.0, precision_digits=precision)
        self.assertAlmostEqual(
            order.order_line.foreign_price, expected, places=precision,
            msg=f"foreign_price perdio precision: "
                f"{order.order_line.foreign_price} (esperado {expected})"
        )
        self.assertNotEqual(order.order_line.foreign_price, 0.0)
