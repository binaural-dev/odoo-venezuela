"""TA-80647: recalculo por cambio de moneda del Pedido de Ventas a la Factura.

Espejo de lo que binaural_purchase hace con la Orden de Compra (TA-74966), con
dos diferencias propias de ventas:

* el enlace factura-orden es `sale_line_ids`, un Many2many;
* la factura puede llevar tarifa (`account_invoice_pricelist`), y esa tarifa
  tambien fija price_unit. Si define una regla para el producto, la conversion
  se aborta con error en vez de pisarla.
"""

from datetime import timedelta
import logging

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestTa80647InvoiceCurrency(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.company.write({
            "currency_id": self.ves.id,
            "foreign_currency_id": self.usd.id,
            "convert_currency_from_sale_order": True,
        })

        self.today = fields.Date.today()
        self._set_rate(self.usd, self.today, 50.0)

        self.partner = self.env["res.partner"].create({"name": "Partner TA80647"})
        self.product = self.env["product.product"].create({
            "name": "Producto TA80647",
            "list_price": 100.0,
        })
        self.eur = self.env.ref("base.EUR")
        self.eur.active = True
        self._set_rate(self.eur, self.today, 55.0)

        self.pl_usd = self._pricelist(self.usd)
        self.pl_ves = self._pricelist(self.ves)
        self.pl_eur = self._pricelist(self.eur)

    def _set_rate(self, currency, date, ves_per_unit):
        rate = self.env["res.currency.rate"].search([
            ("currency_id", "=", currency.id),
            ("company_id", "=", self.company.id),
            ("name", "=", date),
        ], limit=1)
        if rate:
            rate.inverse_company_rate = ves_per_unit
            return rate
        return self.env["res.currency.rate"].create({
            "currency_id": currency.id,
            "company_id": self.company.id,
            "name": date,
            "inverse_company_rate": ves_per_unit,
        })

    def _pricelist(self, currency):
        return self.env["product.pricelist"].create({
            "name": f"PL TA80647 {currency.name}",
            "currency_id": currency.id,
            "company_id": self.company.id,
        })

    def _so_and_invoice(self, price_unit=300.0, pricelist=None):
        """Orden + factura ligada por sale_line_ids."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": (pricelist or self.pl_usd).id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": price_unit,
            })],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        return order, invoice

    def test_01_converts_from_sale_order_at_invoice_rate(self):
        """Cotizacion en USD, factura pasada a VES: el precio se convierte a la
        tasa de la factura.

        Es el requerimiento del ticket: 300 USD a tasa 50 = 15.000 VES.
        """
        order, invoice = self._so_and_invoice(price_unit=300.0)
        self.assertEqual(invoice.currency_id, self.usd)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected = self.usd._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, expected, places=2,
            msg=f"El precio no se convirtio a la tasa de la factura: "
                f"{draft.invoice_line_ids.price_unit} (esperado {expected})"
        )

    def test_02_round_trip_restores_the_order_price(self):
        """Ida y vuelta USD -> VES -> USD dentro del mismo borrador: el precio
        vuelve al de la orden.

        REVERSION: con un guard que compare contra `_origin`, el segundo cambio
        se interpreta como "no cambio nada" y la factura queda en USD con el
        importe en bolivares (15.000 USD en vez de 300).
        """
        order, invoice = self._so_and_invoice(price_unit=300.0)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()
        converted = self.usd._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, converted, places=2
        )

        draft.currency_id = self.usd
        draft._onchange_currency_sync_from_so()

        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, 300.0, places=2,
            msg=f"Al volver a la moneda de la orden debe recuperarse su precio, "
                f"no quedarse con el de la otra moneda "
                f"({draft.invoice_line_ids.price_unit})"
        )

    def test_03_pricelist_rule_blocks_the_conversion(self):
        """Si la tarifa de la factura define una regla para el producto, la
        conversion se aborta con error.

        Las dos logicas escriben el mismo campo (price_unit): la tarifa via
        _compute_price_unit de account_invoice_pricelist y el recalculo via
        este onchange. Una pisaria a la otra, asi que se exige elegir.
        """
        if "pricelist_id" not in self.env["account.move"]._fields:
            self.skipTest("account_invoice_pricelist no esta instalado")

        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pl_ves.id,
            "applied_on": "0_product_variant",
            "product_id": self.product.id,
            "compute_price": "fixed",
            "fixed_price": 9999.0,
        })

        order, invoice = self._so_and_invoice(price_unit=300.0)

        draft = invoice.new(origin=invoice)
        draft.pricelist_id = self.pl_ves
        draft.currency_id = self.ves

        with self.assertRaises(UserError):
            draft._onchange_currency_sync_from_so()

    def test_04_no_conversion_when_disabled(self):
        """Sin el flag no se toca nada."""
        self.company.convert_currency_from_sale_order = False
        order, invoice = self._so_and_invoice(price_unit=300.0)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, 300.0, places=2,
            msg="Con el flag desactivado el precio no debe recalcularse"
        )

    def test_05_grouped_lines_are_left_alone(self):
        """Una linea de factura con varias lineas de venta detras no tiene un
        precio de origen unico, asi que se deja como esta."""
        order, invoice = self._so_and_invoice(price_unit=300.0)
        line = invoice.invoice_line_ids

        extra = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.product.id,
            "product_uom_qty": 1,
            "price_unit": 111.0,
        })
        line.sale_line_ids = [(4, extra.id)]
        self.assertEqual(len(line.sale_line_ids), 2)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, 300.0, places=2,
            msg="Las lineas agrupadas no deben recalcularse"
        )

    # ── el sentido inverso y las demas monedas que pide el ticket ────

    def test_06_converts_from_bs_order_to_foreign_invoice(self):
        """Cotizacion en Bs (Tarifa VES) y factura en moneda extranjera.

        El ticket lo pide explicitamente: "si la cotizacion es en Bs y la
        factura en ME el comportamiento de conversion debe realizarse tambien".

        Como USD es ademas la moneda alterna de la compania, esta es la rama
        que toma foreign_price de la linea de venta.
        """
        order, invoice = self._so_and_invoice(
            price_unit=15000.0, pricelist=self.pl_ves
        )
        self.assertEqual(invoice.currency_id, self.ves)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.usd
        draft._onchange_currency_sync_from_so()

        # 15.000 Bs a tasa 50 = 300 USD
        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, 300.0, places=2,
            msg=f"Bs -> ME no se convirtio: "
                f"{draft.invoice_line_ids.price_unit} (esperado 300)"
        )

    def test_07_converts_to_a_third_currency(self):
        """Tarifa EUR: el ticket habla de "Tarifa USD o EUR", asi que la
        conversion debe funcionar tambien hacia una moneda que no es ni la de
        la compania ni la alterna."""
        eur = self.env.ref("base.EUR")
        eur.active = True
        self._set_rate(eur, self.today, 55.0)   # 1 EUR = 55 Bs
        pl_eur = self._pricelist(eur)

        order, invoice = self._so_and_invoice(
            price_unit=15000.0, pricelist=self.pl_ves
        )

        draft = invoice.new(origin=invoice)
        draft.currency_id = eur
        draft._onchange_currency_sync_from_so()

        expected = self.ves._convert(
            15000.0, eur, self.company, self.today, round=False
        )
        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, expected, places=2,
            msg=f"No se convirtio a la tercera moneda: "
                f"{draft.invoice_line_ids.price_unit} (esperado {expected})"
        )

    def test_08_credit_note_is_not_converted(self):
        """Las notas de credito NO se recalculan.

        Una nota de credito o debito se emite siempre en base a su factura de
        origen; recalcularla desde el pedido de ventas la desalinearia del
        documento que rectifica. Por eso el onchange se limita a out_invoice.
        """
        order, invoice = self._so_and_invoice(price_unit=300.0)

        refund = self.env["account.move"].create({
            "move_type": "out_refund",
            "partner_id": self.partner.id,
            "invoice_origin": order.name,
            "invoice_date": self.today,
            "currency_id": self.usd.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 300.0,
                "sale_line_ids": [(6, 0, order.order_line.ids)],
            })],
        })

        draft = refund.new(origin=refund)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, 300.0, places=2,
            msg="La nota de credito no debe recalcularse desde el pedido"
        )

    # ── casos borde ──────────────────────────────────────────────────

    def test_09_lines_without_origin_are_ignored(self):
        """Secciones, notas y lineas agregadas a mano en la factura no tienen
        linea de venta detras: deben quedarse como estan y no romper nada."""
        order, invoice = self._so_and_invoice(price_unit=300.0)

        invoice.write({"invoice_line_ids": [
            (0, 0, {"display_type": "line_section", "name": "Seccion"}),
            (0, 0, {"display_type": "line_note", "name": "Nota"}),
            (0, 0, {
                "product_id": self.product.id,
                "quantity": 2,
                "price_unit": 77.0,
            }),
        ]})

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        manual = draft.invoice_line_ids.filtered(
            lambda l: not l.sale_line_ids and l.display_type == "product"
        )
        self.assertAlmostEqual(
            manual.price_unit, 77.0, places=2,
            msg="Una linea agregada a mano no procede de la orden y no debe "
                "recalcularse"
        )
        origen = draft.invoice_line_ids.filtered(lambda l: l.sale_line_ids)
        self.assertNotAlmostEqual(origen.price_unit, 300.0, places=2)

    def test_10_without_foreign_currency_configured(self):
        """Compania sin moneda alterna: la conversion normal debe seguir
        funcionando, porque solo la rama de moneda alterna la necesita."""
        self.company.foreign_currency_id = False
        order, invoice = self._so_and_invoice(price_unit=300.0)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected = self.usd._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        self.assertAlmostEqual(draft.invoice_line_ids.price_unit, expected, places=2)

    # Nota: no hay caso borde de "precio cero". l10n_ve_invoice lo impide con
    # la constraint _check_price_in_zero ("An invoice cannot have a line with a
    # price of zero"), asi que una factura con precio cero no puede existir en
    # esta localizacion.

    def test_12_discount_is_left_untouched(self):
        """El recalculo toca price_unit y nada mas: el descuento de la linea
        se respeta."""
        order, invoice = self._so_and_invoice(price_unit=300.0)
        invoice.invoice_line_ids.discount = 15.0

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        self.assertAlmostEqual(
            draft.invoice_line_ids.discount, 15.0, places=2,
            msg="El descuento no debe alterarse al convertir el precio"
        )

    def test_13_small_price_keeps_precision(self):
        """Un precio unitario pequeno no debe colapsar al convertir: se
        redondea a la precision de "Product Price", no a la de la moneda."""
        precision = self.env["decimal.precision"].precision_get("Product Price")
        self.assertGreater(precision, 2)

        order, invoice = self._so_and_invoice(price_unit=0.0567)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected = self.usd._convert(
            0.0567, self.ves, self.company, self.today, round=False
        )
        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, expected, places=4,
            msg=f"Se perdio precision: {draft.invoice_line_ids.price_unit}"
        )

    def test_14_invoice_without_origin_is_untouched(self):
        """Una factura que no viene de una orden no se toca, aunque el flag
        este activo."""
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "invoice_date": self.today,
            "currency_id": self.usd.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 300.0,
            })],
        })
        self.assertFalse(invoice.invoice_origin)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        self.assertAlmostEqual(draft.invoice_line_ids.price_unit, 300.0, places=2)

    def test_15_ui_flow_changing_the_pricelist(self):
        """El flujo real de la interfaz: el usuario cambia la TARIFA.

        Es el unico camino disponible en la UI. account_invoice_pricelist
        impide cambiar la moneda sin cambiar la tarifa (_check_currency:
        "Pricelist and Invoice need to use the same currency"), asi que el
        usuario cambia la tarifa, _compute_currency_id ajusta currency_id y eso
        dispara este onchange en cascada.

        REVERSION: si esa cascada se rompe -- por ejemplo cambiando el onchange
        a otro campo -- los demas tests seguirian pasando porque llaman al
        metodo a mano, y la funcionalidad estaria muerta en produccion.
        """
        if "pricelist_id" not in self.env["account.move"]._fields:
            self.skipTest("account_invoice_pricelist no esta instalado")

        order, invoice = self._so_and_invoice(price_unit=3140.2772)
        self.assertEqual(invoice.currency_id, self.usd)

        with Form(invoice) as form:
            form.pricelist_id = self.pl_ves

        self.assertEqual(
            invoice.currency_id, self.ves,
            "Cambiar la tarifa debe arrastrar la moneda de la factura"
        )
        # 3140,2772 USD a tasa 50 = 157.013,86 Bs (el ejemplo del ticket)
        self.assertAlmostEqual(
            invoice.invoice_line_ids.price_unit, 157013.86, places=2,
            msg=f"El precio no se recalculo al cambiar la tarifa: "
                f"{invoice.invoice_line_ids.price_unit}"
        )
        # y el monto alterno vuelve exacto al de la orden
        self.assertAlmostEqual(
            invoice.invoice_line_ids.foreign_price, 3140.2772, places=4,
            msg="foreign_price debe recalcularse solo y volver al valor original"
        )

    def test_16_changing_only_the_currency_is_not_a_valid_path(self):
        """Cambiar solo la moneda, dejando la tarifa, NO es un camino valido.

        account_invoice_pricelist lo impide con _check_currency
        ("Pricelist and Invoice need to use the same currency"). Este test lo
        deja visible: el unico camino por el que la funcionalidad se alcanza es
        cambiando la tarifa (test_15), y este documenta que el atajo esta
        cerrado por la propia localizacion.

        La constraint solo se evalua en tests con `force_check_currecy` en el
        contexto (el typo es del modulo OCA): sin ese flag se desactiva bajo
        config["test_enable"].
        """
        if "pricelist_id" not in self.env["account.move"]._fields:
            self.skipTest("account_invoice_pricelist no esta instalado")

        order, invoice = self._so_and_invoice(price_unit=300.0)
        self.assertEqual(invoice.pricelist_id, self.pl_usd)

        with self.assertRaises(UserError):
            invoice.with_context(force_check_currecy=True).write({
                "currency_id": self.ves.id,
            })

    # ── casos borde: duplicados y origen borrado ──────────────────────

    def test_17_duplicate_lines_same_product_price_and_qty_convert_independently(self):
        """Dos lineas del mismo producto, mismo precio y misma cantidad, cada
        una facturada por separado: cada una debe convertir con SU PROPIA
        linea de origen, sin cruzarse entre ellas.

        El emparejamiento es por la FK real (sale_line_ids), no por
        producto/precio/cantidad, asi que dos lineas identicas no se
        confunden entre si.
        """
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_usd.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
            ],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(len(invoice.invoice_line_ids), 2)
        for line in invoice.invoice_line_ids:
            self.assertEqual(len(line.sale_line_ids), 1)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected = self.usd._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        for line in draft.invoice_line_ids:
            self.assertAlmostEqual(
                line.price_unit, expected, places=2,
                msg="Cada linea duplicada debe convertir de forma "
                    "independiente, sin cruzarse con la otra"
            )

    def test_18_pricelist_rule_error_does_not_repeat_duplicate_product(self):
        """Con dos lineas del mismo producto bloqueadas por regla de tarifa,
        el mensaje de error no debe repetir el nombre del producto.

        REVERSION: sin deduplicar, "blocking" tendria el nombre dos veces y el
        mensaje diria "..., Producto X, Producto X" para la misma linea de
        productos.
        """
        if "pricelist_id" not in self.env["account.move"]._fields:
            self.skipTest("account_invoice_pricelist no esta instalado")

        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pl_ves.id,
            "applied_on": "0_product_variant",
            "product_id": self.product.id,
            "compute_price": "fixed",
            "fixed_price": 9999.0,
        })

        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_usd.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
            ],
        })
        order.action_confirm()
        invoice = order._create_invoices()

        draft = invoice.new(origin=invoice)
        draft.pricelist_id = self.pl_ves
        draft.currency_id = self.ves

        with self.assertRaises(UserError) as cm:
            draft._onchange_currency_sync_from_so()

        message = str(cm.exception)
        self.assertEqual(
            message.count(self.product.display_name), 1,
            msg=f"El producto no debe repetirse en el mensaje: {message}"
        )

    def test_19_deleted_invoice_line_is_simply_absent(self):
        """Si el usuario borra una linea de la factura antes de cambiar la
        tarifa, el onchange no la ve y no falla: solo procesa lo que queda."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_usd.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 111.0}),
            ],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        line_to_delete = invoice.invoice_line_ids.filtered(
            lambda l: l.price_unit == 111.0
        )

        draft = invoice.new(origin=invoice)
        draft.invoice_line_ids = [(2, line_to_delete.id, 0)]
        self.assertEqual(len(draft.invoice_line_ids), 1)

        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected = self.usd._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        self.assertAlmostEqual(draft.invoice_line_ids.price_unit, expected, places=2)

    def test_20_orphan_line_without_sale_line_is_skipped(self):
        """Una linea de factura cuya sale.order.line de origen ya no existe
        (sale_line_ids vacio) se salta sin error, no se le adivina un
        origen por producto/precio."""
        order, invoice = self._so_and_invoice(price_unit=300.0)
        original_price = invoice.invoice_line_ids.price_unit

        draft = invoice.new(origin=invoice)
        draft.invoice_line_ids.sale_line_ids = [(5, 0, 0)]
        self.assertFalse(draft.invoice_line_ids.sale_line_ids)

        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, original_price, places=2,
            msg="Sin sale_line_ids, la linea no debe convertirse"
        )

    def test_21_archived_product_line_is_skipped_without_error(self):
        """Producto archivado antes de cambiar la tarifa: la linea no debe
        reventar ni bloquear la conversion de las demas."""
        archived = self.env["product.product"].create({
            "name": "Producto a archivar",
            "list_price": 50.0,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_usd.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
                (0, 0, {"product_id": archived.id, "product_uom_qty": 1,
                        "price_unit": 50.0}),
            ],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        archived.active = False

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        # No debe lanzar excepcion pese al producto archivado
        draft._onchange_currency_sync_from_so()

        expected = self.usd._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        converted = draft.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product
        )
        self.assertAlmostEqual(converted.price_unit, expected, places=2)

    def test_22_reordering_invoice_lines_does_not_affect_conversion(self):
        """Cambiar el orden (sequence) de las lineas de la factura no debe
        afectar la conversion: el emparejamiento es por sale_line_ids de cada
        registro, nunca por posicion/indice contra order.order_line."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_usd.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
            ],
        })
        second_product = self.env["product.product"].create({
            "name": "Segundo producto TA80647", "list_price": 20.0,
        })
        order.order_line = [(0, 0, {
            "product_id": second_product.id, "product_uom_qty": 1,
            "price_unit": 111.0,
        })]
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(len(invoice.invoice_line_ids), 2)

        # Se invierte el orden de las lineas en la factura, tal como haria un
        # usuario arrastrando filas en la UI.
        lines = invoice.invoice_line_ids
        lines[0].sequence, lines[1].sequence = lines[1].sequence + 1, lines[0].sequence

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected_300 = self.usd._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        expected_111 = self.usd._convert(
            111.0, self.ves, self.company, self.today, round=False
        )
        line_300 = draft.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product
        )
        line_111 = draft.invoice_line_ids.filtered(
            lambda l: l.product_id == second_product
        )
        self.assertAlmostEqual(
            line_300.price_unit, expected_300, places=2,
            msg="La linea de 300 debe seguir convirtiendo a partir de SU "
                "propio origen, aunque haya cambiado de posicion"
        )
        self.assertAlmostEqual(
            line_111.price_unit, expected_111, places=2,
            msg="La linea de 111 no debe heredar el valor de la otra por "
                "el reordenamiento"
        )

    # ── cobertura de las 3 ramas del onchange, con monedas distintas ──
    #
    # En los tests anteriores la moneda de la orden (USD) coincide con la
    # moneda alterna de la compania (tambien USD), asi que la rama
    # "elif foreign_currency" y la rama "else" (_convert generico) quedaban
    # indistinguibles entre si. Con una orden en una TERCERA moneda (EUR --
    # ni la de compania VES ni la alterna USD) las tres ramas del if/elif/else
    # se ejercitan por separado.

    def test_23_order_in_company_currency_to_foreign_converts_at_invoice_date(self):
        """Orden en VES (moneda de la compania), factura pasada a USD (la
        alterna): convierte con _convert() a la fecha de la FACTURA.

        No debe usar so_line.foreign_price: ese campo esta calculado con la
        fecha de la ORDEN (order.foreign_rate_date), que puede no coincidir
        con invoice_date -- ver test_28 para el caso donde de verdad
        divergen.
        """
        order, invoice = self._so_and_invoice(price_unit=300.0, pricelist=self.pl_ves)
        self.assertEqual(order.currency_id, self.ves)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.usd
        draft._onchange_currency_sync_from_so()

        # 300 VES / 50 = 6 USD
        expected = 300.0 / 50.0
        self.assertAlmostEqual(draft.invoice_line_ids.price_unit, expected, places=2)

    def test_24_order_in_third_currency_converts_with_the_general_branch(self):
        """Orden en EUR (ni la moneda de compania ni la alterna), factura
        pasada a VES: convierte con _convert() a la fecha de la factura.
        """
        order, invoice = self._so_and_invoice(price_unit=300.0, pricelist=self.pl_eur)
        self.assertEqual(order.currency_id, self.eur)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected = self.eur._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        self.assertAlmostEqual(draft.invoice_line_ids.price_unit, expected, places=2)

    def test_25_order_in_third_currency_to_foreign_currency_converts_at_invoice_date(self):
        """Orden en EUR, factura pasada a USD (la alterna de la compania,
        pero NO la moneda de la orden): tambien convierte con _convert() a la
        fecha de la factura -- la rama depende de la moneda DESTINO, no de la
        de origen, y en ningun caso usa foreign_price.
        """
        order, invoice = self._so_and_invoice(price_unit=300.0, pricelist=self.pl_eur)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.usd
        draft._onchange_currency_sync_from_so()

        expected = self.eur._convert(
            300.0, self.usd, self.company, self.today, round=False
        )
        self.assertAlmostEqual(draft.invoice_line_ids.price_unit, expected, places=2)

    def test_28_uses_invoice_date_not_the_order_rate_date(self):
        """La conversion hacia la moneda alterna debe usar la fecha de la
        FACTURA, no la fecha de la tasa de la orden -- son cosas distintas
        cuando convert_currency_from_sale_order esta activo pero
        use_invoice_rate_from_sale_order no (son flags independientes: la
        factura no hereda la fecha de la orden y puede tener la suya propia).

        REVERSION: si se vuelve a usar so_line.foreign_price aqui, este test
        falla porque foreign_price esta calculado con la fecha de la ORDEN
        (hoy, tasa 50), no con la fecha de la factura (hace 30 dias, tasa 25).
        """
        past_date = self.today - timedelta(days=30)
        self._set_rate(self.usd, past_date, 25.0)

        order, invoice = self._so_and_invoice(price_unit=300.0, pricelist=self.pl_ves)
        self.assertEqual(order.foreign_rate_date, self.today)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.usd
        draft.invoice_date = past_date
        draft._onchange_currency_sync_from_so()

        # 300 VES a la tasa de HACE 30 DIAS (25) = 12 USD, no 6 (tasa de hoy)
        self.assertAlmostEqual(
            draft.invoice_line_ids.price_unit, 12.0, places=2,
            msg=f"Debio usar la tasa de invoice_date (25 -> 12 USD), no la "
                f"de la orden (50 -> 6 USD): "
                f"{draft.invoice_line_ids.price_unit}"
        )

    def test_26_duplicate_lines_in_third_currency_order_convert_independently(self):
        """El caso de duplicados (test_17) repetido con una orden en una
        tercera moneda: ambas lineas deben seguir convirtiendo de forma
        independiente y al mismo valor esperado."""
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_eur.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
            ],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertEqual(len(invoice.invoice_line_ids), 2)

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected = self.eur._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        for line in draft.invoice_line_ids:
            self.assertAlmostEqual(line.price_unit, expected, places=2)

    def test_27_orphan_and_archived_lines_skipped_regardless_of_currency(self):
        """El caso de linea huerfana (test_20) y producto archivado (test_21)
        repetidos con una orden en una tercera moneda: deben seguir
        saltandose, y la linea normal debe seguir convirtiendo bien."""
        archived = self.env["product.product"].create({
            "name": "Producto a archivar (EUR)", "list_price": 50.0,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_eur.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
            "order_line": [
                (0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                        "price_unit": 300.0}),
                (0, 0, {"product_id": archived.id, "product_uom_qty": 1,
                        "price_unit": 50.0}),
            ],
        })
        order.action_confirm()
        invoice = order._create_invoices()
        archived.active = False
        orphan_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == archived
        )
        original_archived_price = orphan_line.price_unit

        draft = invoice.new(origin=invoice)
        draft.invoice_line_ids.filtered(
            lambda l: l.product_id == archived
        ).sale_line_ids = [(5, 0, 0)]

        draft.currency_id = self.ves
        draft._onchange_currency_sync_from_so()

        expected = self.eur._convert(
            300.0, self.ves, self.company, self.today, round=False
        )
        normal_line = draft.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product
        )
        archived_line = draft.invoice_line_ids.filtered(
            lambda l: l.product_id == archived
        )
        self.assertAlmostEqual(normal_line.price_unit, expected, places=2)
        self.assertAlmostEqual(
            archived_line.price_unit, original_archived_price, places=2,
            msg="La linea huerfana con producto archivado no debe convertirse"
        )

    def test_29_combo_product_header_is_skipped_and_item_converts(self):
        """Productos tipo combo: la linea del combo padre no lleva product_id
        (llega a la factura como display_type='line_section',
        _prepare_invoice_line en el core) y se salta sin error; el item
        elegido dentro del combo es una linea de producto normal, con su
        propia linea de pedido de origen, y se convierte igual que cualquiera.

        Construccion identica a la que usa el propio core de Odoo en
        sale/tests/test_sale_combo_multicurrency.py: parent_line (producto
        tipo combo) + child_line (combo_item_id + linked_line_id), ambas
        creadas directamente, sin wizard.
        """
        combo = self.env["product.combo"].create({
            "name": "Combo TA80647",
            "combo_item_ids": [(0, 0, {"product_id": self.product.id})],
        })
        combo_product = self.env["product.product"].create({
            "name": "Combo product TA80647",
            "type": "combo",
            "combo_ids": [(4, combo.id)],
            # list_price no puede ser 0 en este proyecto (constraint propia),
            # pero es irrelevante para el precio real de la linea: el core
            # ignora list_price del producto combo y arma la linea de
            # encabezado sin price_unit (display_type='line_section').
            "list_price": 1.0,
        })
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": self.pl_usd.id,
            "company_id": self.company.id,
            "date_order": fields.Datetime.now(),
        })
        parent_line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": combo_product.id,
            "product_uom_qty": 1,
        })
        combo_item = combo.combo_item_ids[0]
        child_line = self.env["sale.order.line"].create({
            "order_id": order.id,
            "product_id": self.product.id,
            "combo_item_id": combo_item.id,
            "linked_line_id": parent_line.id,
            "product_uom_qty": 1,
        })
        order.action_confirm()
        invoice = order._create_invoices()

        header_line = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == "line_section"
        )
        item_line = invoice.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product
        )
        self.assertTrue(header_line, "Debe existir la linea de encabezado del combo")
        self.assertTrue(item_line, "Debe existir la linea del item del combo")
        self.assertFalse(
            header_line.product_id,
            "La linea de encabezado del combo no debe tener producto"
        )
        original_item_price = item_line.price_unit

        draft = invoice.new(origin=invoice)
        draft.currency_id = self.ves
        # No debe reventar con la linea de encabezado sin producto
        draft._onchange_currency_sync_from_so()

        draft_header = draft.invoice_line_ids.filtered(
            lambda l: l.display_type == "line_section"
        )
        draft_item = draft.invoice_line_ids.filtered(
            lambda l: l.product_id == self.product
        )
        self.assertAlmostEqual(
            draft_header.price_unit, 0.0, places=2,
            msg="La linea de encabezado del combo no debe convertirse"
        )
        expected = self.usd._convert(
            original_item_price, self.ves, self.company, self.today, round=False
        )
        self.assertAlmostEqual(
            draft_item.price_unit, expected, places=2,
            msg="El item del combo debe convertirse igual que cualquier "
                "linea de producto normal"
        )
