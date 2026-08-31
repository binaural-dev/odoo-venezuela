from odoo import api, fields, models


class AccountPaymentRegisterIgtfNoteDebit(models.TransientModel):
    _inherit = "account.payment.register"

   
    igtf_note_debit_include_in_payment = fields.Boolean(
        string="Include IGTF in Amount",
        default=lambda self: self.env.company.igtf_note_debit_include_in_payment_default,
    )

    igtf_note_debit_mode = fields.Selection(related="company_id.igtf_note_debit_mode")

    # Bandera interna (no expuesta en la vista): marca que el próximo write
    # de `amount` viene de nuestro propio recompute al destildar el
    # checkbox, no de una edición manual del usuario. Un campo real del
    # wizard (a diferencia de `self.env.context`) sí sobrevive el ciclo de
    # onchange de Odoo (que puede re-evaluar `_onchange_amount` en una
    # iteración posterior tras nuestro propio write) -- ver
    # `_onchange_igtf_note_debit_include_in_payment` y `_onchange_amount`.
    igtf_note_debit_internal_amount_write = fields.Boolean(default=False, copy=False)

    total_amount_with_igtf_note_debit = fields.Monetary(
        string="Total to Pay (payment + IGTF Debit Note)",
        compute="_compute_total_amount_with_igtf_note_debit",
        currency_field="currency_id",
    )

    # NOTA: `@api.depends` se resuelve a partir del método FINAL de la MRO
    # (Odoo no acumula los decoradores de las clases padre) -- hay que
    # copiar aquí la lista COMPLETA de dependencias que usa
    # `l10n_ve_igtf/wizard/account_payment_register.py::_compute_amount`,
    # sin quitar ninguna, y solo añadir el campo nuevo.
    @api.depends(
        'can_edit_wizard', 'source_amount', 'source_amount_currency', 'source_currency_id',
        'company_id', 'currency_id', 'payment_date', 'installments_mode', 'is_igtf',
        'custom_user_amount', 'payment_difference_handling',
        'igtf_note_debit_include_in_payment',
    )
    def _compute_amount(self):
        super()._compute_amount()
        for wizard in self:
            # Si el usuario ya escribió a mano el monto a pagar
            # (`custom_user_amount`), con 'Incluir IGTF en el pago'
            # desmarcado ese monto YA es el importe puro de la factura (sin
            # IGTF) -- no hay que restarle nada. `amount_without_difference`
            # en ese caso viene mal calculada desde `l10n_ve_igtf` (asume
            # que el monto tecleado incluye el IGTF embebido, semántica del
            # flujo 'inline').
            #
            # Este método es un COMPUTE (no un onchange): se re-dispara con
            # CUALQUIER cambio en sus `@api.depends`, así que la corrección
            # de abajo tiene que aplicarse EN CADA recompute, no una sola
            # vez -- por eso vive acá y no en un onchange separado (un
            # onchange del checkbox por sí solo NO sobrevive al siguiente
            # recompute de este método, que volvería a poner `amount` en
            # el valor "natural" con IGTF incluido).
            if not (
                wizard.igtf_note_debit_mode == "debit_note"
                and wizard.is_igtf
                and not wizard.igtf_note_debit_include_in_payment
                and not wizard.custom_user_amount
            ):
                continue
            # Marcar el flag ANTES de escribir `amount`: distingue esta
            # reescritura interna (recompute automático) de una edición
            # manual real del usuario -- ver `_onchange_amount` abajo, que
            # reacciona a este mismo write dentro del mismo ciclo de
            # onchange de Odoo (confirmado: `web/models/models.py`, el
            # bucle `while todo` de `onchange()` reprocesa 'amount' como
            # campo recién cambiado, en la MISMA llamada, no en una
            # petición aparte).
            wizard.igtf_note_debit_internal_amount_write = True
            wizard.amount = wizard.amount_without_difference
            wizard.last_computed_amount = wizard.amount

    # Ver nota en `_compute_amount` sobre por qué hace falta esta bandera:
    # el write de `amount` de arriba retrigger este `_onchange_amount`
    # (heredado, reacciona a 'amount') dentro del mismo ciclo de onchange.
    # Sin la bandera, `l10n_ve_igtf::_onchange_amount` compararía el monto
    # ya recalculado (SIN IGTF) contra el total CON IGTF, concluiría
    # erróneamente que hubo una edición manual, y pisaría
    # `custom_user_amount`/`amount_without_difference`. Se bypasea SOLO
    # cuando la bandera indica que el write vino de nuestro propio
    # recompute -- cualquier otro cambio de `amount` (ej. un pago parcial
    # tecleado a mano sobre una sola factura) sigue yendo a `super()` sin
    # alterar, preservando la detección normal de edición manual.
    # NOTA: el trigger es SOLO 'amount'/'payment_date' (igual que la base) --
    # 'igtf_note_debit_include_in_payment' NO debe estar acá. Si lo estuviera,
    # Odoo invoca este método una SEGUNDA vez en el mismo ciclo de onchange
    # (una vez por 'amount' cambiado -- bypass correcto vía el flag -- y otra
    # vez por el checkbox cambiado, YA con el flag reseteado por la primera
    # invocación, cayendo en `super()` y corrompiendo `custom_user_amount`
    # de nuevo). Confirmado empíricamente: con el trigger duplicado, el
    # segundo llamado siempre llega con flag=False aunque `amount` no haya
    # cambiado desde la primera invocación.
    @api.onchange("amount", "payment_date")
    def _onchange_amount(self):
        # `_onchange_amount` está registrado también bajo el trigger
        # 'payment_date' -- cuando el usuario cambia `payment_date` (con el
        # checkbox ya desmarcado y `amount` ya en su valor "sin IGTF"),
        # Odoo invoca ESTE método directamente, ANTES de que el recompute
        # perezoso de `amount` (disparado por `_compute_amount`, que
        # también depende de `payment_date`) haya corrido -- confirmado
        # contra `web/models/models.py::_apply_onchange_methods`. Si se lee
        # la bandera en ese punto, todavía tiene su valor previo (False),
        # el bypass no aplica, se llama a `super()` con el monto viejo, y
        # RECIÉN DESPUÉS el recompute de `amount` pone la bandera en True
        # -- demasiado tarde, ya se corrompió `custom_user_amount`. Forzar
        # aquí la lectura de `amount` obliga a que `_compute_amount` (y su
        # escritura de la bandera) corra ANTES de decidir el bypass.
        for wizard in self:
            # Fuerza el recompute perezoso de `amount` antes de leer la
            # bandera (ver nota arriba); la asignación a `_` evita el
            # falso positivo de pylint "pointless-statement" que dispara
            # una lectura de atributo sin usar su valor.
            _ = wizard.amount
        bypass_recs = self.filtered("igtf_note_debit_internal_amount_write")
        other_recs = self - bypass_recs
        if other_recs:
            super(AccountPaymentRegisterIgtfNoteDebit, other_recs)._onchange_amount()
        for wizard in bypass_recs:
            wizard.igtf_note_debit_internal_amount_write = False
            wizard.last_computed_amount = wizard.amount

    @api.depends("amount", "igtf_to_show", "igtf_note_debit_include_in_payment", "is_igtf", "igtf_note_debit_mode")
    def _compute_total_amount_with_igtf_note_debit(self):
        for wizard in self:
            if (
                wizard.igtf_note_debit_mode == "debit_note"
                and wizard.is_igtf
                and not wizard.igtf_note_debit_include_in_payment
            ):
                wizard.total_amount_with_igtf_note_debit = wizard.amount + wizard.igtf_to_show
            else:
                wizard.total_amount_with_igtf_note_debit = wizard.amount

    # Ver nota equivalente en `_compute_amount` sobre por qué hace falta
    # copiar la lista COMPLETA de dependencias del override base.
    @api.depends(
        'can_edit_wizard', 'amount', 'installments_mode', 'is_igtf', 'amount_without_difference',
        'igtf_note_debit_include_in_payment',
    )
    def _compute_payment_difference(self):

        super()._compute_payment_difference()
        for wizard in self:
            if not (
                wizard.igtf_note_debit_mode == "debit_note"
                and wizard.is_igtf
                and not wizard.igtf_note_debit_include_in_payment
                and wizard.payment_date
            ):
                continue
            total_amount_values = wizard._get_total_amounts_to_pay(wizard.batches)
            efective_amount = abs(wizard.amount)
            if wizard.installments_mode == "full":
                wizard.payment_difference = total_amount_values["full_amount_for_difference"] - efective_amount
            else:
                wizard.payment_difference = total_amount_values["amount_for_difference"] - efective_amount

    def _check_igtf_note_debit_group_payment(self):
        # `self.is_igtf` ya encapsula diario IGTF + partner aplicable +
        # moneda + `debit_origin_id` (`l10n_ve_igtf::_compute_check_igtf`) --
        # sin este chequeo, CUALQUIER pago agrupado multi-factura quedaba
        # bloqueado en compañías con el modo activado, aunque las facturas
        # no aplicaran IGTF (ej. pago en VEF, partner exento), contradiciendo
        # el propio mensaje de error de abajo y lo documentado en el README/spec.
        if (
            self.company_id.igtf_note_debit_mode != "debit_note"
            or not self.group_payment
            or not self.is_igtf
        ):
            return
        invoices = self.get_moves()
        if isinstance(invoices, set):
            invoices = sum(invoices, self.env["account.move"])
        if len(invoices) > 1:
            raise UserError(_(
                "'Group Payments' cannot be used when the 'IGTF Perception "
                "Mode' is 'Automatic Fiscal Debit Note': each invoice paid "
                "through an IGTF journal must generate its own Debit Note. "
                "Uncheck 'Group Payments' and register the payment for each "
                "invoice separately."
            ))

    def _create_payments(self):
        self._check_igtf_note_debit_group_payment()

        payments = super()._create_payments()

        if self.company_id.igtf_note_debit_mode != "debit_note":
            return payments

     
        invoices = self.get_moves()
        if isinstance(invoices, set):
            invoices = sum(invoices, self.env["account.move"])
        if not invoices:
            return payments

        for payment in payments:
            if not payment.igtf_amount or payment.igtf_amount <= 0.0:
                continue

            # Cada `payment` puede corresponder a una factura distinta
            # (pago sin agrupar de varias facturas a la vez) -- se usa la
            # factura realmente conciliada por ESTE pago cuando hay más de
            # una factura en el batch; con una sola, se conserva el mismo
            # comportamiento de siempre (evita depender de que
            # `reconciled_invoice_ids` ya esté actualizado en este punto).
            invoice = invoices[:1]
            if len(invoices) > 1:
                invoice = payment.reconciled_invoice_ids[:1] or invoice
            if not invoice:
                continue

            company_currency = payment.company_id.currency_id
            reconcilable_lines = payment.move_id.line_ids.filtered(
                lambda l: l.account_type in ("asset_receivable", "liability_payable")
            )
            
            payment_total_base = payment.move_id.amount_total_signed
            payment_residual_base = reconcilable_lines.amount_residual

            # `payment.igtf_amount` (calculado por la base con
            # `indexed_default`) respeta si el pago es indexado o no, pero
            # está en la moneda del PAGO -- la conversión a moneda de
            # compañía para la ND debe usar la MISMA fecha que se usó para
            # calcular ese monto (fecha del pago si es indexado, fecha de
            # la factura si no), o se reintroduce la tasa "equivocada" en
            # este último paso aunque el cálculo previo haya sido correcto.
            conversion_date = payment.date if self.indexed_default else invoice.invoice_date
            igtf_amount_company_curr = payment.currency_id._convert(
                payment.igtf_amount, company_currency, payment.company_id, conversion_date,
            )
         
            if abs(payment_residual_base) > 0:
                supposed_invoice_amount = payment.currency_id.round(
                    abs(payment_total_base) - abs(igtf_amount_company_curr)
                )
                # Solo se sustituye el IGTF calculado por el residual del
                # pago cuando el pago cubre EXACTAMENTE el total de la
                # factura (comparación con tolerancia real de la moneda,
                # no una constante mágica). Con `<= 0.1` sin `abs()` en la
                # resta, un pago PARCIAL (donde `supposed_invoice_amount <
                # invoice.amount_total_signed`) también entraba aquí y se
                # sustituía el IGTF por el residual completo del pago --
                # monto incorrecto en la ND para el escenario más común.
                if invoice.currency_id.compare_amounts(
                    abs(supposed_invoice_amount), abs(invoice.amount_total_signed)
                ) == 0:
                    igtf_amount_company_curr = abs(payment_residual_base)

            debit_note = invoice.prepare_igtf_payment_debit_note(
                igtf_amount_company_curr, invoice, payment,
            )

            outstanding_line = reconcilable_lines.filtered(
                lambda l: not l.reconciled and abs(l.amount_residual) > 0.01
            )[:1]
            invoice.settle_igtf_debit_note(
                debit_note, payment,
                include_in_payment=self.igtf_note_debit_include_in_payment,
                outstanding_line=outstanding_line,
            )

        return payments
