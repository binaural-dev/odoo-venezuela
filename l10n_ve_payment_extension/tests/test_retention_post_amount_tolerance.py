from odoo import Command, fields
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon

# Texto (en ingles, el idioma fuente) del error que puertea action_post. Se
# busca por subcadena porque el mensaje interpola importes.
ERROR_MONTO = "cannot be greater than the invoice total signed amount"


@tagged("post_install", "-at_install", "retention_post_amount_tolerance")
class TestRetentionPostAmountTolerance(RetentionTestCommon):
    """La validacion de importe de `action_post` tolera el grano de moneda.

    Una factura en moneda extranjera lleva su importe adeudado en ESA moneda
    y con la precision de esa moneda; la retencion se calcula sobre el IVA
    del asiento, que esta en moneda de compania. A una tasa de cientos, un
    centimo de la moneda de la factura vale varias unidades de la de
    compania: la retencion correcta puede caer dentro de ese hueco sin ser
    un exceso.

    Estos tests atacan el borde directamente -adeudado + medio grano contra
    adeudado + dos granos- en vez de reproducir el 75% de un IVA concreto,
    para que el caso no dependa de que la alicuota de la ficticia coincida
    con la de ningun cliente.
    """

    def setUp(self):
        # RetentionTestCommon siembra tasas de USD para hoy y ayer con
        # `Command.create`, que es un INSERT ciego. En una base que ya tiene
        # tasas cargadas -cualquier instancia real- eso choca contra la
        # restriccion `res_currency_rate_unique_name_per_day` y el fixture
        # revienta antes de llegar al test. Se limpian esos dos dias primero
        # para que la clase corra tanto en CI (base limpia, no borra nada)
        # como contra una base con datos.
        #
        # Es un parche local a proposito: arreglar el fixture compartido
        # afecta a la treintena de ficheros de test del modulo y no pertenece
        # a este cambio.
        hoy = fields.Date.today()
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.env.ref("base.USD").id),
            ("name", "in", [hoy, fields.Date.subtract(hoy, days=1)]),
        ]).unlink()
        super().setUp()
        # `binaural_subsidiary` -otro repositorio- vuelve obligatoria la
        # cuenta analitica de la factura cuando la compania esta marcada como
        # sucursal, y entonces el Form del fixture no se puede guardar. Se
        # desmarca para este test. En el CI de la localizacion ese modulo no
        # esta instalado, el campo no existe y esto no hace nada.
        if "subsidiary" in self.company._fields:
            self.company.subsidiary = False
        # El `sale_journal` del fixture esta anclado a VEF, y
        # `_check_constrains_account_id_journal_id` rechaza una linea en otra
        # moneda. Aqui hace falta justamente una factura en divisa, asi que
        # se usa un diario sin moneda fija, que sigue a la de la compania.
        self.journal_multi = self.Journal.create({
            "name": "Diario Venta Multimoneda",
            "type": "sale",
            "code": "SVMM",
            "company_id": self.company.id,
        })

    def _invoice_in_foreign_currency(self, amount, rate):
        invoice = self._create_invoice_reten_iva(
            amount, self.partner_pnr_75, out_invoice="out_invoice",
            journal=self.journal_multi.id,
        )
        invoice.write({"currency_id": self.currency_usd.id})
        invoice.action_post()
        # Tasa congelada de la factura, igual que en produccion: es la que
        # convierte el centimo de divisa a moneda de compania.
        invoice.write({"foreign_rate": rate, "foreign_inverse_rate": 1 / rate})
        return invoice

    def _retention_for(self, invoice, amount_company_currency):
        today = fields.Date.today()
        return self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": today,
            "date_accounting": today,
            "number": "20260900000001",
            "retention_line_ids": [
                Command.create({
                    "move_id": invoice.id,
                    "name": "Linea de retencion IVA",
                    "invoice_total": invoice.amount_total,
                    "invoice_amount": invoice.amount_untaxed,
                    "retention_amount": amount_company_currency,
                    "foreign_currency_rate": invoice.foreign_rate,
                    "foreign_invoice_amount": invoice.amount_untaxed,
                    "foreign_retention_amount": (
                        amount_company_currency / invoice.foreign_rate
                    ),
                })
            ],
        })

    def _post_error_message(self, retention):
        """Devuelve el mensaje con que `action_post` rechazo, o None.

        `action_post` no se limita a validar: si el importe pasa el filtro
        sigue adelante y genera los pagos, y eso puede fallar por motivos
        ajenos a este test (secuencias, conciliacion, configuracion de la
        compania). Por eso se mira SOLO si el rechazo es el del importe:
        cualquier otro desenlace significa que esta validacion dejo pasar el
        comprobante, que es justo lo que se quiere comprobar.
        """
        try:
            # lang forzado: `_()` traduce con el idioma del env y la base
            # puede estar en español. La asercion mira el texto fuente.
            result = retention.with_context(lang="en_US").action_post()
        except Exception as exc:  # noqa: BLE001 - ver docstring
            # Solo se traga la excepcion si ES la del importe. Cualquier
            # otra se relanza: antes se capturaban todas y se devolvia el
            # texto, asi que un fallo por secuencia, diario o conciliacion
            # hacia pasar en verde un test que afirma "se acepto".
            if ERROR_MONTO in str(exc):
                return str(exc)
            raise
        if isinstance(result, dict):
            return (result.get("params") or {}).get("message") or ""
        return None

    def test_amount_within_currency_grain_is_accepted(self):
        rate = 772.54
        invoice = self._invoice_in_foreign_currency(1000.0, rate)
        due = abs(invoice.amount_residual_signed)
        grain = self.currency_usd.rounding * rate

        retention = self._retention_for(invoice, due + grain / 2)

        message = self._post_error_message(retention) or ""
        self.assertNotIn(
            ERROR_MONTO, message,
            "Un exceso menor que el centimo de divisa convertido no es un "
            "exceso: es lo que las dos medidas no pueden expresar igual.",
        )

    def test_amount_beyond_currency_grain_is_still_rejected(self):
        rate = 772.54
        invoice = self._invoice_in_foreign_currency(1000.0, rate)
        due = abs(invoice.amount_residual_signed)
        grain = self.currency_usd.rounding * rate

        retention = self._retention_for(invoice, due + grain * 2)

        message = self._post_error_message(retention) or ""
        self.assertIn(
            ERROR_MONTO, message,
            "La tolerancia es el grano de la moneda, no un margen libre: por "
            "encima de el sigue siendo un exceso real.",
        )

    def test_company_currency_invoice_keeps_strict_comparison(self):
        """Sin cambio de moneda no hay grano, y el filtro es el de siempre."""
        invoice = self._create_invoice_reten_iva(
            1000.0, self.partner_pnr_75, out_invoice="out_invoice",
            journal=self.journal_multi.id,
        )
        invoice.action_post()
        due = abs(invoice.amount_residual_signed)

        retention = self._retention_for_vef(invoice, due + 0.02)

        message = self._post_error_message(retention) or ""
        self.assertIn(
            ERROR_MONTO, message,
            "Con una sola moneda el margen es cero: dos centimos de mas son "
            "dos centimos de mas.",
        )

    def _retention_for_vef(self, invoice, amount_company_currency):
        today = fields.Date.today()
        return self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": today,
            "date_accounting": today,
            "number": "20260900000002",
            "retention_line_ids": [
                Command.create({
                    "move_id": invoice.id,
                    "name": "Linea de retencion IVA",
                    "invoice_total": invoice.amount_total,
                    "invoice_amount": invoice.amount_untaxed,
                    "retention_amount": amount_company_currency,
                    "foreign_currency_rate": 1.0,
                    "foreign_invoice_amount": invoice.amount_untaxed,
                    "foreign_retention_amount": amount_company_currency,
                })
            ],
        })
