from odoo import fields, http, Command
from odoo.http import request
from odoo.osv import expression
from odoo.exceptions import ValidationError


from datetime import datetime, timedelta
from ..utils.utils_retention import load_retention_lines
from collections import defaultdict

import traceback


import json
import base64
import logging

_logger = logging.getLogger(__name__)


class AccountPaymentPayments(http.Controller):
    FIELDNAMES = ["id", "name", "journal_id", "amount", "date", "ref", "partner_id", "state"]
    FIELDFILTERS = ["id", "partner_id", "journal_id"]

    @http.route(
        "/payments/register_payment",
        type="json",
        methods=["POST"],
        auth="public",
        website=False,
        sitemap=False,
    )
    def register_account_payment(
        self,
        use_credit=False,
        dairy_type=False,
        invoices=False,
        payments=False,
        partner_id=False,
        **kwargs
    ):
        """
        Here the payments compiled by the seller in the APP
        are recorded and thus create the record of the payments and
        reconcile with the invoice, in addition, this will feed the
        payment master of the sellers app and also record the withholdings, igtf generated

        Args:
            use_credit (bool, ): Use use of customer advances. Defaults to False.
            dairy_type (int, ): id of the journal type selected by the seller . Defaults to False.
            invoices (dic, ): id from invoices selected for the Seller. Defaults to False.
            payments (dic, ): Dic with all dictionary with all the payment information added by qweb.
                              Defaults to False.
            partner_id (int, ): id of the partner selected. Defaults to False.

        Returns:
            dic: result of the function
        """
        data = {"status": 200, "msg": "Success"}

        file = kwargs.get("file", False)
        file2 = kwargs.get("file", False)

        if invoices and payments and partner_id or invoices and use_credit and partner_id:
            partner_id = int(partner_id)
            invoices_id = []
            for invoice in invoices:
                invoice_id = int(invoices[invoice]["idInvoice"])
                invoices_id.append(invoice_id)

            company = request.env.company
            order_options = {"0": "create_date asc", "1": "amount_residual desc"}

            order_invoices = order_options.get(company.order_payment, "create_date asc")

            data_invoices = (
                request.env["account.move"]
                .sudo()
                .search([("id", "in", invoices_id)], order=order_invoices)
            )

            ctx = {"active_model": "account.move", "active_ids": data_invoices.ids}

            try:
                type_fiscal = (
                    request.env["account.journal"]
                    .sudo()
                    .search([("id", "=", int(dairy_type))])
                    .fiscal
                )
                partner = (
                    request.env["res.partner"]
                    .sudo()
                    .search([("id", "=", int(partner_id))])
                )
                taxpayer = partner.taxpayer_type
                seller_id = request.env.user.employee_id.id
                payments_igtf = request.env["payment.mobile.igtf"]
                pays_registered = request.env["account.payment"]
                pays_retention_registered = pays_registered
                advance_pays = pays_registered
                module_advance_payment = (
                    request.env["ir.module.module"]
                    .sudo()
                    .search([("name", "ilike", "binaural_advance_payment")], limit=1)
                )
                advance_payment_installed = module_advance_payment.state == "installed"
                advance_account_customer_ids = False

                module_igtf = (
                    request.env["ir.module.module"]
                    .sudo()
                    .search([("name", "ilike", "binaural_igtf")])
                )
                igtf_installed = module_igtf.state == "installed"

                if advance_payment_installed:
                    advance_account_customer_ids = [company.advance_customer_account_id.id]
                    if igtf_installed:
                        advance_account_customer_ids.append(company.customer_account_igtf_id.id)

                if type_fiscal and taxpayer != "ordinary":
                    retentions, pays_retention_registered = self.register_retentions(
                        data_invoices, partner_id, company, pays_retention_registered
                    )

                pays_app_register = request.env["payment.mobile"]

                if use_credit:
                    if advance_payment_installed:
                        invoices = (
                            data_invoices.mapped("line_ids")
                            .filtered(lambda l: l.account_id.account_type == "asset_receivable")
                            .sorted(lambda l: l.date_maturity)
                        )
                        domain_customer = [
                            ("partner_id", "=", int(partner_id)),
                            ("account_id", "in", advance_account_customer_ids),
                            ("move_id.state", "=", "posted"),
                        ]

                        advance_lines = request.env["account.move.line"].search(domain_customer)

                        for invoice in invoices:
                            total_residual = 0
                            for payment in advance_lines:
                                total_residual = payment.amount_residual
                                if total_residual < 0 and invoice.amount_residual != 0:
                                    (payment + invoice).sudo().reconcile(from_app=True)
                                    advance_pays += payment.move_id.payment_id

                if payments:
                    pays_registered, payments_igtf = self.register_payments(
                        payments,
                        ctx,
                        company,
                        data_invoices,
                        seller_id,
                        type_fiscal,
                        igtf_installed,
                    )
                pays_registered += pays_retention_registered
                pays_registered += advance_pays

                _logger.warning(pays_registered)


                pays_app_methods = request.env["payment.mobile.methods"]
                pays_app_lines = request.env["payment.mobile.line"]

                for pay_r in pays_registered:
                    for invoice in data_invoices:
                        if invoice.id in pay_r.reconciled_invoice_ids.ids:
                            pays_app_lines += self.create_line_app(
                                pay_r, invoice, company, advance_account_customer_ids
                            )

                        if advance_payment_installed and pay_r.is_advance_payment:
                            for line in pay_r.move_id.line_ids:
                                line_id = line.filtered(
                                    lambda line: line.account_id.account_type == "liability_current"
                                )
                                domain = [("credit_move_id", "=", line_id.id)]
                                domain = expression.OR(
                                    [domain, [("debit_move_id", "=", line_id.id)]]
                                )
                                reconcile = request.env["account.partial.reconcile"].search(domain)
                                for invoice_ids in reconcile:
                                    invoice_id = invoice_ids.debit_move_id.move_id
                                    if line_id and invoice == invoice_id:
                                        pays_app_lines += self.create_line_app(
                                            pay_r, invoice_id, company, advance_account_customer_ids
                                        )
                            
                    pays_app_method = request.env["payment.mobile.methods"].create(
                        {
                            "journal_id": pay_r.journal_id.id,
                            "currency_id": company.currency_id.id,
                            "residual_payment": pay_r.id,
                        }
                    )

                    pays_app_methods += pays_app_method

                payment_app = pays_app_register.create(
                    {
                        "partner_id": partner_id,
                        "seller_id": seller_id,
                        "seller_id_user": request.env.user.id,
                        "payment_mobile_methods": pays_app_methods,
                        "payment_mobile_line": pays_app_lines,
                        "proof_payment_id": file,
                        "proof_payment_domain": file2,
                        "is_fiscal": type_fiscal,
                        "state": "process",
                    }
                )

                if len(payments_igtf) > 0:
                    for line in payment_app.payment_mobile_line:
                        for igtf in payments_igtf:
                            if line.payment_related.id == igtf.payment_id.id:
                                igtf.write(
                                    {
                                        "payment_mobile_id": line.payment_mobile_id.id,
                                    }
                                )

                if (type_fiscal and taxpayer != "ordinary"):
                    if company.retentions_draft_or_published == "0" and retentions:
                        for retention in retentions:
                            retention.sudo().action_cancel()
                            retention.sudo().action_draft()

            except Exception as e:
                data.update({"status": 400, "msg": str(e)})
                _logger.warning(traceback.format_exc())
        else:
            data.update({"status": 400, "msg": "Faltan parametros de registro"})
        return data

    def register_retentions(self, data_invoices, partner_id, company, pays_retention_registered):
        retentions = request.env["account.retention"]
        today_one = fields.Date.today() + timedelta(days=1)
        retention_percentage = company.condition_withholding_id.value / 100

        for data_invoice in data_invoices:
            invoice_with_tax = False
            for line in data_invoice.line_ids:
                if line.tax_ids:
                    if line.tax_ids[0].amount > 0:
                        invoice_with_tax = True

            if invoice_with_tax:
                register_retention = (
                    request.env["account.retention"]
                    .sudo()
                    .create(
                        {
                            "type": "out_invoice",
                            "partner_id": int(partner_id),
                            "date_accounting": today_one,
                            "number": "/",
                            "date": today_one,
                            "state": "draft",
                            "company_id": company.id,
                            "type_retention": "iva",
                        }
                    )
                )
                invoice_retention = data_invoice.filtered(
                    lambda i: not any(
                        i.retention_iva_line_ids.filtered(lambda l: l.state in ("draft", "emitted"))
                    )
                )

                lines = load_retention_lines(invoice_retention, register_retention)

                if lines:
                    lines_per_invoice_counter = defaultdict(int)

                    for line in lines:
                        line[2]["foreign_retention_amount"] = (
                            line[2]["foreign_iva_amount"] * retention_percentage
                        )
                        line[2]["retention_amount"] = line[2]["iva_amount"] * retention_percentage
                        lines_per_invoice_counter[str(line[2]["move_id"])] += 1

                    register_retention.update(
                        {
                            "retention_line_ids": lines,
                            "original_lines_per_invoice_counter": json.dumps(
                                lines_per_invoice_counter
                            ),
                        }
                    )
                    register_retention.action_post()
                    for payment in register_retention.payment_ids:

                        pays_retention_registered += payment

                    retentions += register_retention
                else:
                    register_retention.sudo().unlink()

        return retentions, pays_retention_registered

    def register_payments(
        self, payments, ctx, company, data_invoices, seller_id, fiscal, igtf_installed
    ):
        pays_registered = request.env["account.payment"]
        currency_vef_id = request.env.company.currency_foreign_id.id
        payments_igtf = request.env["payment.mobile.igtf"]

        for payment in payments:
            pay_day = payments[payment]["dateToPay"]
            pay_day_formatted = datetime.strptime(pay_day, "%Y-%m-%d")
            payment_register = (
                request.env["account.payment.register"]
                .sudo()
                .with_context(**ctx)
                .create(
                    {
                        "amount": payments[payment]["paymentAmount"],
                        "journal_id": int(payments[payment]["idDairy"]),
                        "payment_date": pay_day_formatted,
                        "communication": payments[payment]["reference"],
                    }
                )
            )

            batches = payment_register._get_batches()
            first_batch_result = batches[0]
            payment_vals = payment_register._create_payment_vals_from_wizard(first_batch_result)

            currency_id = request.env["res.currency.rate"].search(
                [
                    ("currency_id", "=", currency_vef_id),
                    ("name", "<=", pay_day_formatted),
                    ("company_id", "=", company.id),
                ],
                order="name desc",
                limit=1,
            )

            payment_vals.update(
                {
                    "company_id": company.id,
                    "payment_type": "inbound",
                    "user_id": request.env.user.id,
                    "payment_method_id": request.env.ref(
                        "account.account_payment_method_manual_in"
                    ).id,
                    "foreign_rate": currency_id.company_rate,
                    "foreign_inverse_rate": currency_id.company_rate,
                    "payment_from_app": True,
                }
            )

            payment_create = request.env["account.payment"].sudo().create(payment_vals)
            payment_create.action_post()
            if igtf_installed:
                payments_igtf += self.register_payment_with_igtf(
                    payment_create, payments[payment]["igtf_amount"], seller_id, fiscal
                )

            pays_registered += payment_create

        invoices = (
            data_invoices.mapped("line_ids")
            .filtered(lambda l: l.account_id.account_type == "asset_receivable")
            .sorted(lambda l: l.date_maturity)
        )
        pays = pays_registered.mapped("move_id.line_ids").filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        for invoice in invoices:
            total_residual = 0
            for payment in pays:
                total_residual += payment.amount_residual

            if total_residual < 0:
                (pays + invoice).sudo().reconcile(from_app=True)

        return pays_registered, payments_igtf

    def register_payment_with_igtf(self, rec_payment, amount_igtf, seller_id, fiscal):
        payment_igtf = request.env["payment.mobile.igtf"]
        if rec_payment.currency_id.symbol == "$" and fiscal and rec_payment.journal_id.is_igtf:
            payment_igtf = payment_igtf.create(
                {
                    "payment_id": rec_payment.id,
                    "amount_igtf": float(amount_igtf),
                    "seller_id": seller_id,
                }
            )
        return payment_igtf

    def create_line_app(self, payment, invoice, company, advance):
        pays_app_line = request.env["payment.mobile.line"].create(
            {
                "name": payment.name,
                "currency_id": company.currency_id.id,
                "invoice_id": invoice.id,
                "payment_related": payment.id,
                "use_balance": True
                if advance and payment.destination_account_id.id in advance
                else False,
            }
        )
        return pays_app_line

    @http.route("/upload_attachment", type="json", auth="public", methods=["POST"], website=True)
    def upload_attachment(self, **kw):
        data = {"status": 200, "msg": "Success"}
        base64 = kw["attachments"]
        if not base64:
            data.update({"status": 400, "msg": "the file was not sent"})
            return data
        attach = base64.strip("data:application/pdf;base64")
        attachment = request.env["payment.mobile.proof"].create(
            {
                "name": kw["attachment_name"],
                "proof_file": attach,
            }
        )

        data.update({"data": attachment.id})
        return data

    @http.route("/delete_attachment", type="json", auth="public", methods=["POST"], website=True)
    def delete_attachment(self, attach_id, **kw):
        data = {"status": 200, "msg": "Success"}
        if not attach_id:
            data.update({"status": 400, "msg": "the file was not sent"})
            return data
        int(attach_id)
        file = request.env["payment.mobile.proof"].search([("id", "=", attach_id)])
        file.unlink()
        return data

    @http.route(
        "/payment_total_or_partial", type="json", auth="public", methods=["POST"], website=True
    )
    def payment_total_or_partial(self, **kw):
        data = {"status": 200, "msg": "Success"}
        total_or_partial = request.env.company.process_payments_invoices
        data.update({"data": total_or_partial})
        return data

    @http.route("/installment_payments", type="json", auth="public", methods=["POST"], website=True)
    def installment_payments(self, **kw):
        data = {"status": 200, "msg": "Success"}
        installment_payments = request.env.company.allow_installment_payments
        data.update({"data": installment_payments})
        return data