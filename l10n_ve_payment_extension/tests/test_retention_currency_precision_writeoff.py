import random

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from .test_withholding_common_VEF import RetentionTestCommon


@tagged("post_install", "-at_install", "retention_currency_precision_writeoff")
class TestRetentionCurrencyPrecisionWriteoff(RetentionTestCommon):
    """Una factura en moneda extranjera lleva su adeudado en ESA moneda y con
    su propia precision; la retencion se calcula sobre el impuesto del
    asiento, en moneda de compania. A tasas de cientos, un centimo de la
    moneda de la factura vale varias unidades de la de compania, y la
    retencion correcta puede caer dentro de ese hueco sin ser un exceso.

    `account.move._retention_excess_within_currency_precision` decide eso
    reconvirtiendo el excedente a la moneda de la factura con la tasa DEL
    DOCUMENTO (`invoice_currency_rate`): si desaparece (redondea a cero en
    esa moneda), es redondeo, no exceso. `_prepare_retention_payment_vals`
    declara ese sobrante como `write_off_line_vals` en el momento de crear
    el pago, para que la conciliacion cierre la factura sin sobrante.
    """

    RATE = 772.54  # bolivares por 1 dolar

    def setUp(self):
        super().setUp()

        if "subsidiary" in self.company._fields:
            self.company.subsidiary = False

        # El propio `RetentionTestCommon.setUp()` ya siembra una tasa de
        # USD para hoy (INSERT ciego via Command.create); hay que borrarla
        # DESPUES de que corra -no antes, `res_currency_rate_unique_name_
        # per_day` la vuelve a insertar igual- para poder imponer la tasa
        # fija y conocida con la que este test calcula el "grano" a mano.
        hoy = fields.Date.today()
        self.env["res.currency.rate"].search([
            ("currency_id", "=", self.env.ref("base.USD").id),
            ("name", "=", hoy),
        ]).unlink()
        self.currency_usd.write({
            "rate_ids": [Command.create({
                "name": hoy,
                "rate": 1 / self.RATE,
                "company_rate": 1 / self.RATE,
                "inverse_company_rate": self.RATE,
            })],
        })

        # El `sale_journal` del fixture comun esta anclado a VEF; aqui hace
        # falta una factura en divisa, asi que se usa un diario sin moneda
        # fija, que sigue a la de la compania.
        self.journal_multi = self.Journal.create({
            "name": "Diario Venta Multimoneda Precision",
            "type": "sale",
            "code": "SVMP",
            "company_id": self.company.id,
        })
        # Mismo problema del lado de compras: `self.purchase_journal` del
        # fixture comun esta anclado a VEF.
        self.journal_multi_purchase = self.Journal.create({
            "name": "Diario Compra Multimoneda Precision",
            "type": "purchase",
            "code": "PCMP",
            "company_id": self.company.id,
        })

        # Actividad economica minima para las retenciones municipales.
        country = self.env["res.country"].search(
            [("code", "=", "TC-PREC")], limit=1
        ) or self.env["res.country"].create({"name": "Pais Precision", "code": "TC-PREC"})
        state = self.env["res.country.state"].search(
            [("code", "=", "TS-PREC")], limit=1
        ) or self.env["res.country.state"].create(
            {"name": "Estado Precision", "code": "TS-PREC", "country_id": country.id}
        )
        municipality = self.env["res.country.municipality"].search(
            [("code", "=", "MUN-PREC")], limit=1
        ) or self.env["res.country.municipality"].create({
            "name": "Municipio Precision", "code": "MUN-PREC",
            "country_id": country.id, "state_id": [(6, 0, [state.id])],
        })
        branch = self.env["economic.branch"].search(
            [("name", "=", "Rama Precision")], limit=1
        ) or self.env["economic.branch"].create({"name": "Rama Precision", "status": "active"})
        self.economic_activity = self.env["economic.activity"].search(
            [("name", "=", "Actividad Precision")], limit=1
        ) or self.env["economic.activity"].create({
            "name": "Actividad Precision", "aliquot": 5.0,
            "municipality_id": municipality.id, "branch_id": branch.id,
            "description": "Test", "minimum_monthly": 0, "minimum_annual": 0,
        })

        # El fixture comun solo configura los diarios de IVA/ISLR; faltan
        # los de Municipal para poder emitir esas retenciones.
        self.company.write({
            "municipal_supplier_retention_journal_id": self.bank_journal_sup_ret.id,
            "municipal_customer_retention_journal_id": self.bank_journal_sub.id,
        })

        # El writeoff necesita a donde ir: diario y cuentas de diferencial
        # cambiario, garantizados aqui para que el test hable del
        # comportamiento y no de la configuracion de la compania.
        if not self.company.currency_exchange_journal_id:
            self.company.currency_exchange_journal_id = self.Journal.create({
                "name": "Diferencial Cambiario",
                "type": "general",
                "code": "EXCHT",
                "company_id": self.company.id,
            })
        if not self.company.income_currency_exchange_account_id:
            self.company.income_currency_exchange_account_id = self.get_or_create_account(
                "7501", "income_other", "Ganancia por diferencial cambiario",
            )
        if not self.company.expense_currency_exchange_account_id:
            self.company.expense_currency_exchange_account_id = self.get_or_create_account(
                "6501", "expense", "Perdida por diferencial cambiario",
            )

    def _invoice_in_usd(self, amount):
        invoice = self._create_invoice_reten_iva(
            amount, self.partner_pnr_75, out_invoice="out_invoice",
            journal=self.journal_multi.id,
        )
        invoice.write({"currency_id": self.currency_usd.id})
        invoice.action_post()
        return invoice

    def _bill_in_usd(self, amount):
        bill = self._create_invoice_reten_iva(
            amount, self.partner_pnr_75, out_invoice="in_invoice",
            journal=self.journal_multi_purchase.id,
        )
        bill.write({"currency_id": self.currency_usd.id})
        bill.action_post()
        return bill

    def _document_in_usd_islr(self, amount, move_type, journal):
        """Como `_invoice_in_usd`/`_bill_in_usd`, pero con un producto que
        SI trae `payment_concept` (`self.product_islr_one`, del fixture
        comun) -`_check_islr_concept_amounts` exige que el concepto
        declarado en la linea de retencion coincida con un producto
        realmente facturado con ese concepto."""
        with Form(self.env["account.move"].with_context(
            default_move_type=move_type, default_journal_id=journal.id,
        )) as doc_form:
            doc_form.partner_id = self.partner_pnr_75
            doc_form.invoice_date = fields.Date.today()
            doc_form.currency_id = self.currency_vef
            if move_type == "in_invoice":
                doc_form.correlative = str(random.randint(10000000000000, 99999999999999))
        doc = doc_form.save()
        with Form(doc) as doc_form_edit:
            with doc_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.product_islr_one
                line.quantity = 1
                line.price_unit = amount
        doc = doc_form_edit.save()
        doc.write({"currency_id": self.currency_usd.id})
        doc.action_post()
        return doc

    def _grain(self, invoice):
        """Cuanto vale, en VEF, un centimo de la moneda de la factura -la
        misma cantidad que calcula `retention_excess_within_currency_
        precision`, pero derivada aqui de forma independiente (division,
        no la formula de produccion) para no probar el codigo contra si
        mismo."""
        return invoice.currency_id.rounding / invoice.invoice_currency_rate

    def _retention_for(self, invoice, amount_company_currency, number):
        rate = invoice.invoice_currency_rate or 1.0
        return self.env["account.retention"].create({
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
                "foreign_retention_amount": amount_company_currency * rate,
            })],
        })

    def _post_error_message(self, retention):
        result = retention.action_post()
        if isinstance(result, dict):
            return (result.get("params") or {}).get("message") or ""
        return None

    def test_tolerable_excess_is_accepted_and_settles_invoice_with_writeoff(self):
        invoice = self._invoice_in_usd(1000.0)
        due = abs(invoice.amount_residual_signed)
        grain = self._grain(invoice)
        excess = self.currency_vef.round(grain / 2)
        retained = self.currency_vef.round(due + excess)

        retention = self._retention_for(invoice, retained, "20260900000301")
        message = self._post_error_message(retention)

        self.assertIsNone(
            message,
            "Un excedente menor que un centimo de la moneda de la factura "
            "convertido no debe rechazar la retencion: %s" % message,
        )
        self.assertEqual(retention.state, "emitted")

        # Saldo EXACTO -ni queda residual (factura abierta), ni queda
        # negativo (saldo a favor, sobre-pago)- en ninguna de las dos
        # monedas. `assertEqual` contra 0.0 tras redondear a la precision
        # de cada moneda, no una comparacion de tolerancia laxa.
        self.assertEqual(
            self.currency_vef.round(invoice.amount_residual_signed), 0.0,
            "La factura no puede quedar ni abierta ni con saldo a favor en VEF.",
        )
        self.assertEqual(
            invoice.currency_id.round(invoice.amount_residual), 0.0,
            "La factura no puede quedar ni abierta ni con saldo a favor en "
            "su propia moneda.",
        )
        self.assertEqual(invoice.payment_state, "paid")

        # El sobrante debe haberse declarado como writeoff DESDE la
        # creacion del pago -una sola linea, en la cuenta correcta, por el
        # monto exacto- no via un asiento aparte creado despues.
        payment = retention.payment_ids
        self.assertEqual(len(payment), 1, "Debe haberse creado un solo pago de retencion.")

        income_account = self.company.income_currency_exchange_account_id
        expense_account = self.company.expense_currency_exchange_account_id
        writeoff_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id in (income_account | expense_account)
        )
        self.assertEqual(
            len(writeoff_lines), 1,
            "Debe existir exactamente una linea de writeoff por el sobrante.",
        )
        writeoff_line = writeoff_lines[0]

        # Un sobra siempre va a GANANCIA -este metodo nunca detecta una
        # falta, solo un exceso- nunca a la cuenta de perdida.
        self.assertEqual(
            writeoff_line.account_id, income_account,
            "Un sobrante debe ir a la cuenta de ganancia por diferencial "
            "cambiario, no a la de perdida.",
        )
        # Credito (negativo) al reconocer la ganancia: en un pago inbound
        # `contrapartida = -liquidez - writeoff`, y para que la
        # contrapartida cierre en -adeudado (no en -(adeudado+sobrante))
        # el writeoff tiene que ser -sobrante, no +sobrante.
        self.assertAlmostEqual(
            writeoff_line.balance, -excess, places=2,
            msg="El writeoff debe acreditar exactamente el sobrante "
            "declarado a la cuenta de ganancia.",
        )
        self.assertAlmostEqual(
            writeoff_line.amount_currency, -excess, places=2,
            msg="amount_currency debe llevar el mismo monto y signo que balance "
            "-la linea esta en moneda de compania.",
        )

        # La cuenta por cobrar debe reconciliar EXACTAMENTE lo adeudado
        # original -ni un centimo mas ni menos: el excedente lo absorbio el
        # writeoff, no la cuenta por cobrar.
        receivable_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        self.assertTrue(receivable_lines, "Debe existir la linea de cuenta por cobrar del pago.")
        self.assertAlmostEqual(
            abs(sum(receivable_lines.mapped("balance"))), due, places=2,
            msg="La cuenta por cobrar debe cerrar exactamente por el adeudado "
            "original, sin el sobrante de precision.",
        )

        # El asiento del pago tiene que cuadrar como partida doble real.
        self.assertAlmostEqual(
            sum(payment.move_id.line_ids.mapped("balance")), 0.0, places=2,
            msg="El asiento del pago debe estar balanceado.",
        )

    def test_missing_exchange_account_blocks_instead_of_leaving_surplus_open(self):
        """Sin cuenta de ganancia por diferencial cambiario, el proceso se
        detiene -no se emite una retencion con un residual silencioso."""
        self.company.income_currency_exchange_account_id = False

        invoice = self._invoice_in_usd(1000.0)
        due = abs(invoice.amount_residual_signed)
        grain = self._grain(invoice)

        retention = self._retention_for(
            invoice, self.currency_vef.round(due + grain / 2), "20260900000305",
        )
        with self.assertRaises(UserError):
            retention.action_post()

        self.assertNotEqual(retention.state, "emitted")
        self.assertFalse(
            retention.payment_ids,
            "No puede haberse creado un pago si no se pudo declarar el writeoff.",
        )

    def test_real_excess_is_still_rejected(self):
        invoice = self._invoice_in_usd(1000.0)
        due = abs(invoice.amount_residual_signed)
        grain = self._grain(invoice)

        retention = self._retention_for(
            invoice, self.currency_vef.round(due + grain * 5), "20260900000302",
        )
        message = self._post_error_message(retention)

        self.assertIsNotNone(
            message,
            "Un exceso de varios centimos de la moneda de la factura sigue "
            "siendo un exceso real y debe rechazarse.",
        )
        self.assertIn("cannot be greater", message)
        self.assertNotEqual(retention.state, "emitted")
        self.assertFalse(
            retention.payment_ids,
            "Un rechazo real no puede haber generado ningun pago.",
        )
        self.assertEqual(
            self.currency_vef.round(abs(invoice.amount_residual_signed)), due,
            "La factura debe quedar exactamente como estaba: nada se concilio.",
        )

    def test_company_currency_invoice_keeps_strict_comparison(self):
        """Sin cambio de moneda no hay grano: el margen sigue siendo cero."""
        invoice = self._create_invoice_reten_iva(
            1000.0, self.partner_pnr_75, out_invoice="out_invoice",
            journal=self.journal_multi.id,
        )
        invoice.action_post()
        due = abs(invoice.amount_residual_signed)

        retention = self.env["account.retention"].create({
            "type_retention": "iva",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": invoice.invoice_date,
            "date_accounting": invoice.invoice_date,
            "number": "20260900000303",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "name": "Linea de retencion IVA",
                "invoice_total": invoice.amount_total,
                "invoice_amount": invoice.amount_untaxed,
                "retention_amount": due + 0.02,
                "foreign_currency_rate": 1.0,
                "foreign_invoice_amount": invoice.amount_untaxed,
                "foreign_retention_amount": due + 0.02,
            })],
        })
        message = self._post_error_message(retention)

        self.assertIsNotNone(
            message,
            "Con una sola moneda dos centimos de mas son un exceso real, "
            "sin tolerancia posible.",
        )
        self.assertNotEqual(retention.state, "emitted")

    def test_check_retention_amount_line_edit_uses_same_tolerance(self):
        """`check_retention_amount` (la barrera que corre al editar una
        linea ya guardada) no puede divergir de la de `action_post`."""
        invoice = self._invoice_in_usd(1000.0)
        due = abs(invoice.amount_residual_signed)
        grain = self._grain(invoice)

        retention = self._retention_for(
            invoice, self.currency_vef.round(due), "20260900000304",
        )
        line = retention.retention_line_ids[:1]

        # Dentro del grano: no debe reventar.
        line.write({"retention_amount": self.currency_vef.round(due + grain / 2)})

        # Mas alla del grano: debe rechazar, igual que action_post.
        with self.assertRaises(ValidationError):
            line.write({"retention_amount": self.currency_vef.round(due + grain * 5)})

    # ------------------------------------------------------------------
    # El mismo mecanismo (accion_post, writeoff en la creacion del pago)
    # es compartido por los tres tipos de retencion y las dos direcciones
    # -no hay ningun `if type_retention == "iva"` que lo restrinja- pero
    # eso solo se confirma probandolo, no infiriendolo del codigo.
    # ------------------------------------------------------------------

    def _force_line_retention_amount(self, line, amount):
        """Fuerza el monto EXACTO de la linea para ejercitar el borde de
        tolerancia, en un `write()` separado del `create()`.

        Para ISLR, `retention_amount` es un campo compute
        (`_compute_retention_amount`) que se dispara con la formula de
        concepto/tarifa del partner - pasar un valor en `create()` no
        alcanza, la formula lo pisa. Pero ese compute escucha
        `invoice_amount`/`related_percentage_*`/`foreign_currency_rate`,
        nunca `retention_amount` en si mismo, asi que un `write()`
        posterior que solo toque `retention_amount` no vuelve a disparar
        el compute y el valor explicito se queda. Municipal no tiene este
        problema -su calculo vive en un `@api.onchange`, que no corre por
        ORM directo- pero se usa el mismo mecanismo por uniformidad.
        """
        line.write({
            "retention_amount": amount,
            "foreign_retention_amount": amount,
        })

    def test_islr_client_retention_tolerable_excess_settles_invoice(self):
        invoice = self._document_in_usd_islr(1000.0, "out_invoice", self.journal_multi)
        due = abs(invoice.amount_residual_signed)
        grain = self._grain(invoice)
        excess = self.currency_vef.round(grain / 2)
        retained = self.currency_vef.round(due + excess)

        retention = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": invoice.invoice_date,
            "date_accounting": invoice.invoice_date,
            "number": "20260900000401",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "payment_concept_id": self.concept_one.id,
                "name": "Retencion ISLR Cliente",
                "invoice_type": "out_invoice",
                "invoice_amount": invoice.amount_untaxed,
                "foreign_invoice_amount": invoice.amount_untaxed,
            })],
        })
        self._force_line_retention_amount(retention.retention_line_ids[:1], retained)

        message = self._post_error_message(retention)
        self.assertIsNone(
            message,
            "ISLR de cliente debe tolerar el mismo grano que IVA: %s" % message,
        )
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(self.currency_vef.round(invoice.amount_residual_signed), 0.0)
        self.assertEqual(invoice.currency_id.round(invoice.amount_residual), 0.0)
        self.assertEqual(invoice.payment_state, "paid")

        payment = retention.payment_ids
        receivable_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        self.assertAlmostEqual(
            abs(sum(receivable_lines.mapped("balance"))), due, places=2,
            msg="La cuenta por cobrar debe cerrar exactamente por el adeudado.",
        )
        self.assertAlmostEqual(
            sum(payment.move_id.line_ids.mapped("balance")), 0.0, places=2,
            msg="El asiento del pago debe estar balanceado.",
        )

    def test_islr_supplier_retention_tolerable_excess_settles_bill(self):
        bill = self._document_in_usd_islr(1000.0, "in_invoice", self.journal_multi_purchase)
        due = abs(bill.amount_residual_signed)
        grain = self._grain(bill)
        excess = self.currency_vef.round(grain / 2)
        retained = self.currency_vef.round(due + excess)

        retention = self.env["account.retention"].create({
            "type_retention": "islr",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": bill.invoice_date,
            "date_accounting": bill.invoice_date,
            "retention_line_ids": [Command.create({
                "move_id": bill.id,
                "payment_concept_id": self.concept_one.id,
                "name": "Retencion ISLR Proveedor",
                "invoice_type": "in_invoice",
                "invoice_amount": bill.amount_untaxed,
                "foreign_invoice_amount": bill.amount_untaxed,
            })],
        })
        self._force_line_retention_amount(retention.retention_line_ids[:1], retained)

        message = self._post_error_message(retention)
        self.assertIsNone(
            message,
            "ISLR de proveedor debe tolerar el mismo grano que del lado "
            "cliente: %s" % message,
        )
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(self.currency_vef.round(bill.amount_residual_signed), 0.0)
        self.assertEqual(bill.currency_id.round(bill.amount_residual), 0.0)
        self.assertEqual(bill.payment_state, "paid")

        payment = retention.payment_ids
        payable_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        )
        self.assertTrue(payable_lines, "Debe existir la linea de cuenta por pagar del pago.")
        self.assertAlmostEqual(
            abs(sum(payable_lines.mapped("balance"))), due, places=2,
            msg="La cuenta por pagar debe cerrar exactamente por el adeudado "
            "-la direccion 'outbound' no puede dejar el sobrante puesto ahi.",
        )

        # Del lado proveedor (outbound) el writeoff cae en PERDIDA, no en
        # ganancia: un debito a la cuenta de ganancia la reduciria, que es
        # lo opuesto de lo que hay que registrar.
        expense_account = self.company.expense_currency_exchange_account_id
        income_account = self.company.income_currency_exchange_account_id
        writeoff_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id in (income_account | expense_account)
        )
        self.assertEqual(len(writeoff_lines), 1)
        self.assertEqual(
            writeoff_lines.account_id, expense_account,
            "Del lado proveedor el sobrante debe ir a PERDIDA, no a ganancia.",
        )
        self.assertAlmostEqual(
            writeoff_lines.balance, excess, places=2,
            msg="Debito exacto del sobrante a la cuenta de perdida.",
        )

        self.assertAlmostEqual(
            sum(payment.move_id.line_ids.mapped("balance")), 0.0, places=2,
            msg="El asiento del pago debe estar balanceado tambien del lado "
            "proveedor.",
        )

    def test_municipal_client_retention_tolerable_excess_settles_invoice(self):
        invoice = self._invoice_in_usd(1000.0)
        due = abs(invoice.amount_residual_signed)
        grain = self._grain(invoice)
        excess = self.currency_vef.round(grain / 2)
        retained = self.currency_vef.round(due + excess)

        retention = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "out_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": invoice.invoice_date,
            "date_accounting": invoice.invoice_date,
            "number": "20260900000402",
            "retention_line_ids": [Command.create({
                "move_id": invoice.id,
                "economic_activity_id": self.economic_activity.id,
                "aliquot": self.economic_activity.aliquot,
                "name": "Retencion Municipal Cliente",
                "invoice_total": invoice.amount_total,
                "invoice_amount": invoice.amount_untaxed,
                "retention_amount": retained,
                "foreign_invoice_amount": invoice.amount_untaxed,
                "foreign_retention_amount": retained,
            })],
        })

        message = self._post_error_message(retention)
        self.assertIsNone(
            message,
            "Municipal de cliente debe tolerar el mismo grano que IVA/ISLR: "
            "%s" % message,
        )
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(self.currency_vef.round(invoice.amount_residual_signed), 0.0)
        self.assertEqual(invoice.payment_state, "paid")

        payment = retention.payment_ids
        receivable_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        self.assertAlmostEqual(
            abs(sum(receivable_lines.mapped("balance"))), due, places=2,
        )

    def test_municipal_supplier_retention_tolerable_excess_settles_bill(self):
        bill = self._bill_in_usd(1000.0)
        due = abs(bill.amount_residual_signed)
        grain = self._grain(bill)
        excess = self.currency_vef.round(grain / 2)
        retained = self.currency_vef.round(due + excess)

        retention = self.env["account.retention"].create({
            "type_retention": "municipal",
            "type": "in_invoice",
            "company_id": self.company.id,
            "partner_id": self.partner_pnr_75.id,
            "date": bill.invoice_date,
            "date_accounting": bill.invoice_date,
            "retention_line_ids": [Command.create({
                "move_id": bill.id,
                "economic_activity_id": self.economic_activity.id,
                "aliquot": self.economic_activity.aliquot,
                "name": "Retencion Municipal Proveedor",
                "invoice_total": bill.amount_total,
                "invoice_amount": bill.amount_untaxed,
                "retention_amount": retained,
                "foreign_invoice_amount": bill.amount_untaxed,
                "foreign_retention_amount": retained,
            })],
        })

        message = self._post_error_message(retention)
        self.assertIsNone(
            message,
            "Municipal de proveedor debe tolerar el mismo grano: %s" % message,
        )
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(self.currency_vef.round(bill.amount_residual_signed), 0.0)
        self.assertEqual(bill.payment_state, "paid")

        payment = retention.payment_ids
        payable_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type == "liability_payable"
        )
        self.assertTrue(payable_lines)
        self.assertAlmostEqual(
            abs(sum(payable_lines.mapped("balance"))), due, places=2,
            msg="La cuenta por pagar debe cerrar exactamente por el adeudado "
            "tambien para Municipal proveedor.",
        )

        expense_account = self.company.expense_currency_exchange_account_id
        income_account = self.company.income_currency_exchange_account_id
        writeoff_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id in (income_account | expense_account)
        )
        self.assertEqual(len(writeoff_lines), 1)
        self.assertEqual(
            writeoff_lines.account_id, expense_account,
            "Del lado proveedor el sobrante debe ir a PERDIDA, no a ganancia "
            "-tambien para Municipal.",
        )
        self.assertAlmostEqual(writeoff_lines.balance, excess, places=2)
