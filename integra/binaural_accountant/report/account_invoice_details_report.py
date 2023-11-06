from collections import defaultdict
from datetime import datetime
from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, format_date

import logging

_logger = logging.getLogger(__name__)

p_initial_amounts = {"amount": 0, "foreign_amount": 0}

initial_amounts = {
    "gross_amount": 0,
    "discount_amount": 0,
    "total_amount": 0,
    "formatted_gross_amount": 0,
    "formatted_discount_amount": 0,
    "formatted_total_amount": 0,
}


class AccountInvoiceDetailsReport(models.AbstractModel):
    _name = "report.binaural_accountant.report_account_invoices_details"

    def _get_domain_search_moves(self, wizard):
        return [
            ("state", "=", "posted"),
            ("company_id", "=", wizard.company_id.id),
            ("invoice_date", ">=", wizard.date_from),
            ("invoice_date", "<=", wizard.date_to),
            ("move_type", "in", ["out_invoice", "out_refund"]),
        ]

    def _get_domain_search_payment(self, wizard):
        return [
            ("state", "=", "posted"),
            ("company_id", "=", wizard.company_id.id),
            ("date", ">=", wizard.date_from),
            ("date", "<=", wizard.date_to),
            ("reconciled_invoice_ids", "!=", False),
        ]

    @api.model
    def get_sale_details(self, wizard):
        invoice_ids = self.env["account.move"].search(self._get_domain_search_moves(wizard))
        payment_ids = self.env["account.payment"].search(self._get_domain_search_payment(wizard))

        invoices = defaultdict(lambda: dict())
        payments = defaultdict(lambda: dict())

        journals = []
        p_journals = []
        payment_terms = [{"name": _("Instant payment"), "id": "cash"}]
        invoice_move_types = [
            {"name": _("Invoices"), "type": "out_invoice"},
            {"name": _("Refund"), "type": "out_refund"},
        ]

        p_payment_terms = [{"name": _("Instant payment"), "id": "cash"}]

        for payment in payment_ids:
            for p_invoice in payment.reconciled_invoice_ids:
                term_id = (
                    str(p_invoice.invoice_payment_term_id.id)
                    if p_invoice.invoice_payment_term_id
                    else "cash"
                )

                journal_id = str(payment.journal_id.id)

                if term_id not in [x["id"] for x in p_payment_terms]:
                    p_payment_terms.append(self.new_payment_term(p_invoice))

                if journal_id not in [x["id"] for x in p_journals]:
                    p_journals.append(self.new_journal(payment))

                if not payments[term_id].get(journal_id, False):
                    payments[term_id][journal_id] = [{"invoice": p_invoice, "payment": payment}]
                else:
                    payments[term_id][journal_id].append({"invoice": p_invoice, "payment": payment})

                if not invoices[term_id].get("totals_" + journal_id, False):
                    journal_totals = p_initial_amounts
                else:
                    journal_totals = payments[term_id]["totals_" + journal_id]

                payments[term_id]["totals_" + journal_id] = self.p_get_new_values(
                    journal_totals, payment
                )

        _logger.info("Payment %s:", payments)

        for invoice in invoice_ids:
            journal_id = str(invoice.journal_id.id)

            if journal_id not in [x["id"] for x in journals]:
                journals.append(self.new_journal(invoice))

            if not invoices[journal_id].get(invoice.move_type, False):
                invoices[journal_id][invoice.move_type] = defaultdict(lambda: dict())

            term_id = (
                str(invoice.invoice_payment_term_id.id)
                if invoice.invoice_payment_term_id
                else "cash"
            )

            if term_id not in [x["id"] for x in payment_terms]:
                payment_terms.append(self.new_payment_term(invoice))

            if not invoices[journal_id][invoice.move_type].get(term_id, False):
                invoices[journal_id][invoice.move_type][term_id] = invoice

            invoices[journal_id][invoice.move_type][term_id] |= invoice

            if not invoices[journal_id][invoice.move_type].get("totals_" + term_id, False):
                term_totals = initial_amounts
            else:
                term_totals = invoices[journal_id][invoice.move_type]["totals_" + term_id]

            invoices[journal_id][invoice.move_type]["totals_" + term_id] = self.get_new_values(
                term_totals, invoice
            )

            if not invoices[journal_id].get("totals_" + invoice.move_type, False):
                type_totals = initial_amounts
            else:
                type_totals = invoices[journal_id]["totals_" + invoice.move_type]

            invoices[journal_id]["totals_" + invoice.move_type] = self.get_new_values(
                type_totals, invoice
            )

        data = {
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "date_now": datetime.now(),
            "company_id": wizard.company_id,
            "journal_ids": journals,
            "p_journals_ids": p_journals,
            "payment_term_ids": payment_terms,
            "p_payment_term_ids": p_payment_terms,
            "invoices": invoices,
            "payments": payments,
            "invoice_move_type": invoice_move_types,
        }

        return data

    def p_get_new_values(self, totals, payment):
        if payment.currency_id.id == self.env.ref("base.USD"):
            amount = totals["amount"] + payment.amount
            foreign_amount = totals["foreign_amount"] + payment.amount * payment.foreign_rate
        else:
            amount = totals["amount"] + payment.move_id.line_ids[0].debit
            foreign_amount = totals["foreign_amount"] + payment.amount

        return {"amount": amount, "foreign_amount": foreign_amount}

    def get_new_values(self, totals, invoice):
        gross_amount = totals["gross_amount"] + invoice.detailed_amounts["gross_amount"]
        discount_amount = totals["discount_amount"] + invoice.detailed_amounts["discount_amount"]
        total_amount = totals["total_amount"] + invoice.tax_totals["amount_total"]

        return {
            "gross_amount": gross_amount,
            "discount_amount": discount_amount,
            "total_amount": total_amount,
            "formatted_gross_amount": formatLang(
                self.env, gross_amount, currency_obj=invoice.currency_id
            ),
            "formatted_discount_amount": formatLang(
                self.env, discount_amount, currency_obj=invoice.currency_id
            ),
            "formatted_total_amount": formatLang(
                self.env, total_amount, currency_obj=invoice.currency_id
            ),
        }

    def new_payment_term(self, invoice):
        return {
            "name": invoice.invoice_payment_term_id.name,
            "id": str(invoice.invoice_payment_term_id.id),
        }

    def new_journal(self, invoice):
        return {"name": invoice.journal_id.name, "id": str(invoice.journal_id.id)}

    @api.model
    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        data.update(self.get_sale_details(self.env["account.invoices.details"].browse(docids)))
        return data
