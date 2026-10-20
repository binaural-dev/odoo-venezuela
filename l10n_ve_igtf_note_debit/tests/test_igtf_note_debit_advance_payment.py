from odoo.tests import tagged, Form
from odoo.tools import float_compare
from odoo import fields

from odoo.addons.l10n_ve_igtf.tests.test_igtf_common_partner_formal_VEF import IGTFTestCommon


@tagged("igtf_note_debit", "-at_install", "post_install")
class TestIgtfNoteDebitAdvancePayment(IGTFTestCommon):
    """Cobertura de los flujos de anticipo / desconciliación de
    `account_move.py` bajo el modo 'debit_note':

      * `js_assign_outstanding_line` -- aplicar un anticipo (pago sin
        factura de origen) contra una factura, cuando el pago viene de un
        diario IGTF.
      * `remove_igtf_from_account_move` / `create_note_credit_igtf` --
        desconciliar un pago ya aplicado, revirtiendo la ND de IGTF con una
        Nota de Crédito.

    Replica el mismo patrón que usan los tests `test03`/`test12` de
    `l10n_ve_igtf`, pero verificando que bajo 'debit_note' el resultado sea
    una ND real (no una línea embebida en el asiento)."""

    def setUp(self):
        super().setUp()

        # `IGTFTestCommon` fija `country_id` en Venezuela pero no
        # `account_fiscal_country_id` (quedaría en el país demo por
        # defecto) -- la reversión de la ND para la Nota de Crédito sí
        # depende de ese campo para la restricción `_validate_taxes_country`.
        self.company.write({"account_fiscal_country_id": self.company.country_id.id})

        self.igtf_note_debit_product = self.env["product.product"].create({
            "name": "Percepción de IGTF (ND anticipo test)",
            "type": "service",
            "taxes_id": [(6, 0, [self.tax_iva_exent.id])],
            # `supplier_taxes_id` explícito: sin esto, el default de compra
            # de la compañía trae más de un impuesto al 0% y
            # `l10n_ve_accountant` (`_enforce_single_tax_vals`) rechaza el
            # producto. Reutilizamos el mismo impuesto de compra exento
            # que `IGTFTestCommon` ya asignó a `self.product`.
            "supplier_taxes_id": [(6, 0, self.product.supplier_taxes_id.ids)],
        })
        self.debit_sale_journal = self.Journal.create({
            "name": "ND Forma Libre (anticipo test)",
            "code": "NDFLA",
            "type": "sale",
            "is_debit": True,
            "company_id": self.company.id,
        })
        self.company.write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_note_debit_product.id,
        })

    def _create_advance_payment(self, journal, amount):
        context = {
            'default_payment_type': 'inbound',
            'default_partner_type': 'customer',
            'search_default_inbound_filter': 1,
            'default_move_journal_types': ('bank', 'cash'),
            'display_account_trust': True,
            'default_is_advance_payment': True,
        }
        with Form(self.env['account.payment'].with_context(context)) as pay_form:
            pay_form.partner_id = self.partner
            pay_form.journal_id = journal
            pay_form.amount = amount
        payment = pay_form.save()
        payment.action_post()
        return payment

    def _create_plain_payment(self, journal, amount):
        """Pago SIN el contexto `default_is_advance_payment` -- replica el
        flujo real de un pago suelto (creado aparte, sin factura de origen,
        sin marcarlo explícitamente como 'anticipo') que luego se aplica a
        mano contra una factura desde su propio widget de créditos
        pendientes. A diferencia de `_create_advance_payment`, este pago NO
        queda con `is_advance_payment=True`, así que aplicar su línea
        sobrante ejercita la rama "no es anticipo" de
        `js_assign_outstanding_line` (líneas 194-291 de account_move.py)."""
        payment = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": amount,
            "journal_id": journal.id,
        })
        payment.action_post()
        return payment

    def test_usd_plain_payment_applied_to_two_invoices_hits_deep_branch(self):
        """Pago suelto en USD (diario IGTF), por más de lo que debe la
        factura 1 -- se aplica PRIMERO a la factura 1 (parcial) y el
        remanente de la MISMA línea se aplica luego a la factura 2, sin
        pasar nunca por el mecanismo de 'anticipo' -- exactamente el
        camino que usa `test10`/`test11` de `l10n_ve_igtf`."""
        invoice_1 = self._create_invoice_usd(600.00)
        invoice_1.with_context(move_action_post_alert=True).action_post()
        invoice_2 = self._create_invoice_usd(300.00)
        invoice_2.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_usd, 1000.00)
        self.assertFalse(payment.is_advance_payment)

        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.credit > 0
        )
        self.assertTrue(outstanding_line, "El pago suelto debe dejar una línea CxC sin conciliar.")

        invoice_1.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice_1 = self.env["account.move"].browse(invoice_1.id)
        self.assertIn(invoice_1.payment_state, ("paid", "partial", "in_payment"))
        debit_notes_1 = invoice_1.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(debit_notes_1), 1, "La factura 1 debe generar su propia ND.")

        # La MISMA línea (ahora con residual reducido) se reutiliza para la
        # factura 2 -- su `move_id` sigue siendo el del pago original, sin
        # bandera de anticipo alguna.
        outstanding_line = self.env["account.move.line"].browse(outstanding_line.id)
        self.assertFalse(outstanding_line.reconciled, "Debe quedar residual tras cubrir solo la factura 1.")

        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice_2 = self.env["account.move"].browse(invoice_2.id)
        self.assertIn(invoice_2.payment_state, ("paid", "partial", "in_payment"))
        debit_notes_2 = invoice_2.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(
            len(debit_notes_2), 1,
            "La factura 2, cubierta por el remanente del MISMO pago suelto, también debe generar su ND.",
        )
        self.assertNotEqual(
            debit_notes_1.id, debit_notes_2.id,
            "Cada factura debe tener su propia ND, no compartir la misma.",
        )

    def test_js_assign_outstanding_line_passthrough_in_inline_mode(self):
        """Con modo 'inline' (no 'debit_note'), `js_assign_outstanding_line`
        debe delegar siempre a `super()` sin ejecutar ninguna lógica propia
        de ND -- confirma el guard de la primera línea del override."""
        self.company.write({"igtf_note_debit_mode": "inline"})
        invoice = self._create_invoice_usd(600.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_usd, 600.00)
        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.credit > 0
        )
        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertFalse(
            invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin),
            "En modo 'inline' nunca debe generarse una ND de IGTF.",
        )

    def test_plain_payment_from_non_igtf_journal_skips_deep_debit_note_logic(self):
        """Pago suelto (no anticipo) por un diario que NO es IGTF -- debe
        pasar por la rama profunda de `js_assign_outstanding_line` hasta el
        chequeo de `is_igtf_journal` y ahí delegar a `super()` sin generar ND."""
        invoice = self._create_invoice_vef(600.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_bs, 600.00)
        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.credit > 0 and l.account_id.account_type in ("asset_receivable", "liability_payable")
        )
        self.assertTrue(outstanding_line)

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertFalse(
            invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin),
            "Un pago suelto de un diario sin IGTF no debe generar Nota de Débito.",
        )

    def test_usd_advance_payment_assigned_generates_debit_note(self):
        """Anticipo en USD (diario IGTF) aplicado contra una factura en USD
        -- debe generar la ND de IGTF sin línea embebida en el cruce."""
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_advance_payment(self.bank_journal_usd, 600.00)
        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice = self.env["account.move"].browse(invoice.id)

        debit_notes = invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(debit_notes), 1, "Debe generarse una ND de IGTF al asignar el anticipo.")
        debit_note = debit_notes[0]
        self.assertEqual(debit_note.currency_id, self.currency_vef)
        self.assertGreaterEqual(invoice.bi_igtf, 0.0)
        self.assertGreaterEqual(invoice.foreign_bi_igtf, 0.0)

        cross_move_advance = self.env["account.move"].search([], order="id desc", limit=1)
        self.assertFalse(
            cross_move_advance.line_ids.filtered(
                lambda l: l.account_id in (self.acc_igtf_cli, self.acc_igtf_prov)
            ),
            "El asiento de cruce del anticipo no debe llevar línea de IGTF embebida.",
        )

    def test_eur_advance_payment_assigned_generates_debit_note(self):
        """Mismo flujo que el anterior, pero con anticipo y factura en EUR
        -- confirma que el cálculo de IGTF de anticipo es independiente de
        la moneda extranjera usada."""
        invoice = self._create_invoice_eur(500.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_advance_payment(self.bank_journal_eur, 300.00)
        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice = self.env["account.move"].browse(invoice.id)

        debit_notes = invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(debit_notes), 1, "Debe generarse una ND de IGTF al asignar el anticipo en EUR.")
        self.assertEqual(debit_notes[0].currency_id, self.currency_vef)

    def test_assign_outstanding_line_skips_when_not_igtf_journal(self):
        """Control negativo: aplicar un anticipo de un diario que NO es
        IGTF no debe generar ninguna ND (pasa directo a `super()`)."""
        invoice = self._create_invoice_vef(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_advance_payment(self.bank_journal_bs, 1000.00)
        outstanding_line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.advance_cust_acc and l.credit > 0
        )

        invoice.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertFalse(
            invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin),
            "Un anticipo de diario sin IGTF no debe generar Nota de Débito.",
        )

    def test_usd_overpayment_residual_assigned_to_second_invoice_generates_debit_note(self):
        """Pagar de más (sobrepago) por diario IGTF genera automáticamente
        un residual como anticipo -- aplicar luego ese residual a una
        SEGUNDA factura ejercita la rama profunda de
        `js_assign_outstanding_line` (pago real, no anticipo explícito) y
        debe generar una ND de IGTF también para esa segunda factura."""
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            pay_form.amount = 1500.00
            pay_form.save()
        action = pay_form.record.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        invoice = self.env["account.move"].browse(invoice.id)
        debit_notes_1 = invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(debit_notes_1), 1, "La factura 1 debe tener su propia ND de IGTF.")

        outstanding_line = self.env["account.move.line"].search([
            ("account_id", "=", self.advance_cust_acc.id),
            ("credit", ">", 0),
            ("reconciled", "=", False),
        ])
        self.assertTrue(outstanding_line, "Debe haberse generado un residual como anticipo por el sobrepago.")

        invoice_2 = self._create_invoice_usd(400.00)
        invoice_2.with_context(move_action_post_alert=True).action_post()
        invoice_2.with_context({}).js_assign_outstanding_line(outstanding_line.id)
        invoice_2 = self.env["account.move"].browse(invoice_2.id)

        debit_notes_2 = invoice_2.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(
            len(debit_notes_2), 1,
            "Al aplicar el residual (originado en un pago con diario IGTF) contra la "
            "factura 2, debe generarse también su propia ND de IGTF.",
        )
        self.assertEqual(invoice_2.payment_state, "paid")
        self.assertGreaterEqual(invoice.bi_igtf, 0.0)
        self.assertGreaterEqual(invoice_2.bi_igtf, 0.0)

    def test_usd_payment_desconciliation_creates_credit_note_for_debit_note(self):
        """Pagar de una vez vía diario IGTF (genera ND), luego desconciliar
        el pago (`js_remove_outstanding_partial` + wizard de cancelación) --
        debe reversar la ND con una Nota de Crédito real."""
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            pay_form.amount = 1000.00
            pay_form.save()
        action = pay_form.record.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        payment_move = payment.move_id

        debit_notes = invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(debit_notes), 1)
        debit_note = debit_notes[0]
        self.assertEqual(debit_note.state, "posted")

        outstanding_line = payment_move.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.credit > 0
        )
        invoice = self.env["account.move"].browse(invoice.id)
        invoice_receivable_line = invoice.line_ids.filtered(
            lambda l: l.account_id == self.acc_receivable and l.debit > 0
        )
        partial_reconcile = outstanding_line.matched_debit_ids.filtered(
            lambda p: p.debit_move_id == invoice_receivable_line
        )

        # El pago cubrió exactamente el 100% de la factura (sin remanente de
        # anticipo) -- `js_remove_outstanding_partial` no dispara el wizard
        # de confirmación en ese caso, sino que llama directo a
        # `remove_igtf_from_account_move` (mismo método que el wizard usa
        # internamente cuando el usuario confirma).
        invoice.with_context({}).js_remove_outstanding_partial(partial_reconcile.id)

        debit_note = self.env["account.move"].browse(debit_note.id)
        reversal_moves = self.env["account.move"].search([
            ("reversed_entry_id", "=", debit_note.id),
        ])
        self.assertTrue(
            reversal_moves,
            "Debe existir una Nota de Crédito que reversa la ND de IGTF tras desconciliar el pago.",
        )
        self.assertEqual(reversal_moves.state, "posted")
        self.assertFalse(
            debit_note.origin_payment_to_pay_igtf,
            "Tras la reversión, la ND ya no debe seguir vinculada al pago original.",
        )

    def test_usd_payment_direct_cancel_also_reverses_debit_note(self):
        """Cancelar el pago DIRECTO (botón 'Cancelar' del pago, sin pasar
        primero por 'Fijar a borrador') debe reversar la ND igual que la
        desconciliación manual -- cubre el fix de `action_cancel` en
        `l10n_ve_igtf` (antes solo `action_draft` disparaba
        `remove_igtf_from_account_move`, dejando la ND huérfana si el
        usuario cancelaba directo)."""
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            pay_form.amount = 1000.00
            pay_form.save()
        action = pay_form.record.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        debit_notes = invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(debit_notes), 1)
        debit_note = debit_notes[0]
        self.assertEqual(debit_note.state, "posted")

        # Cancelar DIRECTO -- sin llamar a action_draft() antes.
        payment.action_cancel()
        self.assertEqual(payment.state, "canceled")

        debit_note = self.env["account.move"].browse(debit_note.id)
        reversal_moves = self.env["account.move"].search([
            ("reversed_entry_id", "=", debit_note.id),
        ])
        self.assertTrue(
            reversal_moves,
            "Cancelar el pago directo también debe reversar la ND de IGTF con una Nota de Crédito.",
        )
        self.assertEqual(reversal_moves.state, "posted")
        self.assertFalse(debit_note.origin_payment_to_pay_igtf)
