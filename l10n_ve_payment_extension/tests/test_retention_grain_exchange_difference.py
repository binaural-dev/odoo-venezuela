from odoo import Command, fields
from odoo.tests import tagged

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_grain_exchange_difference")
class TestRetentionGrainExchangeDifference(RetentionTestCommon):
    """El sobrante que deja la tolerancia va al diferencial cambiario.

    `action_post` acepta que una retencion supere el adeudado hasta en un
    grano de moneda, pero la conciliacion parcial toma el MINIMO de las dos
    valoraciones: ese sobrante no llega a la factura y se quedaba abierto en
    la cuenta por cobrar como un saldo a favor que nadie reclamaba.

    Aqui se comprueba que ahora se absorbe -y, tan importante como eso, que
    un pago parcial legitimo se sigue dejando en paz.
    """

    def setUp(self):
        # Las tres normalizaciones que necesita este fixture para correr
        # contra una base con datos; las mismas que en
        # test_retention_post_amount_tolerance. No se comparten todavia a
        # proposito: arreglar `RetentionTestCommon` afecta a la treintena de
        # ficheros de test del modulo y es trabajo de su propio ticket.
        hoy = fields.Date.today()
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.env.ref("base.USD").id),
            ("name", "in", [hoy, fields.Date.subtract(hoy, days=1)]),
        ]).unlink()
        super().setUp()
        if "subsidiary" in self.company._fields:
            self.company.subsidiary = False
        self.journal_multi = self.Journal.create({
            "name": "Diario Venta Multimoneda DC",
            "type": "sale",
            "code": "SVDC",
            "company_id": self.company.id,
        })
        # Sin diario de diferencial cambiario configurado el core levanta un
        # UserError explicito; se garantiza aqui para que el test hable del
        # comportamiento y no de la configuracion de la compania.
        if not self.company.currency_exchange_journal_id:
            self.company.currency_exchange_journal_id = self.Journal.create({
                "name": "Diferencial Cambiario",
                "type": "general",
                "code": "EXCHT",
                "company_id": self.company.id,
            })

    def _exchange_moves(self):
        return self.env["account.move"].search([
            ("journal_id", "=", self.company.currency_exchange_journal_id.id),
        ])

    def _invoice(self, amount, rate=None):
        invoice = self._create_invoice_reten_iva(
            amount, self.partner_pnr_75, out_invoice="out_invoice",
            journal=self.journal_multi.id,
        )
        if rate:
            invoice.write({"currency_id": self.currency_usd.id})
        invoice.action_post()
        if rate:
            invoice.write({"foreign_rate": rate, "foreign_inverse_rate": 1 / rate})
        return invoice

    def _post_retention(self, invoice, amount_company_currency, number):
        rate = invoice.foreign_rate or 1.0
        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": invoice.invoice_date,
            "date_accounting": invoice.invoice_date,
            "number": number,
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "Linea de retencion IVA",
                "invoice_total": invoice.amount_total,
                "invoice_amount": invoice.amount_untaxed,
                "retention_amount": amount_company_currency,
                "foreign_currency_rate": rate,
                "foreign_invoice_amount": invoice.amount_untaxed,
                "foreign_retention_amount": amount_company_currency / rate,
            })],
        })
        result = retention.action_post()
        # `action_post` devuelve un dict de notificacion cuando rechaza, en
        # vez de levantar. Sin esta comprobacion los tests negativos pasaban
        # "no se creo ningun asiento" simplemente porque la retencion nunca
        # llego a postearse.
        if isinstance(result, dict):
            self.fail(
                "action_post rechazo la retencion: %s"
                % (result.get("params") or {}).get("message")
            )
        self.assertEqual(retention.state, "emitted")
        return retention

    def _receivable_lines(self, retention):
        return retention.payment_ids.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )

    def test_grain_leftover_goes_to_exchange_difference(self):
        rate = 772.54
        invoice = self._invoice(1000.0, rate)
        due = abs(invoice.amount_residual_signed)
        grain = self.currency_usd.rounding * rate
        before = self._exchange_moves()

        retention = self._post_retention(
            invoice, self.currency_vef.round(due + grain / 2), "20260900000101")

        nuevos = self._exchange_moves() - before
        self.assertEqual(
            len(nuevos), 1,
            "El sobrante de grano debe generar UN asiento de diferencial cambiario.",
        )
        self.assertEqual(nuevos.state, "posted")
        self.assertTrue(
            all(self.currency_vef.is_zero(l.amount_residual)
                for l in self._receivable_lines(retention)),
            "Tras absorberlo no puede quedar saldo abierto en la cuenta por cobrar.",
        )

    def test_partial_retention_creates_no_exchange_difference(self):
        """Una retencion por debajo del adeudado es un pago parcial, no un grano."""
        rate = 772.54
        invoice = self._invoice(1000.0, rate)
        due = abs(invoice.amount_residual_signed)
        before = self._exchange_moves()

        self._post_retention(invoice, self.currency_vef.round(due / 2), "20260900000102")

        self.assertFalse(
            self._exchange_moves() - before,
            "Un pago parcial legitimo deja saldo a proposito: no se absorbe.",
        )

    def test_company_currency_invoice_creates_no_exchange_difference(self):
        """Sin cambio de moneda no hay grano que absorber."""
        invoice = self._invoice(1000.0)
        due = abs(invoice.amount_residual_signed)
        before = self._exchange_moves()

        self._post_retention(invoice, self.currency_vef.round(due), "20260900000103")

        self.assertFalse(
            self._exchange_moves() - before,
            "Con una sola moneda no hay dos precisiones que reconciliar.",
        )

    def test_absorbed_amount_never_exceeds_one_grain(self):
        """La cota es absoluta: como mucho un centimo de la divisa.

        Se dejo fuera a proposito una objecion de revision que pedia no
        absorber cuando el remanente es grande EN PROPORCION al saldo que
        queda -por ejemplo 6 Bs sobre una factura a la que solo le quedaban
        4-. El grano no es un porcentaje: es la resolucion del instrumento,
        lo que un centimo de la moneda de la factura vale en bolivares. Un
        remanente por debajo de esa resolucion sigue siendo indistinguible
        de cero por mucho que el saldo restante sea pequeno, y acotarlo
        ademas en proporcion dejaria abiertos justo los casos que este
        cambio existe para cerrar. Lo que si se acota, y se comprueba aqui,
        es el valor absoluto.
        """
        rate = 772.54
        invoice = self._invoice(1000.0, rate)
        due = abs(invoice.amount_residual_signed)
        grain = invoice.retention_currency_grain()
        before = self._exchange_moves()

        self._post_retention(
            invoice, self.currency_vef.round(due + grain / 2), "20260900000201")

        nuevos = self._exchange_moves() - before
        self.assertEqual(len(nuevos), 1)
        absorbido = sum(abs(l.balance) for l in nuevos.line_ids) / 2
        self.assertLessEqual(
            absorbido, grain,
            "Lo absorbido no puede superar un grano de la moneda de la factura.",
        )

    def test_cancelling_the_retention_reverses_the_exchange_entry(self):
        """El asiento absorbido no puede sobrevivir a la cancelacion.

        Se crea fuera del plan de conciliacion del core, asi que su parcial
        nace sin `exchange_move_id` y el `unlink()` del core no lo
        revertiria: quedaria posteado y sin conciliar en la cuenta por
        cobrar, sin documento que lo justifique.
        """
        rate = 772.54
        invoice = self._invoice(1000.0, rate)
        due = abs(invoice.amount_residual_signed)
        grain = invoice.retention_currency_grain()
        before = self._exchange_moves()

        retention = self._post_retention(
            invoice, self.currency_vef.round(due + grain / 2), "20260900000203")
        creados = self._exchange_moves() - before
        self.assertEqual(len(creados), 1)
        self.assertEqual(retention.grain_exchange_move_ids, creados)

        retention.action_cancel()

        self.assertFalse(
            retention.grain_exchange_move_ids,
            "La retencion cancelada no puede seguir apuntando al asiento.",
        )
        # Solo las lineas de cuentas conciliables cuentan: la de resultado
        # (ganancia/perdida en cambio) no es conciliable por definicion.
        abiertas = creados.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and not l.reconciled
            and not l.company_currency_id.is_zero(l.amount_residual)
        )
        self.assertFalse(
            abiertas,
            "Tras cancelar no puede quedar saldo abierto en la cuenta por "
            "cobrar del asiento de grano.",
        )
