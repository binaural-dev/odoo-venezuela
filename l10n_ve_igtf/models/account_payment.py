from odoo import api, models, fields, _, Command
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, float_compare, float_repr, float_round

import logging

_logger = logging.getLogger(__name__)


class AccountPaymentIgtf(models.Model):
    _inherit = "account.payment"

    is_igtf_on_foreign_exchange = fields.Boolean(
        string="IGTF on Foreign Exchange?",
        help="IGTF on Foreign Exchange",
        compute="_compute_is_igtf",
        store=True,
    )

    igtf_percentage = fields.Float(
        string="IGTF Percentage",
        compute="_compute_igtf_percentage",
        help="IGTF Percentage",
        store=True,
    )

    igtf_amount = fields.Float(
        string="IGTF Amount",
        help="IGTF Amount",
    )

    payment_from_wizard = fields.Boolean()

    invoices_origin_ids = fields.Many2many('account.move', string='Invoices Origin')

    @api.depends("partner_id")
    def _compute_igtf_percentage(self):
        for payment in self:
            payment.igtf_percentage = payment.env.company.igtf_percentage

    @api.depends("journal_id")
    def _compute_is_igtf(self):
        for payment in self:
            payment.is_igtf_on_foreign_exchange = False
            if payment.journal_id.is_igtf and payment.journal_id.currency_id and payment.journal_id.currency_id != self.env.ref("base.VEF"):
                payment.is_igtf_on_foreign_exchange = True

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, force_balance=None):
        for rec in self:
            vals = super(AccountPaymentIgtf, self)._prepare_move_line_default_vals(
                write_off_line_vals,
                force_balance=None,
            )

            if rec.payment_from_wizard:
                move_ids = rec.invoices_origin_ids
                if rec.igtf_percentage and rec.igtf_amount > 0.0:
                    is_international = any(
                        m.journal_id.is_purchase_international for m in move_ids
                    ) or rec.journal_id.is_purchase_international
                    if not is_international:
                        rec._create_igtf_moves_in_payments(vals, write_off_line_vals)
                if rec.igtf_amount <= 0.0:
                    total_base_residual = abs(sum(rec.invoices_origin_ids.mapped('amount_residual_signed')))
                    if write_off_line_vals:
                        rec._fix_writeoff_balance(vals, write_off_line_vals)
                    else:
                        fechas_lista = set(rec.invoices_origin_ids.mapped('invoice_date'))
                        vals0_bal = vals[0].get('debit', 0.0) - vals[0].get('credit', 0.0)
                        if abs(total_base_residual) - abs(vals0_bal) <= 0.1 and len(fechas_lista) == 1 and rec.date in fechas_lista:
                            if rec.partner_type == "customer":
                                vals[0].update({"debit": total_base_residual, "credit": 0.0})
                                vals[1].update({"debit": 0.0, "credit": total_base_residual})
                            else:
                                vals[0].update({"debit": 0.0, "credit": total_base_residual})
                                vals[1].update({"debit": total_base_residual, "credit": 0.0})

            return vals

    def calculate_igtf_for_payment(self, invoice, amount_payment, payment_currency, payment_date, base=False):
        return self.env["l10n_ve_igtf.utils"].calculate_igtf_for_payment(
            invoice, amount_payment, payment_currency, payment_date,
            company=self.company_id, base=base,
        )

    def convert_to_company_currency(self, from_currency, amount, date=False, invoice_currency=False):
        self.ensure_one()
        return self.env["l10n_ve_igtf.utils"]._convert_to_company_currency(
            from_currency, amount, date, self.company_id, invoice_currency=invoice_currency,
        )

    def convert_to_external_currency(self, from_currency, amount, date=False):
        self.ensure_one()
        return self.env["l10n_ve_igtf.utils"]._convert_to_external_currency(
            from_currency, amount, date, self.company_id,
        )

    def _create_igtf_moves_in_payments(self, vals, write_off_line_vals=False):
        igtf_account = (
            self.env.company.customer_account_igtf_id.id
            if self.partner_type == "customer"
            else self.env.company.supplier_account_igtf_id.id
        )
        if self.env.context.get("from_pos", False):
            return

        for payment in self:
            if payment.igtf_amount > 0.0:
                if payment.payment_type == "inbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_inbound_move_line_igtf_vals(vals, write_off_line_vals)

                if payment.payment_type == "outbound":
                    vals_igtf = [x for x in vals if x["account_id"] == igtf_account]
                    if not vals_igtf:
                        payment._prepare_outbound_move_line_igtf_vals(vals, write_off_line_vals)

    def _fix_writeoff_balance(self, vals, write_off_line_vals):
        """Force counterpart line to match the invoices' actual residual
        in company currency, and adjust the write-off to keep the entry
        balanced. Mirrors the residual-based adjustment in
        _prepare_inbound_move_line_igtf_vals for the non-IGTF case,
        preventing descuadres between individual conversion in the
        wizard and aggregate _convert in the payment lines.
        """
        for rec in self:
            if not write_off_line_vals or len(vals) < 3:
                continue
            comp_curr = rec.company_id.currency_id
            currency = rec.currency_id

            cpart = vals[1]
            current = cpart.get('debit', 0.0) - cpart.get('credit', 0.0)

            invoice_residual = sum(rec.invoices_origin_ids.mapped('amount_residual_signed'))
            residual_abs = abs(invoice_residual) if invoice_residual else 0.0

            expected = -invoice_residual if invoice_residual else 0.0

            diff = expected - current
            if comp_curr.is_zero(diff):
                return

            if expected >= 0:
                cpart.update({'debit': expected, 'credit': 0.0})
            else:
                cpart.update({'debit': 0.0, 'credit': -expected})
            amt = comp_curr._convert(
                abs(expected), currency, rec.company_id, rec.date,
            )
            cpart['amount_currency'] = amt if expected > 0 else -amt
            w_off = vals[2]
            w_off_bal = w_off.get('debit', 0.0) - w_off.get('credit', 0.0) - diff

            w_amt = comp_curr._convert(
                abs(w_off_bal), currency, rec.company_id, rec.date,
            )
            if w_off_bal >= 0:
                w_off.update({'debit': w_off_bal, 'credit': 0.0})
            else:
                w_off.update({'debit': 0.0, 'credit': -w_off_bal})
            w_off['amount_currency'] = w_amt if w_off_bal > 0 else -w_amt

    def _create_inbound_move_line_igtf_vals(self, vals, igtf_base):
        for rec in self:
            currency = rec.currency_id

            igtf_account = (
                rec.company_id.customer_account_igtf_id.id
                if rec.partner_type == "customer"
                else rec.company_id.supplier_account_igtf_id.id
            )

            if not igtf_account:
                raise UserError(_('Igtf Account in must be assigned in companies settings'))

            igtf_amount_curr = rec.igtf_amount

            if float_compare(igtf_amount_curr, 0.0, precision_digits=currency.decimal_places) > 0.0:

                if len(vals) == 2:
                    current_net_balance = 0.0
                    for line in vals:
                        line_balance = line.get('balance') or (line.get('debit', 0.0) - line.get('credit', 0.0))
                        current_net_balance += line_balance

                    igtf_amount_currency = abs(rec.igtf_amount)

                    cc = rec.company_id.currency_id
                    final_igtf_balance = float(float_repr(current_net_balance, precision_digits=cc.decimal_places))
                    credit = abs(final_igtf_balance)
                    vals.append({
                        "name": "IGTF",
                        "currency_id": currency.id,
                        "amount_currency": -igtf_amount_currency,
                        "account_id": igtf_account,
                        "partner_id": rec.partner_id.id,
                        "credit": credit,
                    })

                else:
                    credit = abs(igtf_base)
                    vals.append({
                        "name": "IGTF",
                        "currency_id": currency.id,
                        "amount_currency": -igtf_amount_curr,
                        "account_id": igtf_account,
                        "partner_id": rec.partner_id.id,
                        "credit": credit,
                    })

        return vals

    def _create_outbound_move_line_igtf_vals(self, vals, igtf_base):

        for rec in self:
            currency = rec.currency_id

            igtf_account = (
                rec.company_id.customer_account_igtf_id.id
                if rec.partner_type == "customer"
                else rec.company_id.supplier_account_igtf_id.id
            )

            if not igtf_account:
                raise UserError(_('Igtf Account in must be assigned in companies settings'))

            igtf_amount_curr = rec.igtf_amount

            if float_compare(igtf_amount_curr, 0.0, precision_digits=currency.decimal_places) > 0.0:

                if len(vals) == 2:
                    current_net_balance = 0.0
                    for line in vals:
                        line_balance = line.get('balance') or (line.get('debit', 0.0) - line.get('credit', 0.0))
                        current_net_balance += line_balance

                    igtf_amount_currency = abs(rec.igtf_amount)

                    cc = rec.company_id.currency_id
                    final_igtf_balance = float(float_repr(current_net_balance, precision_digits=cc.decimal_places))
                    credit = abs(final_igtf_balance)
                    vals.append({
                        "name": "IGTF",
                        "currency_id": currency.id,
                        "amount_currency": igtf_amount_currency,
                        "account_id": igtf_account,
                        "partner_id": rec.partner_id.id,
                        "debit": credit,
                    })

                else:
                    credit = abs(igtf_base)
                    vals.append({
                        "name": "IGTF",
                        "currency_id": currency.id,
                        "amount_currency": igtf_amount_curr,
                        "account_id": igtf_account,
                        "partner_id": rec.partner_id.id,
                        "debit": credit,
                    })
        return vals

    def _prepare_inbound_move_line_igtf_vals(self, vals, write_off_line_vals=False):
        for rec in self:
            lines = [line for line in vals]
            if rec.payment_type == "inbound":
                fechas_lista = set(rec.invoices_origin_ids.mapped('invoice_date'))

                total_base_residual = abs(sum(rec.invoices_origin_ids.mapped('amount_residual_signed')))
                top_igtf = abs(sum(rec.invoices_origin_ids.mapped('igtf_top_aply')))

                top_igtf_residual_base = total_base_residual + top_igtf
                currency = rec.currency_id
                precision = currency.decimal_places

                credit_line_unrounded = lines[1].get("amount_currency", 0.0) + rec.igtf_amount
                credit_line = credit_line_unrounded

                credit_amount = abs(lines[1].get("debit", 0.0) - lines[1].get("credit", 0.0))
                amount = credit_amount
                igtf_base = 0.0
                total_base_residual_converted = 0.0
                precision_base = self.env.company.currency_id.decimal_places
                if rec.igtf_amount > 0.0:
                    balance = abs(lines[0].get("debit", 0.0) - lines[0].get("credit", 0.0))
                    if balance - top_igtf_residual_base >= 1.0 and len(fechas_lista) == 1 and rec.date in fechas_lista:
                        igtf_base = top_igtf
                        amount = credit_amount - igtf_base
                    else:
                        porcion_igtf = rec.igtf_amount / abs(lines[0].get("amount_currency", 0.0))
                        igtf_base = float_round((balance * porcion_igtf), precision_digits=precision_base)

                        if top_igtf - igtf_base <= 0.1:
                            igtf_base = float_round(top_igtf, precision_digits=precision_base)

                        amount = credit_amount - igtf_base

                    total_base_residual_converted = rec.company_id.currency_id._convert(
                        total_base_residual,
                        currency,
                        rec.company_id,
                        rec.date,
                    )

                    total_base_residual_converted_with_igtf = float_round(abs(total_base_residual_converted) + abs(rec.igtf_amount), precision_digits=precision)
                    if total_base_residual_converted_with_igtf == abs(lines[0].get("amount_currency", 0.0)):
                        if abs(credit_amount) > abs(total_base_residual):
                            amount = abs(total_base_residual)

                if float_compare(rec.igtf_amount, 0.0, precision_digits=precision) > 0.0:
                    if not write_off_line_vals:
                        vals[1].update({"amount_currency": credit_line, "debit": 0.0, "credit": amount})
                    else:
                        vals[1].update({"debit": 0.0, "credit": total_base_residual})

                if write_off_line_vals:
                    net_no_writeoff = sum(
                        v.get('debit', 0.0) - v.get('credit', 0.0)
                        for v in vals
                        if v is not vals[2]
                    ) - igtf_base

                    amout_currency_no_writeoff = sum(
                        v.get('amount_currency', 0)
                        for v in vals
                        if v is not vals[2]
                    ) - rec.igtf_amount

                    if net_no_writeoff >= 0:
                        vals[2].update({'debit': net_no_writeoff, 'credit': 0.0})
                    else:
                        vals[2].update({'debit': 0.0, 'credit': -net_no_writeoff})
                    vals[2]['amount_currency'] = -amout_currency_no_writeoff

                rec._create_inbound_move_line_igtf_vals(vals, igtf_base)

    def _prepare_outbound_move_line_igtf_vals(self, vals, write_off_line_vals=False):
        for rec in self:
            lines = [line for line in vals]
            if rec.payment_type == "outbound":

                total_base_residual = abs(sum(rec.invoices_origin_ids.mapped('amount_residual_signed')))
                top_igtf = abs(sum(rec.invoices_origin_ids.mapped('igtf_top_aply')))

                top_igtf_residual_base = total_base_residual + top_igtf
                currency = rec.currency_id
                precision = currency.decimal_places

                debit_line_unrounded = lines[1].get("amount_currency", 0.0) - rec.igtf_amount
                debit_line = debit_line_unrounded

                debit_amount = abs(lines[1].get("debit", 0.0) - lines[1].get("credit", 0.0))

                amount = debit_amount
                igtf_base = 0.0
                total_base_residual_converted = 0.0
                precision_base = self.env.company.currency_id.decimal_places

                if rec.igtf_amount > 0.0:
                    balance = abs(lines[0].get("debit", 0.0) - lines[0].get("credit", 0.0))
                    if balance - top_igtf_residual_base >= 1.0 or len(rec.invoices_origin_ids) > 1:
                        igtf_base = top_igtf
                        amount = debit_amount - igtf_base
                    else:
                        porcion_igtf = rec.igtf_amount / abs(lines[0].get("amount_currency", 0.0))
                        igtf_base = float_round((balance * porcion_igtf), precision_digits=precision_base)

                        if top_igtf - igtf_base <= 0.1:
                            igtf_base = float_round(top_igtf, precision_digits=precision_base)

                        amount = (debit_amount) - abs(igtf_base)

                    total_base_residual_converted = rec.company_id.currency_id._convert(
                        total_base_residual,
                        currency,
                        rec.company_id,
                        rec.date,
                    )

                    total_base_residual_converted_with_igtf = float_round(abs(total_base_residual_converted) + abs(rec.igtf_amount), precision_digits=precision)
                    if total_base_residual_converted_with_igtf == abs(lines[0].get("amount_currency", 0.0)):
                        if abs(debit_amount) > abs(total_base_residual):
                            amount = abs(total_base_residual)

                if float_compare(rec.igtf_amount, 0.0, precision_digits=precision) > 0.0:
                    if not write_off_line_vals:
                        vals[1].update({"amount_currency": debit_line, "debit": amount, "credit": 0.0})
                    else:
                        vals[1].update({"debit": total_base_residual, "credit": 0.0})

                if write_off_line_vals:
                    net_no_writeoff = sum(
                        v.get('debit', 0.0) - v.get('credit', 0.0)
                        for v in vals
                        if v is not vals[2]
                    ) + igtf_base

                    amout_currency_no_writeoff = sum(
                        v.get('amount_currency', 0)
                        for v in vals
                        if v is not vals[2]
                    ) - rec.igtf_amount

                    if net_no_writeoff >= 0:
                        vals[2].update({'debit': net_no_writeoff, 'credit': 0.0})
                    else:
                        vals[2].update({'debit': 0.0, 'credit': -net_no_writeoff})
                    vals[2]['amount_currency'] = -amout_currency_no_writeoff

                rec._create_outbound_move_line_igtf_vals(vals, igtf_base)

    def get_moves(self):
        ids = self.env.context.get("active_id") or self.env.context.get("active_ids")

        if isinstance(ids, int):
            return self.env["account.move"].browse([ids])
        else:
            move_lines = self.env["account.move.line"].browse(ids)
            return set(move_lines.mapped("move_id"))
