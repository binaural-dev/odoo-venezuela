import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    origin_payment_to_pay_igtf = fields.Many2one('account.move', string="Origin Payment to Pay IGTF",copy=False)

    has_pending_igtf_debit_note = fields.Boolean(
        compute='_compute_has_pending_igtf_debit_note',
        store=False
    )

    @api.depends('debit_note_ids', 'debit_note_ids.state', 'debit_note_ids.payment_state', 'amount_residual')
    def _compute_has_pending_igtf_debit_note(self):
        for move in self:
            move.has_pending_igtf_debit_note = False
            product = move.company_id.igtf_note_debit_product_id
            if move.debit_note_ids:
                pending_igtf_notes = move.debit_note_ids.filtered(
                    lambda dn: dn.state == 'posted' and 
                               dn.payment_state not in ('paid', 'reversed') and
                               any(line.product_id.id == product.id for line in dn.invoice_line_ids)
                )
                
                if pending_igtf_notes:
                    move.has_pending_igtf_debit_note = True


    l10n_ve_igtf_note_debit_origin = fields.Boolean(
        default=False, copy=False,
        help="True si esta Nota de Débito fue generada automáticamente por "
             "el flujo de IGTF Nota de Débito (l10n_ve_igtf_note_debit).",
    )

  
    def prepare_igtf_payment_debit_note(self, igtf_amount_company_curr, invoice, payment):
        
        self.ensure_one()
        company = invoice.company_id
        is_customer = invoice.move_type in ("out_invoice", "in_refund")

        product = company.igtf_note_debit_product_id
        if not product:
            raise UserError(_(
                "Configure el producto de 'Percepción de IGTF' en Ajustes > "
                "Contabilidad > IGTF antes de usar el modo 'Nota de Débito "
                "Fiscal automática'."
            ))

        debit_journal = self.env["account.journal"].search(
            [
                ("company_id", "=", company.id),
                ("is_debit", "=", True),
                ("type", "=", "sale" if is_customer else "purchase"),
            ],
            limit=1,
        )

        debit_note_wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({
            "date": fields.Date.context_today(self),
            "reason": _("Percepción de IGTF (%s%%) s/ %s") % (company.igtf_percentage, invoice.name),
            "journal_id": debit_journal.id if debit_journal else invoice.journal_id.id,
            "move_ids": [(4, invoice.id)],
        })
        action = debit_note_wizard.create_debit()
        debit_note_id = action.get("res_id") if isinstance(action, dict) else False
        if not debit_note_id:
            raise UserError(_("El asistente de Nota de Débito no devolvió un ID válido."))

        
        product_taxes = product.taxes_id if is_customer else product.supplier_taxes_id

        debit_note = self.env["account.move"].browse(debit_note_id)
        debit_note.write({
            "currency_id": company.currency_id.id,
            "origin_payment_to_pay_igtf": payment.move_id.id,
            "l10n_ve_igtf_note_debit_origin": True,
            "invoice_line_ids": [(0, 0, {
                "product_id": product.id,
                "quantity": 1.0,
                "price_unit": igtf_amount_company_curr,
                "tax_ids": [(6, 0, product_taxes.ids)],
            })],
        })
        debit_note.with_context(move_action_post_alert=True).action_post()
        return debit_note

   
    def settle_igtf_debit_note(self, debit_note, source_payment, include_in_payment=None, outstanding_line=None):
        if not debit_note:
            return
        company = debit_note.company_id
        if include_in_payment is None:
            include_in_payment = company.igtf_note_debit_include_in_payment_default

        if not include_in_payment:
            self._settle_igtf_debit_note_with_vef_payment(debit_note, source_payment)
            return

        if outstanding_line is None:
            outstanding_line = source_payment.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
                and not l.reconciled
                and l.currency_id.compare_amounts(l.amount_residual_currency, 0.0) != 0
            )[:1]
        debit_note_open_lines = debit_note.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable") and not l.reconciled
        )
        if outstanding_line and debit_note_open_lines:
            debit_note.js_assign_outstanding_line(outstanding_line.id)

    def _settle_igtf_debit_note_with_vef_payment(self, debit_note, source_payment):
        """Crea y postea un `account.payment` aparte, siempre en VEF, por el
        monto exacto de la ND, y lo concilia contra ella. Se usa cuando
        `company.igtf_note_debit_collection_mode == 'separate_vef_payment'`
        -- el pago de origen (`source_payment`) solo cubrió la factura."""
        company = debit_note.company_id
        journal = company.igtf_note_debit_vef_journal_id
        if not journal:
            journal = self.env["account.journal"].search([
                ("company_id", "=", company.id),
                ("type", "in", ("bank", "cash")),
                ("is_igtf", "!=", True),
                "|",
                ("currency_id", "=", self.env.ref("base.VEF").id),
                "&",
                ("currency_id", "=", False),
                ("company_id.currency_id", "=", self.env.ref("base.VEF").id),
            ], limit=1)
        if not journal:
            raise UserError(_(
                "Configure el diario en VEF para el cobro de IGTF en Ajustes "
                "> Contabilidad > IGTF (o cree un diario de banco/caja en "
                "Bolívares sin marcar como IGTF)."
            ))

        debit_note_line = debit_note.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable") and not l.reconciled
        )
        if not debit_note_line:
            return self.env["account.payment"]
        igtf_amount = abs(sum(debit_note_line.mapped("amount_residual")))

        vef_payment = self.env["account.payment"].create({
            "payment_type": source_payment.payment_type,
            "partner_type": source_payment.partner_type,
            "partner_id": source_payment.partner_id.id,
            "amount": igtf_amount,
            "currency_id": company.currency_id.id,
            "journal_id": journal.id,
            "date": source_payment.date,
            "memo": _("IGTF s/ %s") % debit_note.name,
        })
        vef_payment.action_post()

        counterpart_lines = vef_payment.move_id.line_ids.filtered(
            lambda l: l.account_type in ("asset_receivable", "liability_payable")
        )
        if len(counterpart_lines.mapped("account_id") | debit_note_line.mapped("account_id")) == 1:
            (counterpart_lines | debit_note_line).reconcile()
        return vef_payment

 
    def js_assign_outstanding_line(self, line_id):
        self.ensure_one()
        if self.company_id.igtf_note_debit_mode != "debit_note":
            return super().js_assign_outstanding_line(line_id)

        # Si `self` ya ES una Nota de Débito (ej. `settle_igtf_debit_note`
        # nos vuelve a llamar sobre la propia ND para conciliarla contra el
        # remanente del pago), no hay que generarle otra ND de IGTF -- eso
        # es lo que causaba "no puede crear una nota de débito para una
        # factura que ya está vinculada a otra nota". Se concilia normal.
        if self.debit_origin_id:
            return super().js_assign_outstanding_line(line_id)

        outstanding_line = self.env["account.move.line"].browse(line_id)
        payment_move = outstanding_line.move_id

        is_advance_payment = payment_move.is_advance_move or payment_move.origin_payment_advanced_payment_id or (
            payment_move.origin_payment_id and payment_move.origin_payment_id.is_advance_payment
        )
        if is_advance_payment:
            return super().js_assign_outstanding_line(line_id)

        payment = payment_move.origin_payment_id
        if not payment:
            return super().js_assign_outstanding_line(line_id)

        is_igtf_journal = (
            payment.journal_id.is_igtf
            if (
                self.partner_id._check_igtf_apply_improved(self.move_type)
                and not self.journal_id.is_purchase_international
            )
            else False
        )
        if not is_igtf_journal:
            return super().js_assign_outstanding_line(line_id)

        receivable_payable_line = self.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable") and not l.reconciled
        )
        
        if not receivable_payable_line or receivable_payable_line.account_id != outstanding_line.account_id:
            return super().js_assign_outstanding_line(line_id)

 
        widget = getattr(self, "invoice_outstanding_credits_debits_widget", {}) or {}
        widget_content = widget.get("content", []) if isinstance(widget, dict) else []
        matched_content = next((c for c in widget_content if c.get("id") == line_id), None)
        if not matched_content:
            return super().js_assign_outstanding_line(line_id)

        advance_amount = matched_content.get("amount", 0.0)
        advance_amount_payment_curr = matched_content.get("amount_residual_currency", 0.0)
        conversion_date = matched_content.get("date_to_convert") or outstanding_line.date

        if not advance_amount:
            return super().js_assign_outstanding_line(line_id)

        advance_amount_residual = abs(self.amount_residual)
    
        base_amount_applied = min(advance_amount_residual, advance_amount)

        applied_payment_curr = advance_amount_payment_curr
        if advance_amount > 0:
            applied_payment_curr = payment.currency_id.round(
                advance_amount_payment_curr * (base_amount_applied / advance_amount))

                         
        company_currency = self.company_id.currency_id
        igtf_amount_company_curr = abs(payment.calculate_igtf_for_payment(
            self, base_amount_applied, company_currency, conversion_date
        ))

        if is_igtf_journal:
            if (base_amount_applied + igtf_amount_company_curr) < advance_amount:
                base_amount_applied = self.currency_id.round(base_amount_applied + igtf_amount_company_curr)
                if advance_amount > 0:
                    applied_payment_curr = payment.currency_id.round(
                        advance_amount_payment_curr * (base_amount_applied / advance_amount))
                

        
        factura_line = receivable_payable_line
        force_balance = None
        if abs(base_amount_applied - advance_amount_residual) <= self.currency_id.rounding:
            force_balance = abs(factura_line.amount_residual)

        lines_to_match = receivable_payable_line + outstanding_line
        debit_line = lines_to_match.filtered(lambda l: l.balance > 0.0)[:1]
        credit_line = lines_to_match.filtered(lambda l: l.balance < 0.0)[:1]
        if not debit_line or not credit_line:
            return super().js_assign_outstanding_line(line_id)


        if force_balance is not None:
            amount_curr_by_line_id = {
                receivable_payable_line.id: abs(factura_line.amount_residual_currency),
                outstanding_line.id: applied_payment_curr,
            }
        else:
            amount_curr_by_line_id = {
                receivable_payable_line.id: base_amount_applied,
                outstanding_line.id: applied_payment_curr,
            }

        balance_applied = force_balance if force_balance is not None else payment.currency_id._convert(
            applied_payment_curr, self.company_id.currency_id, self.company_id, conversion_date,
        )
        self.env["account.partial.reconcile"].create({
            "debit_move_id": debit_line.id,
            "credit_move_id": credit_line.id,
            "amount": balance_applied,
            "debit_amount_currency": amount_curr_by_line_id[debit_line.id],
            "credit_amount_currency": amount_curr_by_line_id[credit_line.id],
        })

        debit_note = self.prepare_igtf_payment_debit_note(igtf_amount_company_curr, self, payment)
        self.settle_igtf_debit_note(debit_note, payment)

        return True


    def _create_advance_payment_move(self, amount_residual, lines):
        if self.company_id.igtf_note_debit_mode != "debit_note":
            return super()._create_advance_payment_move(amount_residual, lines)

        self.ensure_one()
        widget = getattr(self, "invoice_outstanding_credits_debits_widget_advance_payment", {}) or {}
        widget_content = widget.get("content", []) if isinstance(widget, dict) else []

        target_move_id = lines.move_id.id
        matched_content = next(
            (c for c in widget_content if c.get("move_id") == target_move_id), None
        )

        advance_amount = matched_content.get("amount", 0.0) if matched_content else 0.0
        advance_amount_payment_curr = matched_content.get("amount_residual_currency", 0.0) if matched_content else 0.0
        conversion_date = matched_content.get("date_to_convert") if matched_content else False

        if not advance_amount:
            raise UserError(_("The advance amount to apply was not found."))

        payment = lines.move_id.origin_payment_advanced_payment_id or lines.move_id.origin_payment_id
        if not payment:
            raise UserError(_("No associated Payment record found."))

        advance_amount_residual = amount_residual
        is_customer = self.move_type in ("out_invoice", "in_refund")

        receivable_payable_line = self.line_ids.filtered(
            lambda l: l.account_id.account_type in ("asset_receivable", "liability_payable")
        )
        if not receivable_payable_line:
            raise UserError(_("No accounts receivable/payable line found on the invoice."))
        account_rp = receivable_payable_line.account_id.id

        is_igtf_journal = (
            payment.journal_id.is_igtf
            if (
                self.partner_id._check_igtf_apply_improved(self.move_type)
                and not self.journal_id.is_purchase_international
            )
            else False
        )

        base_amount_applied = min(advance_amount_residual, advance_amount)

        applied_payment_curr = advance_amount_payment_curr
        if advance_amount > 0:
            applied_payment_curr = payment.currency_id.round(
                advance_amount_payment_curr * (base_amount_applied / advance_amount)
            )

        advance_line = lines.filtered_domain([
            "|",
                "&", ("account_id.account_type", "=", "liability_current"), ("account_id.is_advance_account", "=", True),
                "&", ("account_id.account_type", "=", "asset_current"), ("account_id.is_advance_account", "=", True),
            ("account_id.reconcile", "=", True),
        ])
        advance_line = advance_line.account_id[:1]
        if not advance_line:
            advance_line = (
                self.partner_id.default_advance_customer_account_id if is_customer
                else self.partner_id.default_advance_supplier_account_id
            )

        if is_customer:
            name_rp, name_adv = "CUENTA POR COBRAR CLIENTE", "ANTICIPO/CLIENTE"
        else:
            name_rp, name_adv = "CUENTA POR PAGAR PROVEEDOR", "ANTICIPO/PROVEEDOR"
        account_adv = advance_line.id

        common_vals = {
            "partner_id": self.partner_id.id,
            "payment_id_advance": payment.id,
            "reconciled": False,
            "date": conversion_date,
        }
        advance_val = {"name": name_adv, "account_id": account_adv}
        counter_part_val = {"name": name_rp, "account_id": account_rp}

        igtf_amount = 0.0
        if is_igtf_journal:
            igtf_amount = abs(payment.calculate_igtf_for_payment(
                self, applied_payment_curr, payment.currency_id, conversion_date
            ))

        force_balance = None
        if (abs(base_amount_applied - advance_amount_residual) <= self.currency_id.rounding
                and payment.currency_id == self.currency_id):
            force_balance = abs(receivable_payable_line.amount_residual)

        line_vals = self.prepare_advance_payment_vals(
            payment, base_amount_applied, advance_val, counter_part_val,
            conversion_date, common_vals,
            amount_payment_curr=applied_payment_curr,
            force_balance=force_balance,
        )

        advance_journal = self.env.company.advance_payment_igtf_journal_id
        move = self.env["account.move"].create({
            "journal_id": advance_journal.id,
            "date": conversion_date if not payment.keep_alter_value_vef else payment.date,
            "partner_id": self.partner_id.id,
            "ref": "CRUCE DE ANTICIPO",
            "line_ids": line_vals,
            "is_advance_move": True,
            "currency_id": payment.currency_id.id,
            "origin_payment_advanced_payment_id": payment.id,
        })

        if is_igtf_journal and igtf_amount > 0.0:
           
            company_currency = self.company_id.currency_id
            igtf_amount_company_curr = payment.currency_id._convert(
                igtf_amount, company_currency, self.company_id, conversion_date,
            )
            debit_note = self.prepare_igtf_payment_debit_note(igtf_amount_company_curr, self, payment)
            self.settle_igtf_debit_note(debit_note, payment)
            move.origin_payment_to_pay_igtf = payment.move_id.id

        return move

    @api.depends(
        'amount_residual',
        'debit_note_ids.origin_payment_to_pay_igtf',
        'debit_note_ids.state',
        'debit_note_ids.payment_state',
        'debit_note_ids.amount_total_signed',
    )
    def compute_bi_igtf(self):
        for rec in self:
            rec.igtf_top_aply = 0.0
            rec.alter_bi_igtf = 0.0
            rec.foreign_bi_igtf = 0.0
            rec.bi_igtf = 0.0
            
            if abs(rec.amount_residual) > 0 or rec.payment_state in ['paid','in_payment']: 
                rec.igtf_top_aply = abs(rec.amount_total_signed) * (rec.company_id.igtf_percentage / 100)
                receivable_payable_lines = rec.line_ids.filtered(lambda line: line.account_id.reconcile)

                final_payment_moves = receivable_payable_lines.reconciled_lines_ids.mapped('move_id')

                account = [rec.company_id.customer_account_igtf_id.id,rec.company_id.supplier_account_igtf_id.id ]
                
                total_bi_igtf = 0.0
                igtf_top = 0.0
                alter_bi_igtf = 0.0
                foreign_bi_igtf = 0.0
                bank_amount = 0.0
                target_account = False
                partial_amount = 0.0

                partner_context = rec.partner_id.with_company(rec.company_id)
                igtf_debit_notes = rec.debit_note_ids.filtered(
                    lambda dn: dn.origin_payment_to_pay_igtf
                    and dn.state == 'posted'
                    and dn.payment_state not in ['reversed', 'cancelled']
                )
                debit_note_by_payment = {
                    dn.origin_payment_to_pay_igtf.id: dn for dn in igtf_debit_notes
                }
                for payment_move in final_payment_moves:
                    if rec.move_type in ['out_invoice', 'out_refund']:
                        target_account = partner_context.property_account_receivable_id
                    else:
                        target_account = partner_context.property_account_payable_id

                    igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in account)
                  
                    origin_payment = (
                        payment_move.origin_payment_advanced_payment_id
                        or payment_move.origin_payment_id
                    )
                    lookup_move_id = origin_payment.move_id.id if origin_payment else payment_move.id
                    igtf_debit_note = debit_note_by_payment.get(lookup_move_id)
                    has_igtf = bool(igtf_line) or bool(igtf_debit_note)
                    partner_line = payment_move.line_ids.filtered(lambda l: l.account_id.id == target_account.id)
                    bank_line = payment_move.line_ids.filtered(lambda line: line.account_id.id not in partner_line.mapped('account_id').ids and line.account_id.id not in igtf_line.mapped('account_id').ids)
                    
                    igtf_amount = 0.0
                    amount_base_payment = 0.0
                    if bank_line and partner_line:

                        factura_line = rec.line_ids.filtered(lambda l: l.account_id.id == target_account.id)

                        partial = self.env['account.partial.reconcile'].search([
                            '|',
                            '&', ('debit_move_id', '=', factura_line.id), ('credit_move_id', '=', partner_line.ids),
                            '&', ('debit_move_id', '=', partner_line.ids), ('credit_move_id', '=', factura_line.id)
                        ])
                        bank_amount = abs(bank_line[0].amount_currency)
                        bank_amount_balance = abs(bank_line[0].balance)
                        if partial:
                            partial_amount = abs(sum(partial.mapped('amount')))
                        
                        if has_igtf and partial:
                            if igtf_debit_note:
                                # La ND siempre se emite en moneda de compañía
                                # (VEF) -- hay que convertirla a la moneda del
                                # PAGO para que sea comparable contra
                                # `bank_amount` (que sí está en esa moneda).
                                igtf_amount = abs(igtf_debit_note.amount_total_signed)
                                igtf_amount_currency = abs(rec.company_id.currency_id._convert(
                                    igtf_amount, payment_move.currency_id, rec.company_id, igtf_debit_note.date,
                                ))
                            else:
                                igtf_amount = abs(igtf_line[0].balance)
                                igtf_amount_currency = abs(igtf_line[0].amount_currency)
                            partial_amount = abs(sum(partial.mapped('amount')))
                        
                        if not has_igtf and bank_line and partial:
                            igtf_top += partial_amount
                            
                        
                        if has_igtf and bank_line and partial:

                            if payment_move.origin_payment_id and payment_move.origin_payment_id.reconciled_invoices_count > 1:

                                amount_base_payment = partial_amount

                            elif 'pos_payment_ids' in bank_line[0].move_id._fields and getattr(bank_line[0].move_id, 'pos_payment_ids', False):
                                amount_base_payment = rec.company_id.currency_id.round(igtf_amount / (rec.company_id.igtf_percentage / 100))
                            

                            elif  rec.company_id.currency_id.round(partial_amount * (rec.company_id.igtf_percentage / 100)) == igtf_amount:
                                    
                                amount_base_payment = partial_amount
                                igtf_amount = amount_base_payment * (rec.company_id.igtf_percentage / 100)
                               
                            else:
                                if rec.company_id.currency_id.round(bank_amount * (rec.company_id.igtf_percentage / 100)) == igtf_amount_currency:
                                    
                                    amount_base_payment = bank_amount_balance
                                    igtf_amount = igtf_amount 
                                else:
                                    amount_base_payment = partial_amount
                                    igtf_amount = igtf_amount 

                        if has_igtf and partial:
                            alter_bi_igtf += igtf_amount

                    conversion_date = False

                    if rec.invoice_date != False and payment_move.date <= rec.invoice_date:
                        conversion_date = rec.invoice_date
                    else:
                        conversion_date = payment_move.date

                    total_bi_igtf += amount_base_payment

                    if total_bi_igtf > abs(rec.amount_total_signed):
                        total_bi_igtf = abs(rec.amount_total_signed)

                    foreign_bi_igtf += rec.company_id.currency_id._convert(
                        amount_base_payment, 
                        rec.currency_id, 
                        rec.company_id, 
                        conversion_date,
                    )

                    if foreign_bi_igtf > abs(rec.amount_total):
                        foreign_bi_igtf = abs(rec.amount_total)


                apply = rec.igtf_top_aply - (igtf_top * (rec.company_id.igtf_percentage / 100))
                rec.igtf_top_aply = apply
                rec.alter_bi_igtf = alter_bi_igtf
                rec.foreign_bi_igtf = foreign_bi_igtf
                rec.bi_igtf = total_bi_igtf

  
    def remove_igtf_from_account_move(self, partial_id):

        partial_reconcile = self.env['account.partial.reconcile'].with_company(self.company_id).sudo().browse(partial_id).exists()
        
        related_moves = partial_reconcile.debit_move_id.move_id | partial_reconcile.credit_move_id.move_id
        
        igtf_account_ids = [
            self.company_id.customer_account_igtf_id.id,
            self.company_id.supplier_account_igtf_id.id
        ]

        not_search = [
            'out_invoice',
            'out_refund',
            'in_invoice',
            'in_refund',
            'out_receipt',
            'in_receipt',
        ]
        
        liquidity_account_types = ['asset_cash','bank','asset_current','liability_current']
        payment_move = related_moves.filtered(
            lambda move: move.line_ids.filtered(
                lambda line: line.account_id.account_type in liquidity_account_types and line.move_id.move_type not in not_search
            )
        )[:1]

        if not payment_move:
            return False
        if payment_move.currency_id == self.env.ref("base.VEF") and not payment_move.origin_payment_advanced_payment_id:
            return 
        
        if self.company_id.igtf_note_debit_mode == "debit_note":
            self.create_note_credit_igtf(partial_id)

        try:
            payment_move.button_draft()
        except Exception:
            return False
        
        igtf_line = payment_move.line_ids.filtered(lambda line: line.account_id.id in igtf_account_ids)
        receivable_payable_line = payment_move.line_ids.filtered(
            lambda line: line.account_id.id in [payment_move.partner_id.property_account_payable_id.id,payment_move.partner_id.property_account_receivable_id.id ]
        )[:1]
        if igtf_line and receivable_payable_line:
            igtf_line_balance = igtf_line.balance

            if igtf_line_balance > 0:
                new_debit = receivable_payable_line.debit + igtf_line_balance
                new_credit = 0.0
            else:
                new_credit = receivable_payable_line.credit + abs(igtf_line_balance)
                new_debit = 0.0

            advance_account = payment_move.partner_id.default_advance_customer_account_id.id if receivable_payable_line.credit > 0 else payment_move.partner_id.default_advance_supplier_account_id.id
            
            line_vals = {
                'debit': new_debit,
                'credit': new_credit,
                'balance': receivable_payable_line.balance + igtf_line.balance,
                'amount_currency': receivable_payable_line.amount_currency + igtf_line.amount_currency,
                'foreign_balance': receivable_payable_line.foreign_balance + igtf_line.foreign_balance,
                'foreign_debit': receivable_payable_line.foreign_debit + igtf_line.foreign_debit,
                'foreign_credit': receivable_payable_line.foreign_credit + igtf_line.foreign_credit,
                'account_id': advance_account if not payment_move.origin_payment_id.destination_account_id.is_advance_account else payment_move.origin_payment_id.destination_account_id.id,
                'name': receivable_payable_line.name,
            }

            payment_move.write({
                'line_ids': [
                    (2, igtf_line.id, False),
                    (1, receivable_payable_line.id, line_vals),
                ]
            })

            if 'is_advance_payment' in payment_move.origin_payment_id._fields:
                if payment_move.origin_payment_id and not payment_move.origin_payment_id.is_advance_payment:
                    payment_move.origin_payment_id.write({
                        'is_advance_payment':True,
                        'igtf_amount': 0.0
                    })

        try:
            if payment_move.origin_payment_advanced_payment_id:
                payment_move.origin_payment_advanced_payment_id.write({'advanced_move_ids': [(3, payment_move.id)]})
                payment_move.button_cancel()
            else:
                payment_move.action_post()
        except Exception:
            return False
            
        return True

    def create_note_credit_igtf(self, partial_id):
        """
        Crea y publica la Nota de Crédito correspondiente para reversar el IGTF 
        cuando el pago asociado se desconcilia o cancela.
        """
        partial_reconcile = self.env["account.partial.reconcile"].browse(partial_id)
        credit_move = partial_reconcile.credit_move_id.move_id
        debit_move = partial_reconcile.debit_move_id.move_id

        invoice_move = None
        payment_move = None

        if credit_move.move_type == 'out_invoice':
            invoice_move = credit_move
            payment_move = debit_move
        elif debit_move.move_type == 'out_invoice':
            invoice_move = debit_move
            payment_move = credit_move

        if not (invoice_move and invoice_move.debit_note_ids):
            _logger.error(
                "IGTF: create_note_credit_igtf — no debit_note_ids on invoice %s (id=%s)",
                invoice_move.name if invoice_move else 'None', invoice_move.id if invoice_move else 'None')
            return

    
        origin_payment = (
            payment_move.origin_payment_advanced_payment_id
            or payment_move.origin_payment_id
        )
        origin_payment_move_id = origin_payment.move_id.id if origin_payment else False

        target_debit_note = invoice_move.debit_note_ids.filtered(
            lambda dn: (
                dn.origin_payment_to_pay_igtf
                and dn.state == 'posted'
                and dn.payment_state != 'reversed'
                and dn.origin_payment_to_pay_igtf.id in (payment_move.id, origin_payment_move_id)
            )
        )[:1]

        if not target_debit_note:
            _logger.error(
                "IGTF: create_note_credit_igtf — no matching debit note for payment_move=%s (id=%s), invoice=%s (id=%s)",
                payment_move.name if payment_move else 'None', payment_move.id if payment_move else 'None',
                invoice_move.name, invoice_move.id)
            return

        reconciled_line = target_debit_note.line_ids.filtered(
            lambda l: l.account_type in ('asset_receivable', 'liability_payable')
        )[:1]
        if reconciled_line:
            self._unreconcile_and_cancel_advance(reconciled_line)

        target_debit_note.origin_payment_to_pay_igtf = False

        move_reversal = self.env['account.move.reversal'].with_context(
            active_model="account.move",
            active_ids=target_debit_note.ids
        ).create({
            'date': fields.Date.context_today(self),
            'journal_id': target_debit_note.journal_id.id,
        })

        try:
            reversal_action = move_reversal.refund_moves()
            reversal_move = self.env['account.move'].browse(reversal_action['res_id'])
            reversal_move.origin_payment_id = False
            reversal_move._post(soft=False)
            _logger.info(
                "IGTF: credit note %s (id=%s) created and posted for debit note %s (id=%s)",
                reversal_move.name, reversal_move.id, target_debit_note.name, target_debit_note.id)
        except Exception as e:
            _logger.error(
                "IGTF: failed to create/post credit note for debit note %s (id=%s): %s",
                target_debit_note.name, target_debit_note.id, e)

    def _unreconcile_and_cancel_advance(self, line):
        partials = line.matched_debit_ids + line.matched_credit_ids
        if not partials:
            return False
        partial = partials[0]
        counterpart_move = (
            partial.credit_move_id.move_id 
            if partial.debit_move_id == line 
            else partial.debit_move_id.move_id
        )
        line.remove_move_reconcile()
        if counterpart_move.origin_payment_advanced_payment_id:
            advance_payment = counterpart_move.origin_payment_advanced_payment_id
            counterpart_move.button_draft()
            counterpart_move.write({'origin_payment_advanced_payment_id': False})
            counterpart_move.with_context(
                move_action_cancel_advance_payment=True
            ).button_cancel()
            advance_payment.write({'advanced_move_ids': [(3, counterpart_move.id)]})
        return True
