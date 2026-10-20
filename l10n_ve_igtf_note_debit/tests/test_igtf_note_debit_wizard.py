from odoo.tests import tagged, Form
from odoo.tools import float_compare
from odoo import fields
from odoo.exceptions import UserError

from odoo.addons.l10n_ve_igtf.tests.test_igtf_common_partner_formal_VEF import IGTFTestCommon


@tagged("igtf_note_debit", "-at_install", "post_install")
class TestIgtfNoteDebitWizard(IGTFTestCommon):
    """Cobertura de las ramas restantes de `account.payment.register`
    (wizard) y del passthrough de `account.payment` en modo 'inline'."""

    def setUp(self):
        super().setUp()

        self.igtf_note_debit_product = self.env["product.product"].create({
            "name": "Percepción de IGTF (ND wizard test)",
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
            "name": "ND Forma Libre (wizard test)",
            "code": "NDFLW",
            "type": "sale",
            "is_debit": True,
            "company_id": self.company.id,
        })

    def test_inline_mode_payment_uses_legacy_embedded_igtf_line(self):
        """Con el modo 'inline' (default de la compañía), el wizard y
        `account.payment._create_igtf_moves_in_payments` deben delegar
        siempre a `super()` -- comportamiento legado intacto."""
        self.assertEqual(self.company.igtf_note_debit_mode, "inline")

        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.save()
            pay_form.amount = 600.00
            pay_form.save()
        action = pay_form.record.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.assertEqual(payment.state, "paid")
        # Flujo legado: la línea de IGTF va embebida en el propio asiento.
        self.assertTrue(
            payment.move_id.line_ids.filtered(
                lambda l: l.account_id in (self.acc_igtf_cli, self.acc_igtf_prov)
            ),
            "En modo 'inline' el IGTF debe seguir viniendo embebido en el asiento del pago.",
        )
        self.assertFalse(invoice.debit_note_ids)

    def _activate_debit_note_mode(self):
        self.company.write({
            "igtf_note_debit_mode": "debit_note",
            "igtf_note_debit_product_id": self.igtf_note_debit_product.id,
        })

    def test_toggle_checkbox_without_manual_amount_recomputes_amount(self):
        """Si el usuario NO edita `amount` a mano, desmarcar 'Incluir IGTF
        en el Importe' sí debe recalcular el monto (a partir del saldo de
        la factura, sin IGTF) -- a diferencia del caso donde el usuario ya
        había tecleado un monto manual (ver test de multicurrency)."""
        self._activate_debit_note_mode()
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.save()
            # No se toca `amount` -- sigue en su valor por defecto (full
            # amount con IGTF incluido, dado que el checkbox arranca True).
            pay_form.igtf_note_debit_include_in_payment = False

        wizard = pay_form.record
        self.assertEqual(
            float_compare(wizard.amount, wizard.amount_without_difference, precision_digits=2), 0,
            "Sin edición manual, el monto debe recalcularse al desmarcar el checkbox.",
        )

    def test_partial_payment_with_separate_vef_mode_computes_payment_difference(self):
        """Pago PARCIAL (no de contado) con 'Incluir IGTF en el pago'
        desmarcado -- ejercita la rama de `_compute_payment_difference`
        para `installments_mode != 'full'`."""
        self._activate_debit_note_mode()
        self.company.write({"igtf_note_debit_vef_journal_id": self.bank_journal_bs.id})

        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        with Form.from_action(self.env, invoice.action_register_payment()) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.save()
            pay_form.amount = 400.00
            pay_form.save()
            pay_form.igtf_note_debit_include_in_payment = False

        wizard = pay_form.record
        # No debe reventar -- el compute debe resolver un valor numérico
        # tanto si el monto coincide con una cuota (`installments_mode !=
        # 'full'`) como si no (fallback a 'full').
        self.assertIsInstance(wizard.payment_difference, float)

        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))
        self.assertEqual(payment.state, "paid")
        self.assertEqual(
            float_compare(payment.amount, 400.00, precision_digits=2), 0,
        )

    def _create_two_usd_invoices(self):
        invoices = self.env["account.move"]
        for _ in range(2):
            invoice = self._create_invoice_usd(1000.00)
            invoice.with_context(move_action_post_alert=True).action_post()
            invoices |= invoice
        return invoices

    def test_multi_invoice_payment_ungrouped_generates_debit_note_per_invoice(self):
        """Pago SIN agrupar de VARIAS facturas a la vez (un `account.payment`
        distinto por factura, `group_payment=False`) -- cada factura debe
        recibir su propia ND, atribuida al pago que realmente la cubrió."""
        self._activate_debit_note_mode()
        invoices = self._create_two_usd_invoices()

        lines_to_pay = invoices.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and not l.reconciled
        )
        action = lines_to_pay.action_register_payment()
        ctx = dict(action["context"], active_model="account.move.line", active_ids=lines_to_pay.ids)

        with Form(self.env["account.payment.register"].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            pay_form.group_payment = False
            pay_form.save()

        wizard = pay_form.record
        action = wizard.action_create_payments()
        payments = self.env["account.payment"].search(action.get("domain", []))
        self.assertEqual(len(payments), 2, "Sin agrupar, debe crearse un pago por factura.")

        for invoice in invoices:
            debit_notes = invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin)
            self.assertEqual(
                len(debit_notes), 1,
                f"Cada factura del pago sin agrupar debe tener su propia ND (factura {invoice.name}).",
            )
            self.assertEqual(invoice.payment_state, "paid")
            # Cada ND debe estar atribuida al pago real que cubrió ESA
            # factura (no siempre la primera del batch).
            own_payment = payments.filtered(lambda p: invoice in p.reconciled_invoice_ids)
            self.assertEqual(debit_notes.origin_payment_to_pay_igtf, own_payment.move_id)

    def test_multi_invoice_payment_grouped_is_blocked_in_debit_note_mode(self):
        """Pago AGRUPADO de varias facturas (`group_payment=True`, un solo
        `account.payment` cubriendo ambas) no está soportado en modo ND: no
        hay forma correcta de atribuir el documento fiscal a una sola
        factura cuando el IGTF corresponde a varias. Debe bloquearse con un
        error claro en vez de generar una ND mal atribuida."""
        self._activate_debit_note_mode()
        invoices = self._create_two_usd_invoices()

        lines_to_pay = invoices.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
            and not l.reconciled
        )
        action = lines_to_pay.action_register_payment()
        ctx = dict(action["context"], active_model="account.move.line", active_ids=lines_to_pay.ids)

        with Form(self.env["account.payment.register"].with_context(ctx)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.save()
            pay_form.group_payment = True
            pay_form.save()

        wizard = pay_form.record
        with self.assertRaises(UserError):
            wizard.action_create_payments()

        for invoice in invoices:
            self.assertFalse(
                invoice.debit_note_ids.filtered(lambda dn: dn.l10n_ve_igtf_note_debit_origin),
                "No debe quedar ninguna ND generada tras el bloqueo.",
            )

    def test_bi_igtf_values_match_generated_debit_note(self):
        """`compute_bi_igtf` en modo `debit_note` debe reflejar la ND real
        generada -- no basta con que los campos sean `>= 0`, deben calzar
        numéricamente contra el monto efectivo de la ND y de la factura."""
        self._activate_debit_note_mode()
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
        payment = self.env["account.payment"].browse(
            pay_form.record.action_create_payments().get("res_id")
        )
        invoice.invalidate_recordset()

        dn = invoice.debit_note_ids.filtered(lambda d: d.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(dn), 1)
        self.assertEqual(payment.state, "paid")

        # `amount_total_signed` ya viene en moneda de COMPAÑÍA (VEF) --
        # `amount_total` es el que está en la moneda de la factura (USD).
        expected_bi_igtf = abs(invoice.amount_total_signed)

        # `foreign_bi_igtf`: base imponible en la moneda de la FACTURA --
        # debe ser el monto total facturado (pago de contado, sin residual).
        self.assertEqual(
            float_compare(invoice.foreign_bi_igtf, abs(invoice.amount_total), precision_digits=2), 0,
            "foreign_bi_igtf debe ser el monto total de la factura en su propia moneda.",
        )
        # `bi_igtf`: la misma base, en moneda de compañía (VEF).
        self.assertEqual(
            float_compare(invoice.bi_igtf, expected_bi_igtf, precision_digits=2), 0,
            "bi_igtf debe ser la base imponible en moneda de compañía.",
        )
        # `alter_bi_igtf` ("IGTF Apply"): el monto de IGTF efectivamente
        # cobrado -- debe calzar con el total de la ND generada (ambos en
        # moneda de compañía).
        self.assertEqual(
            float_compare(invoice.alter_bi_igtf, abs(dn.amount_total_signed), precision_digits=2), 0,
            "alter_bi_igtf debe calzar con el monto de la Nota de Débito de IGTF generada.",
        )
        # `igtf_top_aply`: el tope de IGTF (base * alícuota) -- debe
        # coincidir con el IGTF realmente cobrado en este escenario de
        # contado sin residual.
        expected_igtf = expected_bi_igtf * (self.company.igtf_percentage / 100)
        self.assertEqual(
            float_compare(invoice.igtf_top_aply, expected_igtf, precision_digits=2), 0,
            "igtf_top_aply debe coincidir con base_imponible * alicuota_igtf.",
        )

    def test_bi_igtf_values_partial_payment(self):
        """Pago PARCIAL (400 de una factura de 1000 USD, IGTF incluido en
        el pago -- estado por defecto del checkbox) -- `bi_igtf` y
        `foreign_bi_igtf` deben reflejar solo la porción efectivamente
        pagada, no el total facturado, y la ND no debe superar el IGTF
        correspondiente a esa porción.

        Nota: con "Incluir IGTF en el pago" DESMARCADO, el wizard no
        admite editar `amount` a un valor parcial de forma confiable (el
        monto se recalcula automáticamente a partir del saldo pendiente
        -- ver el comentario en `_onchange_amount` de
        `l10n_ve_igtf_note_debit/wizard/account_payment_register.py`);
        por eso este escenario se ejercita con el checkbox en su estado
        por defecto (marcado)."""
        self._activate_debit_note_mode()
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.amount = 400.00
        payment = self.env["account.payment"].browse(
            pay_form.record.action_create_payments().get("res_id")
        )
        invoice.invalidate_recordset()

        dn = invoice.debit_note_ids.filtered(lambda d: d.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(dn), 1)
        # `payment.state` refleja el estado del PAGO en sí (posted/paid una
        # vez contabilizado), no si la FACTURA quedó saldada -- eso lo
        # indica `invoice.payment_state`.
        self.assertEqual(
            invoice.payment_state, "partial",
            "Con un pago de 400 sobre una factura de 1000 (+ IGTF), la factura debe quedar en estado 'partial'.",
        )

        # Invariantes (sin exigir un valor exacto, dado que con el
        # checkbox marcado el monto de 400 combina factura + IGTF y su
        # desglose interno no es trivial de replicar aquí): la base
        # imponible pagada no puede exceder ni el monto pagado ni el total
        # de la factura, y la ND no puede exceder el IGTF que
        # correspondería al total facturado.
        self.assertLessEqual(
            invoice.foreign_bi_igtf, 400.00 + 1e-2,
            "Con pago parcial, foreign_bi_igtf no puede superar el monto pagado.",
        )
        self.assertLess(
            invoice.foreign_bi_igtf, abs(invoice.amount_total) - 1e-2,
            "Con pago parcial, foreign_bi_igtf debe ser estrictamente menor al total de la factura.",
        )
        max_igtf = abs(invoice.amount_total_signed) * (self.company.igtf_percentage / 100)
        self.assertLessEqual(
            abs(dn.amount_total_signed), max_igtf + 1e-2,
            "La ND de IGTF no puede superar el 3% del total de la factura, aun en pago parcial.",
        )
        self.assertEqual(
            float_compare(invoice.alter_bi_igtf, abs(dn.amount_total_signed), precision_digits=2), 0,
            "alter_bi_igtf debe calzar con la ND generada aun en pago parcial.",
        )

    def test_bi_igtf_values_different_dates_uses_payment_date_rate(self):
        """Factura fechada AYER (tasa 380.0) pagada HOY (tasa 390.2944).

        Comportamiento verificado empíricamente (correcto, no un bug): la ND
        de IGTF (`dn.amount_total_signed`) SÍ usa la tasa del PAGO (hoy) --
        `indexed_default=True` por defecto. `bi_igtf`, en cambio, toma el
        monto ya asentado por la conciliación (moneda de compañía), que
        refleja la tasa con la que la FACTURA quedó contabilizada (ayer) --
        no se re-convierte a la tasa del pago. El diferencial cambiario
        entre ambas tasas es responsabilidad de `l10n_ve_exchange_difference`,
        no de `bi_igtf`. Este test documenta esa separación de
        responsabilidades para que no se confunda con un bug en el futuro.
        """
        self._activate_debit_note_mode()
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice = self._create_invoice_usd(1000.00, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()
        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
        payment = self.env["account.payment"].browse(
            pay_form.record.action_create_payments().get("res_id")
        )
        invoice.invalidate_recordset()

        dn = invoice.debit_note_ids.filtered(lambda d: d.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(dn), 1)

        expected_bi_igtf_yesterday_rate = 1000.00 * 380.0000
        expected_igtf_today_rate = (1000.00 * self.rate) * (self.company.igtf_percentage / 100)
        self.assertNotEqual(
            float_compare(1000.00 * self.rate, expected_bi_igtf_yesterday_rate, precision_digits=2), 0,
            "Las tasas de hoy y ayer configuradas en el setUp deben ser distintas -- si no, este test no prueba nada.",
        )
        self.assertEqual(
            float_compare(invoice.bi_igtf, expected_bi_igtf_yesterday_rate, precision_digits=2), 0,
            "bi_igtf debe reflejar la tasa con la que la FACTURA quedó asentada (ayer), no la del pago.",
        )
        self.assertEqual(
            float_compare(dn.amount_total_signed, expected_igtf_today_rate, precision_digits=2), 0,
            "El monto de la ND debe calcularse con la tasa del PAGO (hoy), independiente de bi_igtf.",
        )

    def test_bi_igtf_values_non_indexed_payment_uses_invoice_date_rate(self):
        """Misma factura de AYER pagada HOY, pero con la compañía en modo
        de indexación 'not_indexed' -- el IGTF de la ND debe calcularse con
        la tasa de la FACTURA (ayer), no la del pago (hoy).

        Nota: `indexed_default` en el wizard es de solo lectura salvo que
        `company.indexaxion_payment_mode == 'to_agreed'` (ver
        `l10n_ve_accountant/wizard/account_payment_register.xml`) -- por
        eso se fija `company.indexed_default` directamente en vez de
        editar el campo del wizard."""
        self._activate_debit_note_mode()
        self.company.indexed_default = False
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice = self._create_invoice_usd(1000.00, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()
        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
        payment = self.env["account.payment"].browse(
            pay_form.record.action_create_payments().get("res_id")
        )
        invoice.invalidate_recordset()

        dn = invoice.debit_note_ids.filtered(lambda d: d.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(dn), 1)

        expected_igtf_yesterday_rate = 1000.00 * 380.0000 * (self.company.igtf_percentage / 100)
        self.assertEqual(
            float_compare(dn.amount_total_signed, expected_igtf_yesterday_rate, precision_digits=2), 0,
            "Con indexed_default=False, la ND de IGTF debe calcularse con la tasa de la FACTURA (ayer), no la del pago (hoy).",
        )

    def test_bi_igtf_values_overpayment_caps_at_invoice_total(self):
        """Pago MAYOR a lo adeudado (factura + IGTF) -- `bi_igtf` y
        `foreign_bi_igtf` no deben inflarse más allá del total facturado; el
        excedente es un sobrepago que queda como saldo a favor del cliente,
        no como más "base imponible" de IGTF."""
        self._activate_debit_note_mode()
        invoice = self._create_invoice_usd(1000.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            # Adeudado + IGTF (3%) = 1030.00 -- se paga de más.
            pay_form.amount = 1200.00
        payment = self.env["account.payment"].browse(
            pay_form.record.action_create_payments().get("res_id")
        )
        invoice.invalidate_recordset()

        dn = invoice.debit_note_ids.filtered(lambda d: d.l10n_ve_igtf_note_debit_origin)
        self.assertEqual(len(dn), 1)
        self.assertEqual(invoice.payment_state, "paid")

        expected_bi_igtf = abs(invoice.amount_total_signed)
        expected_foreign_bi_igtf = abs(invoice.amount_total)
        self.assertEqual(
            float_compare(invoice.bi_igtf, expected_bi_igtf, precision_digits=2), 0,
            "Con sobrepago, bi_igtf no debe superar el total de la factura en moneda de compañía.",
        )
        self.assertEqual(
            float_compare(invoice.foreign_bi_igtf, expected_foreign_bi_igtf, precision_digits=2), 0,
            "Con sobrepago, foreign_bi_igtf no debe superar el total de la factura en su propia moneda.",
        )
        # La ND se emite solo por el IGTF correspondiente a lo adeudado
        # (3% de 1000), no sobre el monto total pagado (1200).
        expected_igtf = expected_bi_igtf * (self.company.igtf_percentage / 100)
        self.assertEqual(
            float_compare(dn.amount_total_signed, expected_igtf, precision_digits=2), 0,
            "El sobrepago no debe inflar el monto de la Nota de Débito de IGTF.",
        )
