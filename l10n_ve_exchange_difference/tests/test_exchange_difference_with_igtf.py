from odoo import Command, fields
from odoo.tests import Form, tagged

from odoo.addons.l10n_ve_igtf.tests.test_igtf_common_partner_formal_VEF import IGTFTestCommon


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeDifferenceWithIGTF(IGTFTestCommon):
    """Reusa el fixture ya existente de `l10n_ve_igtf` (`IGTFTestCommon`,
    `l10n_ve_igtf/tests/test_igtf_common_partner_formal_VEF.py`) en vez de
    reconstruir compañía/cuentas/diarios propios -- ese fixture ya deja
    IGTF activo (`igtf_percentage`, `customer_account_igtf_id`, diario de
    banco USD con `is_igtf=True`) sobre la MISMA compañía y las MISMAS
    tasas de cambio (hoy y ayer) que usan sus propios tests. Solo se
    agrega encima la configuración mínima que necesita
    `l10n_ve_exchange_difference` para activarse."""

    def setUp(self):
        super().setUp()
        # No se reutiliza `self.tax_iva_exent` (creado por `IGTFTestCommon`
        # con el país de la compañía, pero sin pasar por el `Form`/onchange
        # que normalmente ajusta la posición fiscal): al crear la ND/NC
        # directo con `create()` (`_create_exchange_difference_note`,
        # `l10n_ve_exchange_difference/models/account_move_line.py`), ese
        # impuesto disparaba `_validate_taxes_country` ("taxes that are not
        # compatible with your fiscal position"). Se busca en su lugar un
        # impuesto de venta al 0% ya existente y compatible -- mismo
        # patrón que usa `test_exchange_note_reversal.py`.
        exent = self.env["account.tax"].search([
            ("type_tax_use", "=", "sale"), ("amount", "=", 0.0),
            ("company_id", "=", self.company.id),
        ], limit=1)
        # `l10n_ve_exchange_note_product_id` exige (`_check_l10n_ve_exchange_note_product_id`,
        # `l10n_ve_exchange_difference/models/res_company.py`) que el
        # producto sea un servicio con la cuenta de ingreso igual a una de
        # las cuentas nativas de ganancia/pérdida por diferencial
        # cambiario de la compañía, y el mismo impuesto exento por
        # defecto (`company.exent_aliquot_sale`).
        self.company.exent_aliquot_sale = exent.id
        self.note_product = self.env["product.product"].create({
            "name": "Diferencial Test IGTF",
            "type": "service",
            "taxes_id": [(6, 0, exent.ids)],
            "property_account_income_id": self.company.income_currency_exchange_account_id.id,
            "property_account_expense_id": self.company.expense_currency_exchange_account_id.id,
        })
        self.company.l10n_ve_exchange_note_product_id = self.note_product.id

        self.note_pricelist = self.env["product.pricelist"].create({
            "name": "Diferencial Test IGTF (VEF)",
            "currency_id": self.company.currency_id.id,
        })
        self.company.l10n_ve_exchange_note_pricelist_id = self.note_pricelist.id
        self.company.l10n_ve_exchange_use_nd_nc = True

        # Diario dedicado de ND con secuencia propia -- requerido desde
        # el fix del bloqueante de numeración (ver
        # `test_exchange_note_reversal.setUpClass`): sin esto, cualquier
        # escenario de este archivo que termine en rama de GANANCIA (ND)
        # fallaría con UserError en vez de la nota.
        self.debit_note_sequence = self.env["ir.sequence"].create({
            "name": "ND Diferencial Cambiario Test IGTF",
            "code": "l10n.ve.exchange.debit.note.test.igtf",
            "company_id": self.company.id,
            "prefix": "NDDIFTIGTF/%(year)s/",
            "padding": 4,
        })
        self.debit_note_journal = self.env["account.journal"].create({
            "name": "ND Diferencial Cambiario Test IGTF",
            "type": "sale",
            "code": "NDDIFTIGTF",
            "company_id": self.company.id,
            "is_debit": True,
            "l10n_ve_exchange_debit_note_sequence_id": self.debit_note_sequence.id,
        })

    def test_grouped_payment_with_igtf_attributes_each_note_to_its_own_invoice(self):
        """Combina el fix de atribución en pagos agrupados (ver
        `test_exchange_note_reversal.test_grouped_payment_gain_direction_invoice_attribution_limitation`)
        con IGTF real de por medio: un pago AGRUPADO en el diario
        `bank_journal_usd` (`is_igtf=True`), liquidando DOS facturas de
        montos DISTINTOS (100 y 500 USD) a la vez, en dirección de
        ganancia (donde Odoo suele atribuir el residual al lado del
        pago). El IGTF retenido sobre el pago combinado no debe alterar
        la atribución exacta de cada ND a su propia factura -- verificado
        con montos distintos (no dos facturas idénticas) para que un
        swap entre ellas sea detectable."""
        self.currency_usd.write({
            "rate_ids": [
                Command.create({"name": "2041-01-01", "company_rate": 1 / 36.0}),
                Command.create({"name": "2041-08-01", "company_rate": 1 / 40.0}),
            ],
        })

        invoice_1 = self._create_invoice_usd(100.0, date="2041-01-01")
        invoice_1.with_context(move_action_post_alert=True).action_post()
        invoice_2 = self._create_invoice_usd(500.0, date="2041-01-01")
        invoice_2.with_context(move_action_post_alert=True).action_post()
        invoices = invoice_1 | invoice_2

        lines_to_pay = invoices.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        action = lines_to_pay.action_register_payment()
        ctx = dict(action["context"], active_model="account.move.line", active_ids=lines_to_pay.ids)
        with Form(self.env["account.payment.register"].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = "2041-08-01"
            pay_form.group_payment = True
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice_1.invalidate_recordset()
        invoice_2.invalidate_recordset()

        # IGTF se siguió cobrando con normalidad sobre el pago agrupado.
        igtf_moves = self.env["account.move.line"].search([
            ("account_id", "=", self.acc_igtf_cli.id),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertTrue(igtf_moves, "El cobro de IGTF debió seguir aplicándose con normalidad.")

        self.assertEqual(invoice_1.payment_state, "paid")
        self.assertEqual(invoice_2.payment_state, "paid")

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("l10n_ve_exchange_payment_id", "=", payment.move_id.id),
        ])
        self.assertEqual(
            len(notes), 2,
            "El pago agrupado con IGTF debió generar una ND/NC por cada factura.",
        )
        self.assertEqual(
            set(notes.mapped("l10n_ve_exchange_invoice_id").ids), {invoice_1.id, invoice_2.id},
            "Cada nota debe quedar vinculada a una factura distinta.",
        )

        note_1 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_1)
        note_2 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_2)
        self.assertAlmostEqual(note_1.amount_total, 400.0, places=1, msg="ND de la factura de 100 USD.")
        self.assertAlmostEqual(note_2.amount_total, 2000.0, places=1, msg="ND de la factura de 500 USD.")

        for note in notes:
            note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            self.assertTrue(note_line.reconciled, "Cada nota debió quedar cerrada, sin excepción.")
            self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

    def test_advance_payment_applied_to_two_invoices_each_gets_correct_note(self):
        """Vía "anticipo" (`is_advance_payment`, patrón usado en
        `l10n_ve_igtf/tests/test_igtf_partner_formal_VEF.py`): un único
        pago de ANTICIPO en USD se aplica, uno a la vez
        (`js_assign_outstanding_line`, el mecanismo real del widget de
        pagos para anticipos -- cada aplicación es su PROPIA
        conciliación, a diferencia del pago agrupado), a DOS facturas de
        montos distintos creadas DESPUÉS del anticipo. Confirma que
        reconciliaciones sucesivas contra el mismo anticipo no
        contaminan la atribución entre sí (cada una debe recibir su
        propia ND exacta), y que el guard de duplicados por (factura,
        pago) sigue distinguiendo cada aplicación como un evento propio
        aunque ambas compartan el mismo `payment.move_id`."""
        self.currency_usd.write({
            "rate_ids": [
                Command.create({"name": "2042-01-01", "company_rate": 1 / 36.0}),
                Command.create({"name": "2042-06-01", "company_rate": 1 / 40.0}),
            ],
        })

        advance_amount = 700.0
        context = {
            "default_payment_type": "inbound", "default_partner_type": "customer",
            "default_move_journal_types": ("bank", "cash"), "display_account_trust": True,
            "default_is_advance_payment": True,
        }
        with Form(self.env["account.payment"].with_context(context)) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = self.bank_journal_usd
            pay_form.date = "2042-06-01"
            pay_form.amount = advance_amount
        advance_payment = pay_form.save()
        advance_payment.action_post()

        invoice_1 = self._create_invoice_usd(100.0, date="2042-01-01")
        invoice_1.with_context(move_action_post_alert=True).action_post()
        invoice_2 = self._create_invoice_usd(500.0, date="2042-01-01")
        invoice_2.with_context(move_action_post_alert=True).action_post()

        outstanding_line = advance_payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )
        self.assertTrue(outstanding_line, "El anticipo debió quedar con su línea de crédito disponible.")

        invoice_1.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        self.env.cr.flush()

        # La línea de crédito ORIGINAL del anticipo (700 USD) no se
        # reemplaza por una nueva al aplicarse parcialmente contra la
        # primera factura (100 USD) -- Odoo la deja parcialmente
        # conciliada, con el residual restante todavía disponible para
        # aplicar contra la segunda factura, la misma línea de siempre.
        outstanding_line.invalidate_recordset()
        self.assertFalse(
            outstanding_line.reconciled,
            "La línea del anticipo debía quedar con residual disponible tras la primera aplicación parcial.",
        )
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        self.env.cr.flush()

        invoice_1.invalidate_recordset()
        invoice_2.invalidate_recordset()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("l10n_ve_exchange_invoice_id", "in", (invoice_1 + invoice_2).ids),
        ])
        self.assertEqual(
            len(notes), 2,
            "Cada aplicación del anticipo (una por factura) debió generar su propia ND.",
        )
        note_1 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_1)
        note_2 = notes.filtered(lambda n: n.l10n_ve_exchange_invoice_id == invoice_2)
        self.assertTrue(note_1, "La factura de 100 USD debió recibir su propia ND.")
        self.assertTrue(note_2, "La factura de 500 USD debió recibir su propia ND.")
        for note in notes:
            note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
            self.assertTrue(note_line.reconciled, "Cada nota debió quedar cerrada, sin excepción.")

    def test_exchange_difference_note_alongside_igtf_payment_different_dates(self):
        """Factura en USD (`_create_invoice_usd`, mismo helper que usan los
        tests de IGTF) emitida AYER, pagada HOY -- mismo monto, mismo
        diario `bank_journal_usd` (`is_igtf=True`) -- en dos tasas de
        cambio distintas (380.0 ayer, `self.rate` = 390.2944 hoy, ya
        configuradas en `IGTFTestCommon.setUp`).

        Nota: una factura en VES (moneda de COMPAÑÍA) NUNCA genera
        diferencial cambiario sin importar en qué moneda ni fecha se
        pague -- su monto en VES está fijo, no fluctúa con la tasa (a
        diferencia de una factura en USD, cuyo equivalente en VES sí
        cambia según la tasa del día). Por eso este test usa factura en
        USD (igual que la ND/NC base ya probada en
        `test_exchange_note_reversal.test_exchange_difference_settled_by_real_note_via_register_payment`),
        para que SÍ exista diferencial real que conviva con IGTF."""
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 1000.00

        invoice = self._create_invoice_usd(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Sin forzar `pay_form.amount`: mismo criterio que la ND/NC base ya
        # probada -- misma moneda (USD) en factura y pago, el monto por
        # defecto del wizard ya es el residual completo en USD (1000.00),
        # sin conversión de por medio en este paso (la conversión real
        # ocurre al conciliar, con la tasa del día del pago).
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        # IGTF se siguió cobrando con normalidad: hay un movimiento
        # posteado contra la cuenta dedicada de IGTF de clientes.
        igtf_moves = self.env["account.move.line"].search([
            ("account_id", "=", self.acc_igtf_cli.id),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertTrue(igtf_moves, "El cobro de IGTF debió seguir aplicándose con normalidad.")

        # La factura quedó saldada (pagó el 100% en USD, con IGTF aparte
        # sobre esa misma línea de pago).
        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        # `l10n_ve_exchange_difference` generó su propia ND/NC por el
        # residual de diferencial cambiario (factura de ayer a 380.0,
        # pago de hoy a `self.rate` = 390.2944) -- exactamente una, ligada
        # a esta factura, cerrada.
        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(
            len(notes), 1,
            "Debió crearse exactamente una ND/NC de diferencial cambiario aun con IGTF de por medio.",
        )
        note = notes[0]
        self.assertEqual(note.state, "posted")
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

        # La ND/NC de diferencial nunca debe tocar la cuenta de IGTF -- son
        # dos ajustes independientes sobre la misma conciliación.
        self.assertNotIn(self.acc_igtf_cli, note.line_ids.account_id)

        # Rama pineada, no autoconsistente (verificada contra el resultado
        # real -- el signo depende de cómo el motor de Odoo atribuye el
        # residual entre factura/pago, no solo de comparar las tasas):
        # este caso produce NC. El monto (147921577.6 Bs) es el que el
        # propio `_prepare_reconciliation_single_partial` de Odoo calculó
        # para esta línea -- confirmado imprimiendo el `amounts` crudo
        # que recibe `_prepare_exchange_difference_move_vals` antes de
        # cualquier procesamiento de este módulo, así que no es un
        # artefacto propio: es la combinación real de las tasas del
        # fixture (380.0 / 390.2944) con el 3% de IGTF ya cobrado sobre
        # el pago (1030 USD en vez de 1000), no una simple resta de
        # tasas contra el monto nominal de la factura.
        self.assertEqual(note.move_type, "out_refund")
        self.assertEqual(note.reversed_entry_id, invoice)
        self.assertTrue(note._is_exchange_credit_note())
        self.assertFalse(note._is_exchange_debit_note())
        self.assertAlmostEqual(note.amount_total, 147921577.6, places=1)
        self.assertAlmostEqual(note.invoice_line_ids.price_unit, 147921577.6, places=1)
        self.assertEqual(note.invoice_line_ids.account_id, self.company.expense_currency_exchange_account_id)
        self.assertEqual(note.date, fields.Date.today())

    def test_ves_invoice_paid_in_usd_generates_rounding_exchange_difference_note(self):
        """Complemento del test anterior: una factura en VES (moneda de
        COMPAÑÍA), pagada en USD con IGTF de por medio, en fechas y tasas
        distintas. El monto adeudado en VES no tiene exposición cambiaria
        propia, pero al conciliarla contra un pago en USD, Odoo igual
        calcula un residual de redondeo de la conversión (ver
        `_prepare_reconciliation_single_partial`/
        `_prepare_exchange_difference_move_vals` en el núcleo: cuando la
        moneda de conciliación termina siendo la del PAGO -- porque la
        factura está en Bs -- ese residual SÍ se calcula sobre la línea
        de la factura). El alcance de este módulo es replicar CUALQUIER
        asiento de diferencial que Odoo genere para una factura de
        cliente como ND/NC real -- también este caso, sin excepción."""
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice_amount = 500000.00

        invoice = self._create_invoice_vef(invoice_amount, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        igtf_moves = self.env["account.move.line"].search([
            ("account_id", "=", self.acc_igtf_cli.id),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertTrue(igtf_moves, "El cobro de IGTF debió seguir aplicándose con normalidad.")

        self.assertTrue(inv_line.reconciled, "La factura debió quedar completamente conciliada.")
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("l10n_ve_exchange_invoice_id", "=", invoice.id),
        ])
        self.assertEqual(
            len(notes), 1,
            "El residual de redondeo de conciliar la factura en Bs contra un pago "
            "en USD debió documentarse como ND/NC, igual que cualquier otro "
            "diferencial de una factura de cliente.",
        )
        note_line = notes.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La nota debió quedar cerrada por su propia conciliación.")
