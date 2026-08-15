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
        # Ojo: esto también corre cuando la línea que quedó con residual es
        # nuestra PROPIA ND/NC de diferencial, o la ND que crea
        # `l10n_ve_igtf_note_debit` al pagar en USD por banco (ambas quedan
        # excluidas de `invoice_lines` en `reconcile()` por tener
        # `debit_origin_id`/`reversed_entry_id`, así que caen aquí vía
        # `super().reconcile()` sin pasar por nuestra lógica) -- sin este
        # chequeo, el asiento genérico que Odoo arma para ESA reconciliación
        # quedaba igual etiquetado `l10n_ve_exchange_diff_entry=True`,
        # apareciendo como una segunda ND/NC "de negocio" fantasma para el
        # mismo partner. Se excluye SOLO ese caso puntual (nota/corrección
        # ya derivada de otro documento) -- cualquier otra cosa (incluida
        # una factura de PROVEEDOR, `liability_payable`, no
        # `asset_receivable`) sí debe quedar etiquetada como siempre, para
        # no perder el asiento genérico de esos casos (ver
        # `test_fallback_tags_generic_exchange_move_for_vendor_bill`).
        is_own_derived_note = self.filtered(
            lambda l: (
                l.move_id.move_type in ('out_invoice', 'out_refund')
                and (
                    l.move_id.debit_origin_id
                    or l.move_id.reversed_entry_id
                    or getattr(l.move_id, 'l10n_ve_igtf_note_debit_origin', False)
                )
            )
        )
        if company.l10n_ve_exchange_use_nd_nc and not is_own_derived_note:
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
                and not getattr(l.move_id, 'l10n_ve_igtf_note_debit_origin', False)
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
        # entre estas dos líneas: el monto REALMENTE emparejado (nunca el
        # residual total) de CADA lado, en SU PROPIA moneda -- NUNCA
        # asumiendo cuál campo (`debit_amount_currency`/`credit_amount_currency`)
        # corresponde a cuál línea, ya que si la factura está en moneda
        # extranjera (USD) y el pago se registró directo en moneda de
        # compañía (VEF, el caso típico de "pagar una factura en USD con
        # VEF"), cada campo queda en la moneda de SU propia línea, no en
        # una moneda común. `partial.amount` NO sirve para esto -- con
        # `no_exchange_difference=True` activo, Odoo lo calcula reflejando
        # la tasa de UN solo lado (se confirmó que siempre da
        # `matched_amount_factura * inv_rate`, igual a lo que la factura
        # necesitaba, jamás lo que el pago realmente cubrió) -- por eso hay
        # que recalcular el lado del PAGO también con su propia tasa fija
        # (`balance / amount_currency`, igual que la de la factura): si el
        # pago quedó en moneda de compañía (VEF), esa tasa es simplemente 1
        # y el monto emparejado del pago YA está en VEF, sin conversión.
        residual = 0.0
        # `payment_line` debe ser el lado del PAGO (banco/caja) de la
        # conciliación, nunca otra factura/NC de cliente -- si no se
        # exigiera esto, la propia conciliación que hace
        # `_create_exchange_difference_note()` al final para cerrar la
        # ND/NC contra `invoice_line` (rama de Nota de Crédito, ver más
        # abajo: `(note_line + invoice_line).reconcile()`) vuelve a entrar
        # AQUÍ MISMO -- `invoice_line` sigue calificando como factura real
        # (no tiene `debit_origin_id`/`reversed_entry_id`), y `note_line`
        # terminaría tratado como si fuera el pago, generando una SEGUNDA
        # ND/NC fantasma para la misma factura. Antes esto quedaba
        # bloqueado por casualidad (la nota se crea en moneda de compañía,
        # `invoice_line` casi siempre en moneda extranjera -- monedas
        # distintas), pero ya no se puede depender de eso ahora que el
        # cálculo soporta monedas distintas a propósito.
        if (
            payment_line
            and payment.move_type not in ('out_invoice', 'out_refund')
            and not invoice_line.currency_id.is_zero(invoice_line.amount_currency)
            and not payment_line.currency_id.is_zero(payment_line.amount_currency)
        ):
            partial = self.env['account.partial.reconcile'].search([
                ('debit_move_id', 'in', (invoice_line + payment_line).ids),
                ('credit_move_id', 'in', (invoice_line + payment_line).ids),
            ], order='id desc', limit=1)
            if partial:
                if partial.debit_move_id == invoice_line:
                    invoice_matched = abs(partial.debit_amount_currency)
                    payment_matched = abs(partial.credit_amount_currency)
                else:
                    invoice_matched = abs(partial.credit_amount_currency)
                    payment_matched = abs(partial.debit_amount_currency)
                inv_rate = abs(invoice_line.balance) / abs(invoice_line.amount_currency)
                pay_rate = abs(payment_line.balance) / abs(payment_line.amount_currency)
                residual = invoice_line.company_currency_id.round(
                    invoice_matched * inv_rate - payment_matched * pay_rate
                )

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
        #
        # `active_model`/`active_id` heredados del contexto ambiental de la
        # acción que disparó esta reconciliación (ej. el wizard "Registrar
        # Pago") también hay que limpiarlos: este precommit corre en medio
        # del `write()`/`action_post()` de ESA acción, así que el `env` de
        # aquí sigue arrastrando esas llaves -- y `l10n_ve_accountant`
        # (`_get_tax_totals_summary`) las usa a ciegas (`self.env[active_model]
        # .browse(active_id)`, sin `exists()`) para decidir de qué
        # `record` calcular los totales de impuesto al postear la ND/NC.
        # Si para este punto ese registro (ej. la línea de la factura/pago
        # original) ya cambió de identidad por la propia conciliación,
        # `record.company_id` revienta con `MissingError` al postear
        # NUESTRA nota. La ND/NC es un documento propio, nuevo -- no debe
        # heredar el `active_id` de otra acción; se limpia para que ese
        # método caiga a su propio fallback (deducir el `record` desde
        # `base_lines`, ver `l10n_ve_accountant/models/account_tax.py`).
        self = self.with_context(skip_invoice_sync=False, active_model=False, active_id=False)
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
            'name': _(
                'Diferencial cambiario (%(concept)s) s/ %(invoice)s',
                concept=_('pérdida') if is_credit_note else _('ganancia'),
                invoice=invoice.name,
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

            # Nota de Débito: `move_type='out_invoice'`, no `out_refund`/
            # `in_refund`, así que `_validate_refund_lines_against_origin()`
            # (módulo en desarrollo, ver nota en la rama de Nota de Crédito
            # más abajo) no le aplica -- no hace falta el contexto aquí.

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
            # `l10n_ve_skip_refund_origin_validation`: esta NC es
            # `reversed_entry_id` -> factura real, pero su única línea es
            # el producto dedicado de diferencial cambiario -- nunca un
            # producto de la factura original -- así que NO debe pasar por
            # `_validate_refund_lines_against_origin()` (módulo de
            # validación de líneas de refund contra su origen, en
            # desarrollo en otro PR, que corre sobre cualquier NC/ND con
            # `reversed_entry_id`). Ese módulo no puede depender de este ni
            # viceversa, así que se coordina con esta llave de contexto en
            # vez de un campo persistido.
            note = self.env['account.move'].with_context(
                l10n_ve_skip_refund_origin_validation=True,
            ).create({
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
            # la rama de Nota de Débito arriba. Se mantiene también
            # `l10n_ve_skip_refund_origin_validation`, por si esa
            # validación corre en `action_post()`/`write()` y no solo en
            # `create()`.
            note.with_context(
                move_action_post_alert=True,
                l10n_ve_skip_refund_origin_validation=True,
            ).action_post()

            # La Nota de Crédito se concilia contra la propia factura de
            # origen (la que quedó "falta"), no contra el pago.
            note_line = note.line_ids.filtered(lambda l: l.account_type == 'asset_receivable')
            invoice_line = invoice.line_ids.filtered(
                lambda l: l.account_type == 'asset_receivable' and not l.reconciled
            )
            if invoice_line:
                (note_line + invoice_line).with_context(no_exchange_difference=True).reconcile()

