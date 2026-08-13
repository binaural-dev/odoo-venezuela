from odoo import fields, models, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _prepare_exchange_difference_move_vals(
        self, amounts_list, company=None, exchange_date=None, **kwargs
    ):
        # Fallback: solo se alcanza a llegar aquí si la conciliación NO pasó
        # por nuestro `reconcile()` (ver más abajo) -- por ejemplo, ajustes
        # de diferencial entre líneas que no pertenecen a una factura de
        # cliente. En ese caso se deja el asiento genérico de Odoo, solo
        # etiquetado.
        res = super()._prepare_exchange_difference_move_vals(
            amounts_list, company=company, exchange_date=exchange_date, **kwargs
        )
        if not res:
            return res

        company = (self.move_id.company_id or company)[:1]
        if company.l10n_ve_exchange_use_nd_nc:
            res['move_values']['l10n_ve_exchange_diff_entry'] = True

        return res

    def reconcile(self):
        # Esto solo aplica cuando hay una factura de cliente
        # (out_invoice/out_refund) de por medio, cuya compañía usa el flujo
        # de ND/NC de diferencial cambiario. El residual que deja abierto
        # `no_exchange_difference=True` normalmente cae del lado del PAGO
        # (así concilia Odoo, no es un caso especial) -- no de la factura,
        # así que se revisan todas las líneas por cobrar de `self`, y la
        # ND/NC que se genere siempre se vincula a la factura encontrada,
        # sea cual sea la línea que terminó con el residual abierto.
        invoice_lines = self.filtered(
            lambda l: (
                l.account_type == 'asset_receivable'
                and l.move_id.move_type in ('out_invoice', 'out_refund')
                and l.company_id.l10n_ve_exchange_use_nd_nc
                # Sin esto, cualquier nota que sea en sí misma una
                # corrección de OTRO documento -- ya sea nuestra propia
                # ND/NC de diferencial, o la ND que crea automáticamente
                # `l10n_ve_igtf_note_debit` al pagar en USD por banco --
                # vuelve a entrar en este mismo `reconcile()` al conciliarse
                # contra el pago (también es un `out_invoice`/`out_refund`
                # de esta compañía). Si queda un remanente de redondeo
                # abierto, eso dispara OTRA ND/NC para la nota misma
                # (rechazada por `account.debit.note`: "ya vinculada a otra
                # nota"). Solo debe aplicar sobre la factura de origen real,
                # nunca sobre una nota/corrección ya derivada de otra.
                and not l.move_id.debit_origin_id
                and not l.move_id.reversed_entry_id
            )
        )
        if not invoice_lines:
            return super().reconcile()
        invoice_line = invoice_lines[:1]
        invoice = invoice_line.move_id
        # Ojo: `self` puede incluir también la línea del banco/caja del
        # pago, no solo la de cuenta por cobrar -- hay que filtrar
        # explícitamente, si no `payment_line` podría terminar siendo la
        # línea equivocada (rompe el cálculo de la tasa propia más abajo).
        payment_line = (self - invoice_lines).filtered(
            lambda l: l.account_type == 'asset_receivable'
        )[:1]
        payment = payment_line.move_id

        # `no_exchange_difference=True` es una llave de contexto YA provista
        # por Odoo (ver `account/models/account_move_line.py`,
        # `_prepare_reconciliation_single_partial`) para saltarse por
        # completo el cálculo/creación del asiento de diferencial -- Odoo
        # sigue calculando todo igual (montos, tasas, multi-moneda), solo
        # que el residual que hubiera cerrado ese asiento queda ABIERTO.
        # No se toca ni un poco la matemática de conciliación.
        res = super(AccountMoveLine, self.with_context(no_exchange_difference=True)).reconcile()

        # El monto EXACTO del diferencial NO es "lo que quede de residual"
        # en la factura o el pago -- si el pago es por un monto mucho mayor
        # (o menor) al de la factura, ese exceso/faltante queda como
        # residual también, pero NO es diferencial cambiario. Lo correcto
        # es tomar el `account.partial.reconcile` que Odoo acaba de crear
        # entre estas dos líneas: `debit_amount_currency`/`credit_amount_currency`
        # es el monto REALMENTE emparejado (nunca el residual total), y con
        # la tasa propia de cada línea (`balance / amount_currency`, fija
        # desde que se creó cada línea, sin importar lo que quede pendiente
        # después) se calcula la diferencia en VEF de esa porción
        # emparejada -- y nada más.
        residual = 0.0
        if (
            invoice_line.currency_id == payment_line.currency_id
            and not invoice_line.currency_id.is_zero(invoice_line.amount_currency)
            and not payment_line.currency_id.is_zero(payment_line.amount_currency)
        ):
            partial = self.env['account.partial.reconcile'].search([
                ('debit_move_id', 'in', (invoice_line + payment_line).ids),
                ('credit_move_id', 'in', (invoice_line + payment_line).ids),
            ], order='id desc', limit=1)
            if partial:
                matched_amount = abs(partial.debit_amount_currency)
                inv_rate = abs(invoice_line.balance) / abs(invoice_line.amount_currency)
                pay_rate = abs(payment_line.balance) / abs(payment_line.amount_currency)
                residual = invoice_line.company_currency_id.round(matched_amount * (inv_rate - pay_rate))

        if not invoice_line.company_currency_id.is_zero(residual):
            # No se llama directo: en este punto la pila de llamadas viene
            # muy profunda (todo el `write()`/`action_post()` del
            # pago/factura que disparó esta conciliación, con las cadenas
            # de `super()` de este proyecto encima) -- crear y postear la
            # ND/NC aquí mismo puede toparse con el límite de recursión de
            # Python en cualquier compute intermedio (ya confirmado en
            # varios puntos distintos, de módulos distintos). Se difiere
            # con un precommit hook (mismo mecanismo que usa `mail.thread`
            # para su propio post-procesamiento): Odoo lo ejecuta más
            # tarde, en el próximo flush de la transacción -- momento en
            # que la pila ya se desenrolló y volvió a un nivel normal.
            self.env.cr.precommit.add(
                lambda invoice_line=invoice_line, invoice=invoice, payment=payment, residual=residual: (
                    invoice_line._create_exchange_difference_note(invoice, payment, residual)
                )
            )

        return res

    def _create_exchange_difference_note(self, invoice, payment, residual):
        """Liquida el diferencial cambiario (monto exacto `residual`,
        capturado por `reconcile()` en el instante en que se detectó -- no
        se vuelve a leer `amount_residual` aquí, porque para cuando corre
        este precommit ya pudo haber cambiado por razones ajenas al
        diferencial: otra nota liquidando la misma línea del pago, o un
        pago por un monto mucho mayor al de esta factura) con una Nota de
        Crédito o Débito real vinculada a `invoice`, construida
        manualmente con `create()` (sin pasar por los asistentes
        `account.debit.note`/`account.move.reversal` -- mismo patrón que
        usa `l10n_ve_igtf_note_debit` para sus propias notas), conciliada
        de inmediato para cerrarla por completo:

        - Residual en DÉBITO ("falta" -- lo que se cobró, ya convertido,
          quedó corto): se emite una Nota de CRÉDITO por esa diferencia --
          su línea de cuenta por cobrar es un crédito, que cancela el
          débito pendiente -- conciliada contra la propia factura de
          origen (la que quedó abierta).
        - Residual en CRÉDITO ("sobra" -- ganancia): se emite una Nota de
          DÉBITO, conciliada contra el sobrante que quedó en el pago.
        """
        self.ensure_one()
        # El contexto en el que corre este precommit hereda `skip_invoice_sync=True`
        # de la conciliación original (ver `account.move._inverse_tax_totals`,
        # `account/models/account_move.py`: si esta llave ya está activa,
        # `_disable_recursion(..., 'skip_invoice_sync')` corta toda la
        # sincronización de líneas -- incluyendo el cálculo real de
        # `balance`/`debit`/`credit` de nuestras propias líneas nuevas, que
        # quedaban en 0 aun después de `action_post()`. Se limpia antes de
        # crear la ND/NC.
        self = self.with_context(skip_invoice_sync=False)
        company = self.company_id

        product = company.l10n_ve_exchange_note_product_id
        if not product:
            raise UserError(_(
                "Configure el 'Producto de Nota de Diferencial Cambiario' en "
                "Ajustes > Contabilidad antes de conciliar facturas en "
                "moneda extranjera con el modo de ND/NC de diferencial "
                "cambiario activado."
            ))

        # Débito pendiente (falta) -> Nota de Crédito (la cierra).
        # Crédito pendiente/sobrante (sobra) -> Nota de Débito (se concilia
        # contra ese sobrante).
        is_credit_note = company.currency_id.compare_amounts(residual, 0.0) > 0

        debit_journal = self.env['account.journal'].search([
            ('company_id', '=', company.id),
            ('is_debit', '=', True),
            ('type', '=', 'sale'),
        ], limit=1)
        journal = debit_journal or invoice.journal_id

        line_vals = {
            'product_id': product.id,
            'quantity': 1.0,
            'price_unit': abs(residual),
            'tax_ids': [(6, 0, product.taxes_id.ids)],
            'name': _('Diferencial cambiario (%s) s/ %s') % (
                _('pérdida') if is_credit_note else _('ganancia'), invoice.name,
            ),
        }
        today = fields.Date.context_today(self)

        if not is_credit_note:
            # Nota de Débito: construida directamente con `create()` --
            # `debit_origin_id` apuntando a la factura deja el mismo botón
            # inteligente que dejaría el asistente `account.debit.note`.
            note = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': invoice.partner_id.id,
                'invoice_date': today,
                'date': today,
                'currency_id': company.currency_id.id,
                'journal_id': journal.id,
                'debit_origin_id': invoice.id,
                'invoice_origin': invoice.name,
                'invoice_line_ids': [(0, 0, line_vals)],
                'l10n_ve_exchange_diff_entry': True,
                'l10n_ve_exchange_is_credit_note': False,
                'l10n_ve_exchange_invoice_id': invoice.id,
            })
            # `action_post()` con `move_action_post_alert=True`: sin esta
            # llave, `action_post()` en facturas/NC de cliente
            # (`l10n_ve_accountant`) devuelve una acción para abrir un
            # wizard de confirmación en vez de postear -- mismo patrón que
            # `l10n_ve_igtf_note_debit.prepare_igtf_payment_debit_note`.
            note.with_context(move_action_post_alert=True).action_post()

            # Línea de conciliación real del pago: mismo criterio que usa
            # `l10n_ve_igtf_note_debit.settle_igtf_debit_note` para ubicar
            # `outstanding_line`, adaptado -- IGTF busca residual en moneda
            # EXTRANJERA (el cliente pagó de más en USD, sin aplicar); acá
            # el monto en moneda extranjera ya calzó exacto, lo que queda
            # pendiente es el residual en moneda de COMPAÑÍA (VEF).
            outstanding_line = payment.line_ids.filtered(
                lambda l: l.account_id.account_type == 'asset_receivable'
                and not l.reconciled
                and not l.company_currency_id.is_zero(l.amount_residual)
            )[:1]
            if outstanding_line:
                note.with_context(no_exchange_difference=True).js_assign_outstanding_line(outstanding_line.id)
        else:
            # Nota de Crédito: construida directamente con `create()` --
            # `reversed_entry_id` apuntando a la factura deja el mismo botón
            # inteligente que dejaría el asistente `account.move.reversal`,
            # sin su comportamiento de revertir el 100% de las líneas
            # originales. Se crea ya desde cero por el monto exacto del
            # residual (con el contexto limpio de `skip_invoice_sync`, ver
            # arriba, para que la línea sincronice bien su balance).
            note = self.env['account.move'].create({
                'move_type': 'out_refund',
                'partner_id': invoice.partner_id.id,
                'invoice_date': today,
                'date': today,
                'currency_id': company.currency_id.id,
                'journal_id': journal.id,
                'reversed_entry_id': invoice.id,
                'invoice_origin': invoice.name,
                'invoice_line_ids': [(0, 0, line_vals)],
                'l10n_ve_exchange_diff_entry': True,
                'l10n_ve_exchange_is_credit_note': True,
                'l10n_ve_exchange_invoice_id': invoice.id,
            })
            # `action_post()` con `move_action_post_alert=True`: sin esta
            # llave, `action_post()` en facturas/NC de cliente
            # (`l10n_ve_accountant`) devuelve una acción para abrir un
            # wizard de confirmación en vez de postear -- mismo patrón que
            # la rama de Nota de Débito arriba.
            note.with_context(move_action_post_alert=True).action_post()

            # La Nota de Crédito se concilia contra la propia factura de
            # origen (la que quedó "falta"), no contra el pago.
            note_line = note.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
            invoice_line = invoice.line_ids.filtered(
                lambda l: l.account_type == 'asset_receivable' and not l.reconciled
            )
            if invoice_line:
                (note_line + invoice_line).with_context(no_exchange_difference=True).reconcile()

