# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
import logging
import time

from datetime import datetime,timedelta
from odoo import models, fields, api,_
from odoo.exceptions import UserError
from .. import shopify
from ..shopify.pyactiveresource.connection import ClientError

_logger = logging.getLogger('Shopify Payout')


class ShopifyPaymentReportEpt(models.Model):
    _name = "shopify.payout.report.ept"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Shopify Payout Report"
    _order = 'id desc'

    name = fields.Char(size=256)
    instance_id = fields.Many2one('shopify.instance.ept', string="Instance")
    payout_reference_id = fields.Char(string="Payout Reference ID",
                                      help="The unique identifier of the payout")
    payout_date = fields.Date(help="The date the payout was issued.")
    payout_transaction_ids = fields.One2many('shopify.payout.report.line.ept', 'payout_id',
                                             string="Payout transaction lines")
    common_log_line_ids = fields.One2many("common.log.lines.ept",'shopify_payout_report_line_id', string="Log Lines")
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  help="currency code of the payout.")
    amount = fields.Float(string="Total Amount", help="The total amount of the payout.")
    statement_id = fields.Many2one('account.bank.statement', string="Bank Statement")
    payout_status = fields.Selection([('scheduled', 'Scheduled'), ('in_transit', 'In Transit'), ('paid', 'Paid'),
                                      ('failed', 'Failed'), ('cancelled', 'Cancelled')],
                                     help="The transfer status of the payout. The value will be one of the following\n"
                                          "- Scheduled:  The payout has been created and had transactions assigned to"
                                          "it, but it has not yet been submitted to the bank\n"
                                          "- In Transit: The payout has been submitted to the bank for processing.\n"
                                          "- Paid: The payout has been successfully deposited into the bank.\n"
                                          "- Failed: The payout has been declined by the bank.\n"
                                          "- Cancelled: The payout has been canceled by Shopify")
    state = fields.Selection([('draft', 'Draft'), ('partially_generated', 'Partially Generated'),
                              ('generated', 'Generated'), ('partially_processed', 'Partially Processed'),
                              ('processed', 'Processed'), ('validated', 'Validated')], string="Status",
                             default="draft", tracking=True)
    is_skip_from_cron = fields.Boolean(string="Skip From Schedule Actions", default=False)

    def get_payout_report(self, start_date, end_date, instance):
        """
        This method is used to import Payout reports and create record in Odoo.
        @param start_date:From Date(year-month-day)
        @param end_date: To Date(year-month-day)
        @param instance: Browsable shopify instance.
        @author: Maulik Barad on Date 27-Nov-2020.
        """
        log_line_obj = self.env['common.log.lines.ept']

        instance.connect_in_shopify()
        _logger.info("Import Payout Reports....")
        try:
            payout_reports = shopify.Payouts().find(status="paid", date_min=start_date, date_max=end_date, limit=250)
        except Exception as error:
            message = "Something is wrong while import the payout records : {0}".format(error)
            log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id,module="shopify_ept",
                                                    message=message,
                                                    model_name=self._name)
            _logger.info(message)
            return False

        payouts = self.create_payout_reports(payout_reports, instance)
        payouts = payouts.sorted(key=lambda x: x.id, reverse=True)

        self._cr.commit()
        _logger.info("Payout Reports are Created. Generating Bank statements...")
        for payout in payouts:
            payout.generate_bank_statement()

        instance.write({'payout_last_import_date': end_date})
        _logger.info("Payout Reports are Imported.")
        return True

    def create_payout_reports(self, payout_reports, instance):
        """
        This method is used to create records of Payout report from the data.
        @param instance: Record of the Instance.
        @param payout_reports: List of Payout reports.
        @author: Maulik Barad on Date 03-Dec-2020.
        """
        payouts = self
        for payout_report in payout_reports:
            payout_data = payout_report.to_dict()
            payout_id = payout_data.get('id')
            payout = self.search([('instance_id', '=', instance.id),
                                  ('payout_reference_id', '=', payout_id)])
            if payout:
                _logger.info("Existing Payout Report found for %s.", payout_id)
                payouts += payout
                continue
            payout_vals = self.prepare_payout_vals(payout_data, instance)
            payout = self.create(payout_vals)

            if not payout:
                continue
            payouts += payout
            _logger.info("Payout Report created for %s. Importing Transaction lines..", payout_id)
            payout.create_payout_transaction_lines(payout_data)

        return payouts

    def create_payout_transaction_lines(self, payout_data):
        """
        Gets Payout Transactions and creates transaction lines from that.
        @param payout_data: Data of the payout.
        @author: Maulik Barad on Date 03-Dec-2020.
        """
        shopify_payout_report_line_obj = self.env['shopify.payout.report.line.ept']

        transaction_all = shopify.Transactions().find(payout_id=self.payout_reference_id, limit=250)
        if len(transaction_all) == 250:
            transaction_all = self.shopify_list_all_transactions(transaction_all)
        for transaction in transaction_all:
            transaction_data = transaction.to_dict()
            transaction_vals = self.prepare_transaction_vals(transaction_data, self.instance_id)
            shopify_payout_report_line_obj.create(transaction_vals)

        # Create fees line
        fees_amount = float(payout_data.get('summary').get('charges_fee_amount', 0.0)) + float(
            payout_data.get('summary').get('refunds_fee_amount', 0.0)) + float(
            payout_data.get('summary').get('adjustments_fee_amount', 0.0))
        shopify_payout_report_line_obj.create({
            'payout_id': self.id or False,
            'transaction_type': 'fees',
            'amount': -fees_amount,
            'fee': 0.0,
            'net_amount': fees_amount,
        })
        _logger.info("Transaction lines are added for %s.", self.payout_reference_id)
        return True

    def shopify_list_all_transactions(self, result):
        """
           This method used to call the page wise data import for payout report transactions from Shopify to Odoo.
           @param : self, result
           @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 15/02/2022.
       """
        transactions_list = []
        catch = ""
        while result:
            link = shopify.ShopifyResource.connection.response.headers.get(
                "Link") if shopify.ShopifyResource.connection.response.headers.get(
                "Link") else shopify.ShopifyResource.connection.response.headers.get("link")
            if not link or not isinstance(link, str):
                return transactions_list
            page_info = ""
            transactions_list += result
            for page_link in link.split(","):
                if page_link.find("next") > 0:
                    page_info = page_link.split(";")[0].strip("<>").split("page_info=")[1]
                    try:
                        result = shopify.Transactions().find(page_info=page_info, limit=250)
                    except ClientError as error:
                        if hasattr(error, "response"):
                            if error.response.code == 429 and error.response.msg == "Too Many Requests":
                                time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                                result = shopify.Transactions().find(page_info=page_info, limit=250)
                    except Exception as error:
                        raise UserError(error)
            if catch == page_info:
                break
        return transactions_list

    def prepare_transaction_vals(self, data, instance):
        """
        Use : Based on transaction data prepare transaction vals.
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        :param data: Transaction data in dict{}.
        :param instance: Browsable record of instance.
        :return: Payout vals{}
        """
        currency_obj = self.env['res.currency']
        sale_order_obj = self.env['sale.order']
        transaction_id = data.get('id', '')
        source_order_id = data.get('source_order_id', '')
        transaction_type = data.get('type', '')
        amount = data.get('amount', 0.0)
        fee = data.get('fee', 0.0)
        net_amount = data.get('net', 0.0)
        currency = data.get('currency', '')

        order_id = False
        if source_order_id:
            order_id = sale_order_obj.search([('shopify_order_id', '=', source_order_id),
                                              ('shopify_instance_id', '=', instance.id)],
                                             limit=1)

        transaction_vals = {
            'payout_id': self.id or False,
            'transaction_id': transaction_id,
            'source_order_id': source_order_id,
            'transaction_type': transaction_type,
            'order_id': order_id and order_id.id,
            'amount': amount,
            'fee': fee,
            'net_amount': net_amount,
        }

        currency_id = currency_obj.search([('name', '=', currency)], limit=1)
        if currency_id:
            transaction_vals.update({'currency_id': currency_id.id})

        return transaction_vals

    def shopify_view_bank_statement(self):
        """
        @author: Ekta Bhut , 9th March 2021
        This function is used to show generated bank statement from process of settlement report
        """
        self.ensure_one()
        res = self.statement_id.action_open_bank_reconcile_widget()
        return res

    def prepare_payout_vals(self, data, instance):
        """
        Use : Based on payout data prepare payout vals.
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        :param data: Payout data in dict{}.
        :param instance: Browsable record of instance.
        :return: Payout vals{}
        """
        currency_obj = self.env['res.currency']
        payout_reference_id = data.get('id')
        payout_date = data.get('date', '')
        payout_status = data.get('status', '')
        currency = data.get('currency', '')
        amount = data.get('amount', 0.0)

        payout_vals = {
            'payout_reference_id': payout_reference_id,
            'payout_date': payout_date,
            'payout_status': payout_status,
            'amount': amount,
            'instance_id': instance.id
        }
        currency_id = currency_obj.search([('name', '=', currency)], limit=1)
        if currency_id:
            payout_vals.update({'currency_id': currency_id.id})
        return payout_vals

    def check_process_statement(self):
        """
        Use : Using this method visible/Invisible the statement execution button.
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        """
        all_statement_processed = True
        if self.payout_transaction_ids and any(line.is_remaining_statement for line in self.payout_transaction_ids):
            all_statement_processed = False
        return all_statement_processed

    def generate_bank_statement(self):
        """
        Use : Using this method user can able to create bank statement.
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        :return: True
        """
        bank_statement_obj = self.env['account.bank.statement']
        journal = self.check_journal_and_currency()
        if not journal:
            return False

        payout_reference_id = self.payout_reference_id
        bank_statement_exist = bank_statement_obj.search([('shopify_payout_ref', '=', payout_reference_id)], limit=1)
        if bank_statement_exist:
            self.write({'statement_id': bank_statement_exist.id})
            self.is_skip_from_cron = False
            return True

        name = '{0}_{1}'.format(self.instance_id.name, payout_reference_id)
        vals = {
            'shopify_payout_ref': payout_reference_id,
            'journal_id': journal.id,
            'name': name,
            'date': self.payout_date,
            'balance_start': 0.0,
            'balance_end_real': 0.0
        }
        bank_statement_id = bank_statement_obj.create(vals)
        _logger.info("Bank Statement Generated for Shopify Payout : %s.", payout_reference_id)
        self.create_bank_statement_lines_for_payout_report(bank_statement_id)

        if self.check_process_statement():
            state = 'generated'
        else:
            state = 'partially_generated'

        _logger.info("Lines are added in Bank Statement %s.", name)
        self.write({'statement_id': bank_statement_id.id, 'state': state, "is_skip_from_cron": False})

        return True

    def create_bank_statement_lines_for_payout_report(self, bank_statement_id, regenerate=False):
        """
        This method creates bank statement lines from the transaction lines of Payout report.
        @param bank_statement_id: New created Bank statement record.
        @param regenerate: If method is called for regenerating the Bank statement.
        @author: Maulik Barad on Date 02-Dec-2020.
        """
        partner_obj = self.env['res.partner']
        bank_statement_line_obj = self.env['account.bank.statement.line']
        log_lines = []
        account_payment_obj = self.env['account.payment']
        sale_order_obj = self.env["sale.order"]

        transaction_ids = self.payout_transaction_ids
        if regenerate:
            transaction_ids = self.payout_transaction_ids.filtered(lambda line: line.is_remaining_statement)
        for transaction in transaction_ids:
            order_id = transaction.order_id
            if transaction.transaction_type in ['charge', 'refund', 'payment_refund'] and not order_id:
                source_order_id = transaction.source_order_id
                order_id = sale_order_obj.search([('shopify_order_id', '=', source_order_id),
                                                  ('shopify_instance_id', '=', self.instance_id.id)],
                                                 limit=1)
                if order_id:
                    transaction.order_id = order_id
                else:
                    message = "Transaction line {0} will not automatically reconcile due to " \
                              "order {1} is not found in odoo.".format(
                        transaction.transaction_id, transaction.source_order_id)
                    log_lines.append({'message': message,
                                      'shopify_payout_report_line_id': transaction.id})
                    # We can not use shopify order reference here because it may create duplicate name,
                    # and name of journal entry should be unique per company. So here I have used transaction Id
                    bank_line_vals = {
                        # 'name': transaction.transaction_id,
                        'payment_ref': transaction.transaction_id,
                        'date': self.payout_date,
                        'amount': transaction.amount,
                        'statement_id': bank_statement_id.id,
                        'shopify_transaction_id': transaction.transaction_id,
                        "shopify_transaction_type": transaction.transaction_type,
                        'sequence': 1000,
                        'journal_id' : self.instance_id.shopify_settlement_report_journal_id.id
                    }
                    bank_statement_line_obj.create(bank_line_vals)
                    transaction.is_remaining_statement = False
                    continue

            partner = partner_obj._find_accounting_partner(order_id.partner_id)
            domain, invoice, log_line = self.check_for_invoice_refund(transaction, log_lines)

            if domain:
                payment_reference = account_payment_obj.search(domain, limit=1)

                if payment_reference:
                    reference = payment_reference.name
                    # if not regenerate:
                    #     payment_aml_rec = payment_reference.line_ids.filtered(
                    #         lambda line: line.account_internal_type == "liquidity")
                    #     reconciled, log_line = self.check_reconciled_transactions(transaction, log_lines,
                    #                                                               payment_aml_rec)
                    #     if reconciled:
                    #         # log_lines += log_line
                    #         continue
                else:
                    reference = invoice.name or ''
            else:
                # log_lines += log_line
                reference = transaction.order_id.name

            if transaction.amount:
                name = False
                if transaction.transaction_type not in ['charge', 'refund', 'payment_refund']:
                    reference = transaction.transaction_type + "/"
                    if transaction.transaction_id:
                        reference += transaction.transaction_id
                    else:
                        reference += self.payout_reference_id
                else:
                    if order_id.name:
                        name = transaction.transaction_type + "_" + order_id.name + "/" + transaction.transaction_id
                counter_part_account_id = self.instance_id.transaction_line_ids.filtered(lambda l :l.transaction_type
                                                                                                   ==
                                                                                                   transaction.transaction_type).account_id
                bank_line_vals = {
                    # 'name': name or reference,
                    'payment_ref': name or reference,
                    'date': self.payout_date,
                    'partner_id': partner and partner.id,
                    'amount': transaction.amount,
                    'statement_id': bank_statement_id.id,
                    'sale_order_id': order_id.id,
                    'shopify_transaction_id': transaction.transaction_id,
                    "shopify_transaction_type": transaction.transaction_type,
                    'sequence': 1000,
                    'journal_id' :  self.instance_id.shopify_settlement_report_journal_id.id,
                    'counterpart_account_id' : counter_part_account_id.id

                }
                if invoice and invoice.move_type == "out_refund":
                    bank_line_vals.update({"refund_invoice_id": invoice.id})
                bank_statement_line_obj.create(bank_line_vals)
                if regenerate:
                    transaction.is_remaining_statement = False

        if log_lines:
            self.set_payout_log_line(log_lines)

            note = "Bank statement lines are generated but will not reconcile automatically for Transaction IDs : "
            for log_line in self.common_log_line_ids:
                note += str(log_line.shopify_payout_report_line_id.transaction_id) + ", "
            self.message_post(body=note)

            if self.instance_id.is_shopify_create_schedule:
                self.common_log_line_ids.create_payout_schedule_activity(note, self)
        return True

    def check_for_invoice_refund(self, transaction, log_lines):
        """
        This method is used to search for invoice or refund and then prepare domain as that..
        @param transaction: record of the transaction line.
        @author: Maulik Barad on Date 03-Dec-2020.
        """
        invoice_ids = self.env["account.move"]
        domain = []
        order_id = transaction.order_id

        if transaction.transaction_type == 'charge':
            invoice_ids = order_id.invoice_ids.filtered(lambda x:
                                                        x.state == 'posted' and x.move_type == 'out_invoice' and
                                                        x.amount_total == transaction.amount)
            if not invoice_ids:
                message = "Invoice amount is not matched for order %s in odoo" % \
                          (order_id.name or transaction.source_order_id)
                log_lines.append({'message': message,
                                  'shopify_payout_report_line_id': transaction.id})
                return domain, invoice_ids, log_lines
            domain += [('amount', '=', transaction.amount), ('payment_type', '=', 'inbound')]
        elif transaction.transaction_type in ['refund', 'payment_refund']:
            invoice_ids = order_id.invoice_ids.filtered(lambda x:
                                                        x.state == 'posted' and x.move_type == 'out_refund' and
                                                        x.amount_total == -transaction.amount)
            if not invoice_ids:
                shopify_instance = order_id.shopify_instance_id
                shopify_instance.connect_in_shopify()
                shopify_order = shopify.Order().find(order_id.shopify_order_id)
                orders_data = shopify_order.to_dict()
                shopify_order_status = orders_data.get("financial_status")
                if shopify_order_status in ["refunded", "partially_refunded"] and orders_data.get("refunds"):
                    created_by = 'import'
                    queue_line = self.env["shopify.order.data.queue.line.ept"]
                    order_id.process_order_refund_data_ept(shopify_order_status, orders_data, order_id, created_by,
                                                           shopify_instance, queue_line)
                invoice_ids = order_id.invoice_ids.filtered(lambda x:
                                                            x.state == 'posted' and x.move_type == 'out_refund' and
                                                            x.amount_total == -transaction.amount)
            if not invoice_ids:
                message = "In Shopify Payout, there is a Refund, but Refund amount is not matched for order %s in" \
                          "odoo" % (order_id.name or transaction.source_order_id)
                log_lines.append({'message': message,
                                  'shopify_payout_report_line_id': transaction.id})
                return domain, invoice_ids, log_lines
            domain += [('amount', '=', -transaction.amount), ('payment_type', '=', 'outbound')]

        domain.append(('ref', 'in', invoice_ids.mapped("payment_reference")))
        return domain, invoice_ids, log_lines

    def check_journal_and_currency(self):
        """
        This method checks for configured journal and its currency.
        @author: Maulik Barad on Date 02-Dec-2020.
        """
        journal = self.instance_id.shopify_settlement_report_journal_id
        if not journal:
            message_body = "You have not configured Payout report Journal in Instance. Please configure it in Settings."
            if self._context.get('cron_process'):
                self.message_post(body=_(message_body))
                self.is_skip_from_cron = True
                return False
            raise UserError(_(message_body))

        currency_id = journal.currency_id.id or self.instance_id.shopify_company_id.currency_id.id or False
        if currency_id != self.currency_id.id:
            message_body = "The Report currency and currency in Journal/Instance are different." \
                           "\nMake sure the Report currency and the Journal/Instance currency must be same."
            self.message_post(body=_(message_body))
            raise UserError(_(message_body))
        return journal

    def check_reconciled_transactions(self, transaction, log_lines, aml_rec=False):
        """
        This method is used to check if the transaction line already reconciled or not.
        @param transaction: Record of the transaction.
        @param aml_rec: Record of move line.
        """
        reconciled = False
        if aml_rec and aml_rec.statement_id:
            message = 'Transaction line %s is already reconciled.' % transaction.transaction_id
            log_lines.append({'message': message,
                              'shopify_payout_report_line_id': transaction.id})
            reconciled = True
        return reconciled, log_lines

    def generate_remaining_bank_statement(self):
        """
        Use : Using this method user can able create remaining bank statement.
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        :return: True
        """
        self.create_bank_statement_lines_for_payout_report(self.statement_id, regenerate=True)

        if self.check_process_statement():
            state = 'generated'
        else:
            state = 'partially_generated'
        self.write({'state': state})
        return True

    def convert_move_amount_currency(self, bank_statement, moveline, amount, date):
        """
        This method converts amount of moveline to bank statement's currency.
        @param date:
        @param bank_statement:
        @param moveline:
        @param amount:
        """
        amount_currency = 0.0
        if moveline.company_id.currency_id.id != bank_statement.currency_id.id:
            amount_currency = moveline.currency_id._convert(moveline.amount_currency,
                                                            bank_statement.currency_id,
                                                            bank_statement.company_id,
                                                            date)
        elif (
                moveline.move_id and moveline.move_id.currency_id.id != bank_statement.currency_id.id):
            amount_currency = moveline.move_id.currency_id._convert(amount,
                                                                    bank_statement.currency_id,
                                                                    bank_statement.company_id,
                                                                    date)
        currency = moveline.currency_id.id
        return currency, amount_currency

    def get_invoices_for_reconcile(self, statement_line):
        """
        This method gets invoices for reconciling the bank statement.
        @param statement_line: Record of bank statement line.
        @author: Maulik Barad on Date 07-Dec-2020.
        """
        log_line = []
        shopify_payout_report_line_obj = self.env['shopify.payout.report.line.ept']
        sale_order_obj = self.env['sale.order']
        shopify_payout_report_line_id = shopify_payout_report_line_obj.search(
            [('transaction_id', '=', statement_line.shopify_transaction_id)])
        if not shopify_payout_report_line_id.order_id:
            sale_order_id = sale_order_obj.search(
                ['|', ('shopify_order_id', '=', shopify_payout_report_line_id.source_order_id),
                 ('name', '=', statement_line.payment_ref), ('shopify_instance_id', '=', self.instance_id.id)], limit=1)
            shopify_payout_report_line_id.write({'order_id': sale_order_id.id})
            statement_line.write({'sale_order_id': sale_order_id.id})
        sale_order_id = shopify_payout_report_line_id.order_id
        if sale_order_id:
            domain, invoice, log_line = self.check_for_invoice_refund(shopify_payout_report_line_id,log_line)
            if invoice and invoice.move_type == "out_refund":
                statement_line.update({"refund_invoice_id": invoice.id})
        order = statement_line.sale_order_id
        if order and not shopify_payout_report_line_id:
            shopify_payout_report_line_id = shopify_payout_report_line_obj.search(
                [('transaction_id', '=', statement_line.shopify_transaction_id)])
        if shopify_payout_report_line_id and shopify_payout_report_line_id.transaction_type == 'refund' \
                and not statement_line.refund_invoice_id:
            invoices = self.env['account.move'].search(
                [('shopify_instance_id', '=', self.instance_id.id), ('invoice_origin', '=', order.name),
                 ('move_type', '=', 'out_refund'), ('amount_total', '=', abs(statement_line.amount))])
            return invoices
        if statement_line.refund_invoice_id:
            invoices = statement_line.refund_invoice_id
        else:
            invoices = order.invoice_ids.filtered(lambda x: x.move_type == 'out_invoice' and x.state in ['posted'])
        return invoices

    def get_paid_move_line_amount(self, statement_line, paid_invoices):
        """
        This method is used to get the total paid amount of the Order for given statement line.
        @param statement_line: Record of the statement line.
        @param paid_invoices: Recordset of Paid Invoices.
        @author: Maulik Barad on Date 09-Dec-2020.
        """
        move_line_total_amount = 0.0
        currency_ids = []
        if statement_line.refund_invoice_id:
            payment_id = paid_invoices.line_ids.matched_debit_ids.debit_move_id.payment_id
            paid_move_lines = payment_id.invoice_line_ids.filtered(lambda x: x.credit != 0.0)
        else:
            payment_id = paid_invoices.line_ids.matched_credit_ids.credit_move_id.payment_id
            paid_move_lines = payment_id.invoice_line_ids.filtered(lambda x: x.debit != 0.0)

        for moveline in paid_move_lines:
            amount = moveline.debit - moveline.credit
            amount_currency = 0.0
            if moveline.amount_currency:
                currency, amount_currency = self.convert_move_amount_currency(self.statement_id, moveline, amount,
                                                                              statement_line.date)
                if currency:
                    currency_ids.append(currency)

            if amount_currency:
                amount = amount_currency

            move_line_total_amount += amount
        return move_line_total_amount, currency_ids, paid_move_lines

    def get_unpaid_move_line_data(self, statement_line, unpaid_invoices):
        """
        This method is used to gather the data of move lines that are remain to register payment.
        @param statement_line: Record of the statement line.
        @param unpaid_invoices: Recordset of Unpaid Invoices.
        @author: Maulik Barad on Date 09-Dec-2020.
        """
        move_line_data = []
        move_line_total_amount = 0.0
        currency_ids = []
        move_lines = unpaid_invoices.line_ids.filtered(
            lambda l:  l.account_id.account_type == 'asset_receivable' and not l.reconciled)
        for moveline in move_lines:
            amount = moveline.debit - moveline.credit
            amount_currency = 0.0
            if moveline.amount_currency:
                currency, amount_currency = self.convert_move_amount_currency(self.statement_id, moveline, amount,
                                                                              statement_line.date)
                if currency:
                    currency_ids.append(currency)

            if amount_currency:
                amount = amount_currency
            move_line_data.append({
                'name': moveline.move_id.name,
                'id': moveline.id,
                'balance': -amount,
                'currency_id': moveline.currency_id.id,
            })
            move_line_total_amount += amount
        return move_line_total_amount, currency_ids, move_line_data

    def reconcile_invoice_refund(self, statement_line, move_line_total_amount, currency_ids, move_line_data,
                                 paid_move_lines, log_lines):
        if round(statement_line.amount, 10) == round(move_line_total_amount, 10) and (
                not statement_line.currency_id or statement_line.currency_id.id ==
                self.statement_id.currency_id.id):
            if currency_ids:
                currency_ids = list(set(currency_ids))
                if len(currency_ids) == 1:
                    statement_currency = statement_line.journal_id.currency_id if \
                        statement_line.journal_id.currency_id else statement_line.company_id.currency_id
                    if not currency_ids[0] == statement_currency.id:
                        vals = {'currency_id': currency_ids[0]}
                        statement_line.write(vals)
            try:
                if move_line_data:
                    data = move_line_data[0]
                    move_line_id = data.get('id', False)
                    self.shopify_reconcile_bank_statement_line_ept(statement_line, move_line_id)
                for payment_line in paid_move_lines:
                    self.shopify_reconcile_bank_statement_line_ept(statement_line, payment_line.id)
            except Exception as error:
                message = "Error occurred while reconciling statement line : " + statement_line.payment_ref + \
                          ".\n" + str(error)
                transaction_line = self.payout_transaction_ids.filtered(
                    lambda x: x.transaction_type == statement_line.shopify_transaction_type and
                              x.transaction_id == statement_line.shopify_transaction_id and x.amount ==
                              statement_line.amount)
                log_lines.append({"message": message,
                                  "shopify_payout_report_line_id": transaction_line.id})
                statement_line.action_undo_reconciliation()
        return log_lines

    def shopify_reconcile_bank_statement_line_ept(self, statement_line_id, move_line_id):
        """
        This method will help to reconcile amazon bank statement line.
        :param statement_line_id: int
        :param move_line_id: int
        :return:
        """
        wizard = self.env['bank.rec.widget'].with_context(default_st_line_id=statement_line_id).new({})
        wizard._action_add_new_amls(self.env['account.move.line'].browse(move_line_id))
        wizard.with_context(dynamic_unlink=True).button_validate(async_action=False)

    def reconcile_other_transactions(self, statement_line, move_line_data, log_lines):

        transaction_type = statement_line.shopify_transaction_type
        transaction_account_line = self.instance_id.transaction_line_ids.filtered(
            lambda x: x.transaction_type == transaction_type)

        if not transaction_account_line:
            message = "Can't reconcile %s.\nPlease configure an account for the Transaction type : %s.\nGo " \
                      "to Configuration > Instances > Open Instance and set account in Payout Configuration " \
                      "Tab." % (statement_line.payment_ref, transaction_type)
            if self._context.get("cron_process"):
                log_lines.append({"message": message})
                return log_lines
            raise UserError(_(message))
        # move_line_id = statement_line.move_id.line_ids.filtered(lambda x: x.credit == 0.0)
        # move_line_id = move_line_id[0]
        # move_line_id.with_context(skip_account_move_synchronization=True).write({
        #     'account_id': transaction_account_line.account_id.id})
        move_line_data.append({
            "id": statement_line.move_id.id,
            "name": statement_line.payment_ref,
            "balance": -statement_line.amount,
            "account_id": transaction_account_line[0].account_id.id
        })
        if move_line_data:
            data = move_line_data[0]
            move_line_id = data.get('id', False)
            self.shopify_reconcile_bank_statement_line_ept(statement_line.id, move_line_id)
        # ending_balance_line.move_id.action_post()
        # move_line_data.append({
        #     "name": statement_line.payment_ref,
        #     "balance": -statement_line.amount,
        #     "account_id": transaction_account_line.account_id.id
        # })
        # statement_line.reconcile(lines_vals_list=move_line_data)
        return log_lines

    def process_bank_statement(self):
        """
        This method is used to process the bank statement.
        @author: Maulik Barad on Date 07-Dec-2020.
        """
        log_lines = []
        bank_statement = self.statement_id

        _logger.info("Processing Bank Statement: %s.", bank_statement.name)
        # if bank_statement.state == "open":
        #     bank_statement.button_post()

        for statement_line in bank_statement.line_ids.filtered(lambda x: not x.is_reconciled):
            move_line_data = []
            move_line_total_amount = 0.0
            currency_ids = []
            paid_move_lines = []
            if statement_line.shopify_transaction_type in ["charge", "refund","payment_refund"]:
                invoices = self.get_invoices_for_reconcile(statement_line)
                if not invoices:
                    continue

                paid_invoices = invoices.filtered(lambda x: x.payment_state in ['paid', 'in_payment'])
                unpaid_invoices = invoices.filtered(lambda x: x.payment_state == 'not_paid')

                if paid_invoices:
                    move_line_total_amount, currency_ids, paid_move_lines = self.get_paid_move_line_amount(
                        statement_line, paid_invoices)

                if unpaid_invoices:
                    move_line_total_amount, currency_ids, move_line_data = self.get_unpaid_move_line_data(
                        statement_line, unpaid_invoices)

                log_line = self.reconcile_invoice_refund(statement_line, move_line_total_amount, currency_ids,
                                                         move_line_data, paid_move_lines, log_lines)
            else:
                log_line = self.reconcile_other_transactions(statement_line, move_line_data, log_lines)

            # if log_line:
            #     log_lines += log_line

        if log_lines:
            self.set_payout_log_line(log_lines)
            note = ""
            for log_line in self.common_log_line_ids:
                note += str(log_line.message) + "<br/>"
            self.message_post(body=note)

            if self.instance_id.is_shopify_create_schedule:
                self.common_log_line_ids.create_payout_schedule_activity(note, self)

        if bank_statement.line_ids.filtered(lambda x: not x.is_reconciled):
            self.write({'state': 'partially_processed'})
        else:
            self.write({'state': 'processed'})
            self.validate_statement()

        return True

    def validate_statement(self):
        """
        Use : To reconcile the bank statement.
        @author: Maulik Barad on Date 07-Dec-2020.
        """
       # self.statement_id.button_validate_or_action()
        self.state = 'validated'
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Use : Inherit Create method to Create Unique sequence for import payout.
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        :param vals: dictionary
        :return: result
        """
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('shopify.payout.report.ept') or _('New')
        result = super(ShopifyPaymentReportEpt, self).create(vals_list)
        return result

    def unlink(self):
        """
        Use : Inherit method for Raiser warning if it is in Processed or closed state.
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        :return: Raise warning of call super method.
        """
        for report in self:
            if report.state != 'draft':
                raise UserError(_('You cannot delete Payout Report, Which is not in Draft state.'))
        return super(ShopifyPaymentReportEpt, self).unlink()

    def auto_import_payout_report(self, ctx=False):
        """
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        Func: this method use get payout report from the last import payout date and current date
        :param ctx: use for the instance
        :return: True
        """
        shopify_instance_obj = self.env['shopify.instance.ept']
        if isinstance(ctx, dict):
            shopify_instance_id = ctx.get('shopify_instance_id', False)
            if shopify_instance_id:
                instance = shopify_instance_obj.search([('id', '=', shopify_instance_id)])
                payout_import_date = instance.payout_last_import_date
                if not instance.payout_last_import_date:
                    payout_import_date = datetime.now() - timedelta(days=30)
                if payout_import_date:
                    _logger.info("===== Auto Import Payout Report =====")
                    self.get_payout_report(payout_import_date, datetime.now(), instance)
        return True

    def auto_process_bank_statement(self, ctx=False):
        """
        Added by : Deval Jagad
        Added on : 05/06/2020
        Task ID : 164126
        Func: this method use for search  generated report and then process bank statement
        :param ctx: use for the instance
        :return: True
        """
        if isinstance(ctx, dict):
            shopify_instance_id = ctx.get("shopify_instance_id", False)
            if shopify_instance_id:
                partially_generated_reports = self.search([("state", "=", "partially_generated"),
                                                           ("instance_id", "=", shopify_instance_id),
                                                           ("is_skip_from_cron", "=", False)], order="payout_date asc")
                for report in partially_generated_reports:
                    report.generate_remaining_bank_statement()
                generated_reports = self.search([("state", "in", ["generated", "partially_processed"]),
                                                 ("instance_id", "=", shopify_instance_id),
                                                 ("statement_id", "!=", False),
                                                 ("is_skip_from_cron", "=", False)], order="payout_date asc")
                for generated_report in generated_reports:
                    _logger.info("===== Auto Process Bank Statement:%s =====", generated_report.name)
                    generated_report.with_context(cron_process=True).process_bank_statement()
                    self._cr.commit()
        return True

    def open_log_book(self):
        """
        Returns action for opening the log book record.
        @author: Maulik Barad on Date 03-Dec-2020.
        @return: Action to open Log Book record.
        """
        return {
            "name": "Logs",
            "type": "ir.actions.act_window",
            "res_model": "common.log.book.ept",
            "views": [(False, "form")],
            'context': self.env.context
        }

    def set_payout_log_line(self, log_lines):
        """
        This method is used to create new log book, add log lines in it and attach to the Payout Report.
        @param log_lines: Recordset of the Log Lines.
        @author: Maulik Barad on Date 09-Dec-2020.
        """
        for log_line in log_lines:
            self.env["common.log.lines.ept"].create_common_log_line_ept(shopify_instance_id=self.instance_id.id,module="shopify_ept",
                                                                        message=log_line.get('message'),
                                                                        model_name=self._name)

        return True
