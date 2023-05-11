from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from datetime import date

import logging

_logger = logging.getLogger(__name__)


class AdvancePaymentReport(models.TransientModel):
    _name = "advance.payment.report"
    _description = "Advance Payment Report"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    report_type = fields.Selection(
        [
            ("customer", "Customer"),
            ("supplier", "Supplier"),
        ],
        required=True,
    )

    payment_type = fields.Selection(
        [
            ("advance", "Advance"),
            ("payment", "Payment"),
        ],
    )

    residual_type = fields.Selection(
        [
            ("all", "All"),
            ("residual", "Residual"),
            ("not_residual", "Not Residual"),
        ],
        required=True,
    )

    all_partner = fields.Boolean(default=True)

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
    )

    at_today = fields.Boolean(default=True)

    start_date = fields.Date(string="From", default=date.today().replace(day=1))

    end_date = fields.Date(
        string="To", default=date.today().replace(day=1) + relativedelta(months=1, days=-1)
    )

    @api.onchange("all_partner")
    def _onchange_all_partner(self):
        domain = []
        if not self.all_partner:
            # print("es un partner especifico, retornar domain")
            if self.report_type == "supplier":
                domain = [("supplier_rank", ">", 0), ("active", "=", True)]
            else:
                domain = [("customer_rank", ">", 0), ("active", "=", True)]

        _logger.warning("domain %s", domain)
        return {
            "domain": {
                "partner_id": domain,
            }
        }

    def print_pdf_payments(self):
        if not self.report_type:
            raise UserError(_("Report type is required"))
        if not self.payment_type:
            raise UserError(_("Payment type is required"))
        if not self.all_partner and not self.partner_id:
            raise UserError(_("Partner is required"))
        if not self.at_today:
            if not self.start_date or not self.end_date:
                raise UserError(_("Start date and end date are required"))
        if self.at_today:
            self.end_date = fields.Date.today()

        data = {
            "form": {
                "residual_type": self.residual_type,
                "report_type": self.report_type,
                "payment_type": self.payment_type,
                "all_partner": self.all_partner,
                "partner_id": self.partner_id.id,
                "at_today": self.at_today,
                "start_date": self.start_date,
                "end_date": self.end_date,
            }
        }
        return (
            self.env.ref("binaural_advance_payment.action_report_advance_payment_report")
            .with_context(landscape=True)
            .report_action(self, data=data)
        )

    def generate_report(self, partner):
        _logger.warning("partner al principio %s", partner)
        search_domain = []
        if self.report_type and self.report_type == "supplier":
            search_domain += [("payment_type", "=", "outbound")]
        else:
            search_domain += [("payment_type", "=", "inbound")]

        if self.payment_type and self.payment_type == "advance":
            search_domain += [("is_advance_payment", "=", True)]
        elif self.payment_type and self.payment_type == "payment":
            search_domain += [("is_advance_payment", "=", False)]
        # elif self.type_payment and self.type_payment == 'is_expense':
        # search_domain += [('is_expense','=',True)]

        if self.at_today:
            search_domain += [("date", "<=", fields.Date.today())]
        else:
            search_domain += [("date", "<=", self.end_date), ("date", ">=", self.start_date)]
        if partner:
            _logger.warning("HAY PARTNER %s", partner)
            search_domain += [("partner_id", "=", partner.id)]
        search_domain += [("state", "=", "posted")]

        _logger.warning("search_domain %s", search_domain)

        payments = self.env["account.payment"].sudo().search(search_domain)

        if self.residual_type != 'all':
            new_payments = []
            for p in payments:
                acum = self.get_residual_by_payment(p)
                if(acum == 0 and self.residual_type == 'not_residual') or (acum != 0 and self.residual_type == 'residual'):
                    new_payments.append(p)
            return new_payments

        return payments

    def get_residual_by_payment(self,p):
        acum = 0
        if p:
            domain = [('partner_id', '=', self.env['res.partner']._find_accounting_partner(p.partner_id).id),
                      ('reconciled', '=', False),
                      ('move_id.state', '=', 'posted'),
                      '|',
                        '&', ('amount_residual_currency', '!=', 0.0), ('currency_id','!=', None),
                        '&', ('amount_residual_currency', '=', 0.0), '&', ('currency_id','=', None), ('amount_residual', '!=', 0.0)]
            if self.report_type == 'customer':

                domain.extend([('credit', '>', 0), ('debit', '=', 0)])
                
            else:

                domain.extend([('credit', '=', 0), ('debit', '>', 0)])

            lines = self.env['account.move.line'].search(domain)

            if len(lines) != 0:
                for line in lines:
                    if line.payment_id.id == p.id:
                        acum += abs(line.amount_residual)
        return acum