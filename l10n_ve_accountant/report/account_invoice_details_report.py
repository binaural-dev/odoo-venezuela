from collections import defaultdict
from datetime import datetime
from odoo import api, fields, models, _
from odoo.tools import float_is_zero
from odoo.tools.misc import formatLang, format_date
from odoo.exceptions import ValidationError
import pytz

import logging

_logger = logging.getLogger(__name__)

p_initial_amounts = {"amount": 0, "foreign_amount": 0}

initial_amounts = {
    "gross_amount": 0,
    "discount_amount": 0,
    "total_amount": 0,
    "taxes_amount": 0,
    "gross_discount_amount": 0,
    "formatted_gross_discount_amount": 0,
    "formatted_taxes_amount": 0,
    "formatted_gross_amount": 0,
    "formatted_discount_amount": 0,
    "formatted_total_amount": 0,
    "total_items": 0,
}


class AccountInvoiceDetailsReport(models.AbstractModel):
    _name = "report.l10n_ve_accountant.report_account_invoices_details"

    def _get_domain_search_moves(self, wizard):
        return [
            ("state", "=", "posted"),
            ("company_id", "=", wizard.company_id.id),
            ("invoice_date_display", ">=", wizard.date_from),
            ("invoice_date_display", "<=", wizard.date_to),
            ("move_type", "in", ["out_invoice", "out_refund"]),
        ]

    def _get_domain_search_payment(self, wizard):
        return [
            ("state", "in", ["in_process", "paid"]),
            ("company_id", "=", wizard.company_id.id),
            ("date", ">=", wizard.date_from),
            ("date", "<=", wizard.date_to),
            ("partner_type", "=", "customer"),
            # ("reconciled_invoice_ids", "!=", False),
        ]

    @api.model
    def get_sale_details(self, wizard):
        user = self.env.user
        # Validar que la zona horaria este registrada de lo contrario no podra ubicar la fecha del dia actual del pais en el que se ubica
        if not user.tz:
            raise ValidationError(_('The time zone is not registered, log in to your profile and configure it.'))

        user_tz = pytz.timezone(user.tz)
        current_datetime = pytz.utc.localize(fields.Datetime.now()).astimezone(user_tz)
        data = {
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "date_now": current_datetime,
            "company_id": wizard.company_id,
            "journal_ids": [],
            "p_journals_ids": [],
            "payment_term_ids": [],
            "p_payment_term_ids": [],
            "invoices": {},
            "payments": {},
            "invoice_move_type": [],
        }
        invoice_ids = self.env["account.move"].search(self._get_domain_search_moves(wizard))
        payment_ids = self.env["account.payment"].search(self._get_domain_search_payment(wizard))

        if not invoice_ids and not payment_ids:
            return data

        invoices = defaultdict(lambda: dict())
        payments = defaultdict(lambda: dict())

        journals = []
        p_journals = []
        payment_terms = [{"name": _("Instant payment"), "id": "cash"}]
        invoice_move_types = [
            {"name": _("Invoices"), "type": "out_invoice"},
            {"name": _("Refund"), "type": "out_refund"},
        ]

        for payment in payment_ids:
            journal_id = str(payment.journal_id.id)

            if journal_id not in [x["id"] for x in p_journals]:
                p_journals.append(self.new_journal(payment))

            if not payments.get(journal_id, False):
                payments[journal_id] = payment
            else:
                payments[journal_id] |= payment

            if not payments.get("totals_" + journal_id, False):
                p_journal_totals = {}
            else:
                p_journal_totals = payments["totals_" + journal_id]

            payments["totals_" + journal_id] = self.p_get_new_values(p_journal_totals, payment)

            payments["totals"] = self.p_get_company_values(
                payments.get("totals", {"amount": 0}), payment
            )

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
                term_totals = {}
            else:
                term_totals = invoices[journal_id][invoice.move_type]["totals_" + term_id]

            invoices[journal_id][invoice.move_type]["totals_" + term_id] = self.get_new_values(
                term_totals, invoice
            )

            if not invoices[journal_id].get("totals_" + invoice.move_type, False):
                type_totals = {}
            else:
                type_totals = invoices[journal_id]["totals_" + invoice.move_type]

            invoices[journal_id]["totals_" + invoice.move_type] = self.get_new_values(
                type_totals, invoice
            )

            invoices["totals"] = self.get_company_values(
                invoices.get("totals", initial_amounts), invoice
            )

        data = {
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "date_now": current_datetime,
            "company_id": wizard.company_id,
            "journal_ids": journals,
            "p_journals_ids": p_journals,
            "payment_term_ids": payment_terms,
            "invoices": invoices,
            "payments": payments,
            "invoice_move_type": invoice_move_types,
            "show_documents": wizard.show_documents,
            "self": self,
        }

        return data

    def format_monetary(self, amount, currency):
        return formatLang(self.env, amount, currency_obj=self.env.ref(currency))

    def p_get_new_values(self, totals, payment):
        """Acumula los pagos por moneda: `totals` es {currency_id: montos}."""
        currency = payment.currency_id
        previous = totals.get(currency.id, {"amount": 0})
        amount = previous["amount"] + payment.amount_signed
        return {
            **totals,
            currency.id: {
                "currency_id": currency.id,
                "currency_name": currency.name,
                "amount": amount,
                "formatted_amount": formatLang(self.env, amount, currency_obj=currency),
            },
        }

    def get_new_values(self, totals, invoice):
        """Acumula los totales por moneda del documento: `totals` es {currency_id: montos}."""
        multiply = 1 if invoice.move_type == "out_invoice" else -1
        currency = invoice.currency_id
        previous = totals.get(currency.id, initial_amounts)
        detailed = invoice.detailed_amounts
        gross_amount = previous["gross_amount"] + detailed["gross_amount"] * multiply
        discount_amount = previous["discount_amount"] + detailed["discount_amount"] * multiply
        gross_discount_amount = previous["gross_discount_amount"] + (
            (detailed["gross_amount"] - detailed["discount_amount"]) * multiply
        )
        taxes_amount = previous["taxes_amount"] + detailed["taxes_amount"] * multiply
        total_amount = previous["total_amount"] + (
            invoice.tax_totals["total_amount_currency"] * multiply
        )

        def fmt(amount):
            return formatLang(self.env, amount, currency_obj=currency)

        return {
            **totals,
            currency.id: {
                "currency_id": currency.id,
                "currency_name": currency.name,
                "gross_amount": gross_amount,
                "discount_amount": discount_amount,
                "total_amount": total_amount,
                "gross_discount_amount": gross_discount_amount,
                "taxes_amount": taxes_amount,
                "formatted_gross_amount": fmt(gross_amount),
                "formatted_taxes_amount": fmt(taxes_amount),
                "formatted_gross_discount_amount": fmt(gross_discount_amount),
                "formatted_discount_amount": fmt(discount_amount),
                "formatted_total_amount": fmt(total_amount),
                "total_items": previous["total_items"] + 1,
            },
        }

    def p_get_company_values(self, totals, payment):
        """Total general de pagos en moneda de la compania."""
        amount = totals["amount"] + payment.amount_company_currency_signed
        return {
            "amount": amount,
            "formatted_amount": formatLang(
                self.env, amount, currency_obj=payment.company_id.currency_id
            ),
        }

    def get_company_values(self, totals, invoice):
        """Total general de facturas en moneda de la compania.

        `tax_totals` ya trae el total y los impuestos en moneda de la compania (con la
        tasa de la propia factura); bruto y descuento se llevan a esa moneda con el
        mismo factor.
        """
        multiply = 1 if invoice.move_type == "out_invoice" else -1
        company_currency = invoice.company_id.currency_id
        tax_totals = invoice.tax_totals
        doc_total = tax_totals["total_amount_currency"]
        factor = 1 if float_is_zero(doc_total, precision_digits=6) else (
            tax_totals["total_amount"] / doc_total
        )
        detailed = invoice.detailed_amounts
        gross_amount = totals["gross_amount"] + detailed["gross_amount"] * factor * multiply
        discount_amount = (
            totals["discount_amount"] + detailed["discount_amount"] * factor * multiply
        )
        gross_discount_amount = totals["gross_discount_amount"] + (
            (detailed["gross_amount"] - detailed["discount_amount"]) * factor * multiply
        )
        taxes_amount = totals["taxes_amount"] + tax_totals["tax_amount"] * multiply
        total_amount = totals["total_amount"] + tax_totals["total_amount"] * multiply

        def fmt(amount):
            return formatLang(self.env, amount, currency_obj=company_currency)

        return {
            "gross_amount": gross_amount,
            "discount_amount": discount_amount,
            "total_amount": total_amount,
            "gross_discount_amount": gross_discount_amount,
            "taxes_amount": taxes_amount,
            "formatted_gross_amount": fmt(gross_amount),
            "formatted_taxes_amount": fmt(taxes_amount),
            "formatted_gross_discount_amount": fmt(gross_discount_amount),
            "formatted_discount_amount": fmt(discount_amount),
            "formatted_total_amount": fmt(total_amount),
            "total_items": totals["total_items"] + 1,
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
