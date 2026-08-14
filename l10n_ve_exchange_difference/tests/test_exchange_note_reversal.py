from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("l10n_ve_exchange_difference", "-at_install", "post_install")
class TestExchangeNoteReversal(TransactionCase):
    """Prueba el flujo REAL tal como lo haría un usuario en el navegador:
    factura en USD -> botón 'Registrar Pago' (wizard `account.payment.register`,
    vía `Form`) -> pago en USD en una fecha con tasa distinta -> Odoo concilia
    internamente (llamando a nuestro `account.move.line.reconcile()`
    sobreescrito). Confirma, en un TransactionCase real (no `odoo shell`
    crudo), que el residual de diferencial cambiario se liquida con una
    ND/NC real sin el `RecursionError` que sí aparecía al intentar usar
    `account.move.reversal` para la Nota de Crédito."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.usd = cls.env.ref("base.USD")
        cls.usd.active = True

        # `expected_currency_rate`/`_get_conversion_rate` (lo que Odoo usa
        # para valorar la factura al contabilizarla) dependen de que la
        # compañía tenga su propia moneda (VEF) Y la "moneda alterna"
        # (`foreign_currency_id`, campo de `l10n_ve_rate`) configuradas --
        # sin esto, en una base limpia sin datos de módulo la compañía
        # queda con su moneda por defecto (USD) y sin moneda alterna, y el
        # cálculo de tasa cae al 1.0 por defecto sin importar qué
        # `res.currency.rate` se inyecten. Mismo patrón que usa
        # `l10n_ve_igtf` en sus tests (`IGTFTestCommon.setUp`,
        # `l10n_ve_igtf/tests/test_igtf_common_providers_formal_VEF.py`).
        cls.company.write({
            "currency_id": cls.env.ref("base.VEF").id,
            "foreign_currency_id": cls.usd.id,
        })

        # Dos tasas distintas para forzar un diferencial cambiario real al
        # conciliar la factura (fecha 2026-01-01, tasa MAYOR) contra el pago
        # (2026-08-01, tasa MENOR) -- el pago vale MENOS en VEF de lo que la
        # factura necesitaba, dejando un residual en DÉBITO ("falta") del
        # lado de la propia factura -> Nota de Crédito.
        #
        # `company_rate` va INVERTIDO (1/tasa_vef_por_usd) -- mismo patrón
        # que usa `l10n_ve_igtf` en sus tests
        # (`l10n_ve_igtf/tests/test_igtf_common_providers_formal_VEF.py`):
        # ahí `self.rate = 390.2944` (VEF por USD) pero se escribe
        # `'company_rate': 1/self.rate`. Pasarlo directo (sin invertir, como
        # se hacía antes) produce tasas de escala absurda (~0.025 en vez de
        # ~40) y diferenciales cambiarios minúsculos/irreales. También hay
        # que activar la moneda en el MISMO `write()` que las tasas.
        cls.rate_invoice_date = 40.0
        cls.rate_payment_date = 36.0
        cls.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2026-01-01",
                    "company_rate": 1 / cls.rate_invoice_date,
                }),
                Command.create({
                    "name": "2026-08-01",
                    "company_rate": 1 / cls.rate_payment_date,
                }),
            ],
        })

        cls.partner = cls.env["res.partner"].create({"name": "Cliente Prueba Reversal"})
        cls.partner.property_product_pricelist = False
        receivable = cls.env["account.account"].search(
            [*cls.env["account.account"]._check_company_domain(cls.company), ("account_type", "=", "asset_receivable")],
            limit=1,
        )
        cls.partner.property_account_receivable_id = receivable.id

        # `company.exent_aliquot_sale` depende de datos de configuración que
        # no existen en una base limpia sin datos de módulo -- se busca un
        # impuesto de venta al 0% ya existente (ej. "0% Exports", viene con
        # los datos fiscales base) en vez de depender de esa configuración.
        cls.exent = cls.env["account.tax"].search([
            ("type_tax_use", "=", "sale"), ("amount", "=", 0.0),
            ("company_id", "=", cls.company.id),
        ], limit=1)
        # `supplier_taxes_id` explícito -- sin esto, el default que arma
        # Odoo para ese campo en `create()` puede traer más de un impuesto
        # en bases con varios impuestos de compra al 0% configurados, y
        # `l10n_ve_accountant` (`_enforce_single_tax_vals`) rechaza
        # cualquier producto con más de un impuesto de compra asignado.
        cls.exent_purchase = cls.env["account.tax"].search([
            ("type_tax_use", "=", "purchase"), ("amount", "=", 0.0),
            ("company_id", "=", cls.company.id),
        ], limit=1)
        cls.note_product = cls.env["product.product"].create({
            "name": "Diferencial Test Reversal",
            "type": "service",
            "taxes_id": [(6, 0, cls.exent.ids)],
            "supplier_taxes_id": [(6, 0, cls.exent_purchase.ids)],
        })
        cls.company.l10n_ve_exchange_note_product_id = cls.note_product.id
        cls.company.l10n_ve_exchange_use_nd_nc = True

        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        # Se reusa un diario de banco en USD si ya existe uno bien
        # configurado (con métodos de pago/cuentas asignadas); si no (base
        # limpia sin datos de módulo), se crea uno mínimo -- Odoo arma la
        # cuenta contable y los métodos de pago del diario automáticamente
        # al crear un `account.journal` de tipo `bank`.
        cls.usd_bank_journal = cls.env["account.journal"].search(
            [
                *cls.env["account.journal"]._check_company_domain(cls.company),
                ("type", "=", "bank"), ("currency_id", "=", cls.usd.id),
            ],
            limit=1,
        )
        if not cls.usd_bank_journal:
            bank_account = cls.env["account.account"].create({
                "name": "Banco USD Prueba Reversal",
                "code": "BUSDR01",
                "account_type": "asset_cash",
                "currency_id": cls.usd.id,
            })
            cls.usd_bank_journal = cls.env["account.journal"].create({
                "name": "Banco USD Prueba Reversal",
                "type": "bank",
                "code": "BUSDR",
                "currency_id": cls.usd.id,
                "company_id": cls.company.id,
                "default_account_id": bank_account.id,
                # El asistente "Registrar Pago" exige un método de pago
                # (`payment_method_line_id`) -- se deja uno solo (manual),
                # con cuenta asignada (si no, Odoo rechaza el método).
                "inbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                    "name": "Manual",
                    "payment_method_id": cls.env.ref("account.account_payment_method_manual_in").id,
                    "payment_account_id": bank_account.id,
                })],
                # Método saliente también, para poder pagar facturas de
                # PROVEEDOR (caso de fallback: factura que no es de
                # cliente, ver `test_fallback_tags_generic_exchange_move_for_vendor_bill`).
                "outbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                    "name": "Manual",
                    "payment_method_id": cls.env.ref("account.account_payment_method_manual_out").id,
                    "payment_account_id": bank_account.id,
                })],
            })
        cls.sale_product = cls.env["product.product"].create({
            "name": "Servicio Test Reversal",
            "type": "service",
            "taxes_id": [(6, 0, cls.exent.ids)],
            "supplier_taxes_id": [(6, 0, cls.exent_purchase.ids)],
        })

        # Diario de banco en la moneda DE COMPAÑÍA (VEF) -- necesario para
        # reproducir el caso "factura en USD pagada directo en VEF"
        # (`test_exchange_difference_settled_with_company_currency_payment`):
        # a diferencia de `usd_bank_journal`, aquí la línea de conciliación
        # del pago queda en VEF, distinta de la moneda de la factura.
        cls.vef_bank_journal = cls.env["account.journal"].search(
            [
                *cls.env["account.journal"]._check_company_domain(cls.company),
                ("type", "=", "bank"), ("currency_id", "=", False),
            ],
            limit=1,
        )
        if not cls.vef_bank_journal:
            vef_bank_account = cls.env["account.account"].create({
                "name": "Banco VEF Prueba Reversal",
                "code": "BVEFR01",
                "account_type": "asset_cash",
            })
            cls.vef_bank_journal = cls.env["account.journal"].create({
                "name": "Banco VEF Prueba Reversal",
                "type": "bank",
                "code": "BVEFR",
                "company_id": cls.company.id,
                "default_account_id": vef_bank_account.id,
                "inbound_payment_method_line_ids": [(5, 0, 0), (0, 0, {
                    "name": "Manual",
                    "payment_method_id": cls.env.ref("account.account_payment_method_manual_in").id,
                    "payment_account_id": vef_bank_account.id,
                })],
            })

    def _create_invoice(self, invoice_date):
        """Mismo patrón que usa `l10n_ve_igtf` para sus facturas de prueba
        (`IGTFTestCommon._create_invoice_usd`, ver
        `l10n_ve_igtf/tests/test_igtf_common_providers_formal_VEF.py`):
        el encabezado se guarda primero con un `Form`, y las líneas se
        agregan en un SEGUNDO `Form` sobre el registro ya guardado -- así
        se disparan los onchange/recompute de impuestos y totales en cada
        paso, en vez de dejar todo en un solo `create()` con
        `invoice_line_ids` embebido de una vez."""
        with Form(self.env["account.move"].with_context(default_move_type="out_invoice")) as inv_form:
            inv_form.partner_id = self.partner
            inv_form.invoice_date = invoice_date
            # `journal_id` ANTES que `currency_id`: el onchange del diario
            # reasigna la moneda a la del propio diario (VEF, la de la
            # compañía) si se hace en el orden contrario, pisando el USD.
            inv_form.journal_id = self.sale_journal
            inv_form.currency_id = self.usd
        invoice = inv_form.save()

        with Form(invoice) as inv_form_edit:
            with inv_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.sale_product
                line.quantity = 1
                line.price_unit = 100.0
        return inv_form_edit.save()

    def test_exchange_difference_settled_by_real_note_via_register_payment(self):
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # Botón "Registrar Pago" de la factura, simulado con Form (igual que
        # el navegador): mismo monto (100 USD) que la factura, pero pagado en
        # una fecha con una tasa distinta -- ahí nace el diferencial.
        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        # La ND/NC se difiere a un precommit hook (para que se cree/postee
        # con la pila de llamadas ya desenrollada, ver `reconcile()`) --
        # se fuerza el flush para que corra antes de verificar el resultado,
        # tal como pasaría naturalmente al final de un request real.
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        self.assertEqual(note.state, "posted")
        self.assertIn(note.move_type, ("out_invoice", "out_refund"))
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

        # Sea cual sea la dirección (ND si sobra/ganancia vía
        # `account.debit.note` con `debit_origin_id`, o NC si falta/pérdida
        # vía `account.move.reversal` con `reversed_entry_id`), la nota
        # SIEMPRE debe quedar vinculada a la factura de origen -- sin
        # importar si el residual terminó cayendo del lado de la factura o
        # del pago (normalmente cae del lado del pago, eso es lo esperado).
        self.assertEqual(note.l10n_ve_exchange_invoice_id, invoice)
        if note.l10n_ve_exchange_is_credit_note:
            self.assertEqual(note.move_type, "out_refund")
            self.assertEqual(note.reversed_entry_id, invoice)
        else:
            self.assertEqual(note.move_type, "out_invoice")
            self.assertEqual(note.debit_origin_id, invoice)

    def test_exchange_difference_settled_with_company_currency_payment(self):
        """Mismo flujo que `test_exchange_difference_settled_by_real_note_via_register_payment`,
        pero pagando la factura en USD directo con un diario de banco en
        VEF (la moneda de compañía) -- reproduce el reporte del usuario
        ("pago una factura en dólares con VEF"). Antes de este fix,
        `reconcile()` exigía `invoice_line.currency_id == payment_line.currency_id`;
        al pagar en VEF una factura en USD esa igualdad nunca se cumplía,
        y el diferencial cambiario se perdía por completo (ni ND/NC propia
        ni asiento genérico de Odoo, por el `no_exchange_difference=True`)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.vef_bank_journal
            # El wizard, por defecto, mantiene la moneda de la factura (USD)
            # sin importar la moneda del diario -- para reproducir el
            # reporte real ("pago una factura en dólares con VEF") hay que
            # forzar explícitamente la moneda del PAGO a VEF, tal como haría
            # un usuario que cambia ese campo en el formulario.
            pay_form.currency_id = self.company.currency_id
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        self.assertEqual(payment_wizard.currency_id, self.company.currency_id)
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(
            len(notes), 1,
            "Debió crearse exactamente una ND/NC de diferencial cambiario aun pagando en VEF "
            "una factura en USD.",
        )
        note = notes[0]
        self.assertEqual(note.state, "posted")
        self.assertEqual(note.l10n_ve_exchange_invoice_id, invoice)
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

    def test_exchange_note_reversed_on_unreconcile(self):
        """Si se rompe la conciliación factura<->pago que originó la
        ND/NC (botón 'x' del widget de pagos, `js_remove_outstanding_partial`),
        la nota YA POSTEADA (con correlativo fiscal real) no puede
        simplemente cancelarse/borrarse -- debe revertirse, igual que hace
        Odoo con su propio asiento genérico de diferencial cambiario al
        desconciliar (`account.partial.reconcile.unlink()`: revierte si
        está posteado, borra si sigue en borrador)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        self.assertEqual(note.state, "posted")

        # Botón "x" del widget de pagos sobre la factura: rompe la
        # conciliación factura<->pago (no la de la nota contra la factura
        # o el pago, esa es una conciliación distinta).
        inv_line.invalidate_recordset()
        partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        self.assertTrue(partial, "Debía existir una conciliación factura<->pago para poder romperla.")
        invoice.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertFalse(inv_line.reconciled, "La factura debió quedar desconciliada del pago.")

        # La nota original NO se cancela ni se borra (documento fiscal ya
        # posteado con correlativo real) -- sigue existiendo, posteada.
        note.invalidate_recordset()
        self.assertEqual(note.state, "posted")

        # Se creó una reversión de la nota, vinculada a ella y ya
        # conciliada/cerrada contra ella (cancel=True).
        reversal = self.env["account.move"].search([
            ("reversed_entry_id", "=", note.id),
        ])
        self.assertEqual(len(reversal), 1, "Debió crearse exactamente una reversión de la ND/NC.")
        self.assertEqual(reversal.state, "posted")
        self.assertTrue(reversal.l10n_ve_exchange_diff_entry)

        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La nota original debió quedar cerrada por su propia reversión.")

    def test_exchange_note_own_reconciliation_cannot_be_broken_directly(self):
        """La conciliación que cierra la ND/NC contra la factura/pago NO
        se puede romper suelta -- ni haciendo click desde la propia nota,
        ni desde la factura viendo esa reconciliación puntual en su lista
        de pagos. Solo debe deshacerse como consecuencia de romper la
        conciliación ORIGINAL factura<->pago (ver
        `test_exchange_note_reversed_on_unreconcile`)."""
        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        # La conciliación que cierra la nota (nota <-> factura/pago, según
        # la rama), vista desde la propia nota.
        note_partial = note_line.matched_debit_ids | note_line.matched_credit_ids
        self.assertTrue(note_partial, "La nota debía quedar conciliada contra la factura/pago.")

        with self.assertRaises(UserError):
            note.js_remove_outstanding_partial(note_partial[:1].id)

        # Mismo bloqueo visto desde el OTRO lado de esa conciliación
        # puntual (la factura o el pago, según a cuál se ligó la nota).
        other_move = (note_partial[:1].debit_move_id.move_id | note_partial[:1].credit_move_id.move_id) - note
        if other_move:
            with self.assertRaises(UserError):
                other_move.js_remove_outstanding_partial(note_partial[:1].id)

        # Nada se rompió: la nota sigue conciliada y posteada.
        note.invalidate_recordset()
        note_line.invalidate_recordset()
        self.assertEqual(note.state, "posted")
        self.assertTrue(note_line.reconciled)

    def test_exchange_difference_credit_note_branch(self):
        """Mismo flujo (factura USD -> 'Registrar Pago' vía Form -> pago USD
        en fecha con tasa distinta), con tasa de la factura MAYOR que la
        del pago -- residual = matched_amount * (inv_rate - pay_rate) > 0
        -> rama de residual en DÉBITO ("falta") -> Nota de Crédito."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2027-01-01",
                    "company_rate": 1 / 40.0,
                }),
                Command.create({
                    "name": "2027-08-01",
                    "company_rate": 1 / 36.0,
                }),
            ],
        })

        invoice = self._create_invoice("2027-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2027-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        payment.action_post()

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        self.assertEqual(note.state, "posted")
        self.assertEqual(note.l10n_ve_exchange_invoice_id, invoice)
        self.assertTrue(
            note.l10n_ve_exchange_is_credit_note,
            "Con la tasa de la factura menor que la del pago, se esperaba la rama de Nota de Crédito.",
        )
        self.assertEqual(note.move_type, "out_refund")
        self.assertEqual(note.reversed_entry_id, invoice)
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

    def test_exchange_difference_debit_note_branch(self):
        """Mismo flujo, con tasa de la factura MENOR que la del pago --
        residual = matched_amount * (inv_rate - pay_rate) < 0 -> rama de
        residual en CRÉDITO ("sobra"/ganancia) -> Nota de Débito vía
        `account.debit.note` (con `debit_origin_id`)."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2029-01-01",
                    "company_rate": 1 / 36.0,
                }),
                Command.create({
                    "name": "2029-08-01",
                    "company_rate": 1 / 40.0,
                }),
            ],
        })

        invoice = self._create_invoice("2029-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2029-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        payment.action_post()

        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1, "Debió crearse exactamente una ND/NC de diferencial cambiario.")
        note = notes[0]
        self.assertEqual(note.state, "posted")
        self.assertEqual(note.l10n_ve_exchange_invoice_id, invoice)
        self.assertFalse(
            note.l10n_ve_exchange_is_credit_note,
            "Con la tasa de la factura mayor que la del pago, se esperaba la rama de Nota de Débito.",
        )
        self.assertEqual(note.move_type, "out_invoice")
        self.assertEqual(note.debit_origin_id, invoice)
        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(note_line.amount_residual))

    def test_exchange_note_debit_note_reversed_on_unreconcile(self):
        """La reversión al desconciliar (ver
        `test_exchange_note_reversed_on_unreconcile`) también debe
        funcionar cuando la nota original es una ND (Nota de Débito, no
        NC) -- confirma que `_reverse_moves` (con su ajuste propio para
        `_is_exchange_debit_note()`, ver `models/account_move.py`) deja
        `l10n_ve_exchange_original_id` apuntando a la ND revertida."""
        self.usd.write({
            "active": True,
            "rate_ids": [
                Command.create({
                    "name": "2030-01-01",
                    "company_rate": 1 / 36.0,
                }),
                Command.create({
                    "name": "2030-08-01",
                    "company_rate": 1 / 40.0,
                }),
            ],
        })

        invoice = self._create_invoice("2030-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2030-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        self.env.cr.flush()
        invoice.invalidate_recordset()

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertFalse(note.l10n_ve_exchange_is_credit_note, "Este caso debía producir una ND.")
        self.assertEqual(note.state, "posted")

        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        partial = (inv_line.matched_debit_ids | inv_line.matched_credit_ids).filtered(
            lambda p: invoice in (p.debit_move_id.move_id, p.credit_move_id.move_id)
        )
        self.assertTrue(partial, "Debía existir una conciliación factura<->pago para poder romperla.")
        invoice.js_remove_outstanding_partial(partial[:1].id)
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()
        self.assertFalse(inv_line.reconciled, "La factura debió quedar desconciliada del pago.")

        # La ND original no se cancela ni se borra -- sigue posteada.
        note.invalidate_recordset()
        self.assertEqual(note.state, "posted")

        # Se creó una reversión (Nota de Crédito, `move_type` se invierte
        # de `out_invoice` a `out_refund`), vinculada a la ND vía
        # `l10n_ve_exchange_original_id` (no `reversed_entry_id` -- ese
        # campo lo usa Odoo para la reversión NATIVA de un documento
        # cualquiera; `l10n_ve_exchange_original_id` es el que usamos
        # específicamente para "esta NC revierte aquella ND de
        # diferencial").
        reversal = self.env["account.move"].search([
            ("l10n_ve_exchange_original_id", "=", note.id),
        ])
        self.assertEqual(len(reversal), 1, "Debió crearse exactamente una reversión de la ND.")
        self.assertEqual(reversal.state, "posted")
        self.assertEqual(reversal.move_type, "out_refund")
        self.assertTrue(reversal.l10n_ve_exchange_diff_entry)

        note_line = note.line_ids.filtered(lambda l: l.account_type == "asset_receivable")
        self.assertTrue(note_line.reconciled, "La ND original debió quedar cerrada por su propia reversión.")

    def test_exchange_use_nd_nc_disabled_uses_native_exchange_entry(self):
        """Con `l10n_ve_exchange_use_nd_nc` desactivado, `reconcile()` no
        debe aplicar ninguna lógica propia -- cae directo al
        `super().reconcile()` nativo de Odoo (con su propio asiento
        genérico de diferencial, sin el context `no_exchange_difference`),
        y no debe crearse ninguna ND/NC nuestra."""
        self.company.l10n_ve_exchange_use_nd_nc = False

        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()
        inv_line = invoice.line_ids.filtered(lambda l: l.account_type == "asset_receivable")

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        invoice.invalidate_recordset()
        inv_line.invalidate_recordset()

        self.assertEqual(invoice.payment_state, "paid")
        self.assertTrue(inv_line.reconciled)
        self.assertTrue(self.company.currency_id.is_zero(inv_line.amount_residual))

        notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("partner_id", "=", self.partner.id),
        ])
        self.assertFalse(notes, "Con el modo ND/NC desactivado no debió crearse ninguna nota nuestra.")

    def test_missing_note_product_raises_user_error(self):
        """Si no se configuró el producto de diferencial cambiario
        (`res.company.l10n_ve_exchange_note_product_id`), no se debe
        crear una nota "a medias" -- debe fallar con un `UserError` claro
        (ver `_create_exchange_difference_note`)."""
        self.company.l10n_ve_exchange_note_product_id = False

        invoice = self._create_invoice("2026-01-01")
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))

        # La ND/NC se crea en el precommit, disparado por el `flush()` --
        # el error debe propagarse desde ahí. No se usa `assertRaises`
        # como context manager: internamente crea su propio savepoint
        # (`cr.savepoint()`), que a su vez hace su propio `cr.flush()`
        # ANTES de entrar al bloque `with` -- el error se dispararía ahí
        # mismo, fuera de lo que `assertRaises` alcanza a capturar. Se usa
        # un `try/except` directo en su lugar.
        try:
            self.env.cr.flush()
            self.fail("Se esperaba un UserError por falta del producto de diferencial cambiario.")
        except UserError:
            pass

    def test_fallback_tags_generic_exchange_move_for_vendor_bill(self):
        """Cuando la línea que queda con residual NO pertenece a una
        factura de cliente (ej. una factura de PROVEEDOR), `reconcile()`
        no aplica su lógica de ND/NC -- cae directo al flujo nativo de
        Odoo (`_prepare_exchange_difference_move_vals`, fallback al
        principio del archivo), que sí genera su propio asiento genérico
        de diferencial cambiario (`move_type='entry'`). Ese asiento debe
        quedar igualmente etiquetado con `l10n_ve_exchange_diff_entry`."""
        supplier = self.env["res.partner"].create({"name": "Proveedor Prueba Reversal"})
        supplier.property_product_pricelist = False
        payable = self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company),
                ("account_type", "=", "liability_payable"),
            ],
            limit=1,
        )
        supplier.property_account_payable_id = payable.id

        purchase_journal = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)], limit=1
        )

        # `company.quick_edit_mode` -- sin esto, el campo `name` viene
        # invisible en el Form (`account.view_move_form`, núcleo de Odoo:
        # solo se muestra si ya tiene valor, si hay `name_placeholder`
        # calculado -esto último solo pasa si el diario de compras AÚN NO
        # tiene ninguna secuencia previa, cosa que no se cumple en una base
        # con datos reales-, o si `move.quick_edit_mode` es `True`). Ese
        # campo es COMPUTADO desde `company.quick_edit_mode` (no un simple
        # valor de contexto) -- hay que activarlo a nivel de compañía para
        # las facturas de proveedor.
        self.company.quick_edit_mode = "in_invoices"
        with Form(self.env["account.move"].with_context(default_move_type="in_invoice")) as bill_form:
            bill_form.partner_id = supplier
            bill_form.invoice_date = "2026-01-01"
            bill_form.journal_id = purchase_journal
            bill_form.currency_id = self.usd
            # Referencia del proveedor y correlativo fiscal -- ambos
            # requeridos para facturas de proveedor (a diferencia de las
            # de cliente, que los calculan solas con la secuencia del
            # diario).
            bill_form.name = "BILL-TEST-0001"
            bill_form.correlative = "00-00000001"
        bill = bill_form.save()
        with Form(bill) as bill_form_edit:
            with bill_form_edit.invoice_line_ids.new() as line:
                line.product_id = self.sale_product
                line.quantity = 1
                line.price_unit = 100.0
        bill = bill_form_edit.save()
        bill.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, bill.action_register_payment()) as pay_form:
            pay_form.journal_id = self.usd_bank_journal
            pay_form.payment_date = "2026-08-01"
            pay_form.save()
        payment_wizard = pay_form.record
        action = payment_wizard.action_create_payments()
        self.env["account.payment"].browse(action.get("res_id"))
        self.env.cr.flush()

        bill.invalidate_recordset()
        self.assertEqual(bill.payment_state, "paid")

        # Ninguna ND/NC "de negocio" (documento fiscal `out_invoice`/
        # `out_refund`) nuestra debió crearse para esto.
        business_notes = self.env["account.move"].search([
            ("l10n_ve_exchange_diff_entry", "=", True),
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("partner_id", "=", supplier.id),
        ])
        self.assertFalse(business_notes)

        # El asiento genérico nativo de Odoo sí debió generarse, y quedar
        # etiquetado.
        generic_exchange_moves = self.env["account.move"].search([
            ("move_type", "=", "entry"),
            ("l10n_ve_exchange_diff_entry", "=", True),
        ])
        self.assertTrue(
            generic_exchange_moves,
            "Debió generarse (y etiquetarse) el asiento genérico nativo de diferencial.",
        )
