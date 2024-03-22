# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import json
from odoo import models, fields, _
from odoo.exceptions import UserError
from .. import shopify


class ShopifyCancelRefundOrderWizard(models.TransientModel):
    _name = "shopify.cancel.refund.order.wizard"
    _description = 'Shopify Cancel Refund Order Wizard'

    message = fields.Selection([('customer', 'Customer changed/cancelled order'),
                                ('inventory', 'Fraudulent order'),
                                ('fraud', 'Items unavailable'),
                                ('other', 'Other'),
                                ], default="other", help="The reason for the order cancellation.")
    notify_by_email = fields.Boolean("Notify By Email ?", default=True,
                                     help="Whether to send an email to the customer notifying the cancellation.")
    auto_create_credit_note = fields.Boolean("Create Credit Note In ERP", default=False,
                                             help="It will create a credit not in Odoo")
    journal_id = fields.Many2one('account.journal', 'Journal',
                                 help='You can select here the journal to use for the credit note that will be created.'
                                      ' If you leave that field empty, it will use the same journal as the current '
                                      'invoice.')
    refund_from = fields.Many2one("shopify.payment.gateway.ept", string="Refund From")
    reason = fields.Char()
    refund_date = fields.Date()
    # Below fields are used for refund process.
    notify_by_email = fields.Boolean("Notify By Email ?", help="Whether to send a refund notification to the customer.")
    note = fields.Char(help="An optional note attached to a refund.")
    restock_type = fields.Selection(
        [('no_restock', 'No Return'), ('cancel', 'Cancel'), ('return', 'Return')],
        default='no_restock',
        help="No Return: Refunding these items won't affect inventory.\nCancel:The items have not yet been fulfilled. "
             "The canceled quantity will be added back to the available count.\n Return:The items were already "
             "delivered,and will be returned to the merchant.The returned quantity will be added back to the available "
             "count")
    payment_ids = fields.Many2many('shopify.order.payment.ept', 'shopify_payment_refund_rel', string="Payments")

    def cancel_in_shopify(self):
        """This method used to cancel order in shopify store.
            @return: action
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20/11/2019.
            Task Id : 157911
        """
        active_id = self._context.get('active_id')
        sale_order_id = self.env['sale.order'].browse(active_id)
        instance = sale_order_id.shopify_instance_id
        instance.connect_in_shopify()
        order_id = self.prepare_cancel_order_data(sale_order_id, instance)

        try:
            order_id.cancel(email=self.notify_by_email, reason=self.message)
        except Exception as error:
            if hasattr(error, "response"):
                if hasattr(error.response, "body") and error.response.code == 422:
                    msg = _("Error while cancelling the order in shopify :\n%s" % (
                        json.loads(error.response.body.decode()).get("error")))
                else:
                    msg = _("Error while cancelling the order in shopify : %s\n%s" % (
                        error.response.code, json.loads(error.response.body.decode())))
            else:
                msg = _("Error while cancelling the order in shopify :\n%s" % str(error))
            raise UserError(msg)

        sale_order_id.write({'canceled_in_shopify': True})
        if self.auto_create_credit_note:
            self.shopify_create_credit_note(sale_order_id)
        return True

    def prepare_cancel_order_data(self, sale_order_id, instance):
        """ This method is used to set cancel order-related data in a session of order object.
            :sale_order_id : Id of shopify order.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 23 October 2020 .
            Task_id: 167537
        """
        instance.connect_in_shopify()
        try:
            order_id = shopify.Order()
        except Exception as error:
            raise UserError(_("Error while cancelling the order in shopify :\n%s" % error))

        order_id.id = sale_order_id.shopify_order_id

        return order_id

    def shopify_create_credit_note(self, order_id):
        """It will create a credit note in Odoo base on the configuration of the pop screen of the cancel wizard.
            :param order_id: Record of sale order.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20/11/2019.
            Task Id : 157911
        """
        moves = order_id.invoice_ids.filtered(
            lambda m: m.move_type == 'out_invoice' and m.payment_state in ['paid', 'in_payment'])
        if not moves:
            # Here we add commit because we need to write values in sale order before warring
            # raise. if raise warring it will not commit so we need to write commit.
            order_id._cr.commit()
            warning_message = "1.Order cancel in Shopify but unable to create a credit note." \
                              "2.Since order may be uncreated or unpaid invoice."
            raise UserError(warning_message)
        default_values_list = []
        for move in moves:
            date = self.refund_date or move.date
            default_values_list.append({
                'ref': _('Reversal of: %s, %s') % (move.name, self.reason) if self.reason else _(
                    'Reversal of: %s') % move.name,
                'date': date,
                'invoice_date': move.is_invoice(include_receipts=True) and date or False,
                'journal_id': self.journal_id and self.journal_id.id or move.journal_id.id,
                'invoice_payment_term_id': None,
                'auto_post': 'at_date' if date >= fields.Date.context_today(self) else 'no',
            })
        moves._reverse_moves(default_values_list)
        return True

    def refund_in_shopify(self):
        """This method used to call the child method to create a refund in the Shopify store.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20/11/2019.
            Task Id : 157911
        """
        active_id = self._context.get('active_id')
        credit_note_ids = self.env['account.move'].browse(active_id)
        self.check_validation_of_multi_payment()
        model = "account.move"
        for credit_note_id in credit_note_ids:
            if not credit_note_id.shopify_instance_id:
                continue
            credit_note_id.shopify_instance_id.connect_in_shopify()
            orders = credit_note_id.invoice_line_ids.sale_line_ids.order_id
            # get shopify order data
            shopify_order_data = shopify.Order.find(orders.shopify_order_id)
            order_data = shopify_order_data.to_dict()
            refund_lines_list, do_not_order_process_ids, mismatch_log_lines = self.prepare_refund_line_list(
                credit_note_id, model, order_data)
            log_lines = self.create_refund_in_shopify(orders, credit_note_id, refund_lines_list,
                                                      model, do_not_order_process_ids,
                                                      credit_note_id.shopify_instance_id)
        if mismatch_log_lines or log_lines:
            total_log_lines = mismatch_log_lines + log_lines
        return True

    def check_validation_of_multi_payment(self):
        """
        This method is used to check the refund validation of multi-payment gateway
        @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 27 November 2021 .
        Task_id: 179257
        """
        if self.payment_ids and not (any(self.payment_ids.mapped('is_want_to_refund'))):
            raise UserError(_('Please select which payment gateway do you want a refund.'))
        return True

    def prepare_refund_line_list(self, credit_note_id, model_id, order_data):
        """ This method is used to prepare a refund lines for order refund in shopify store.
            :param credit_note_id: Record of credit note.
            :param model_id: Which is used for create a mismatch logs.
            @return:refund_lines_list, do_not_order_process_ids, mismatch_log_lines
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 24 October 2020 .
            Task_id: 167537
        """
        restock_type = self.restock_type
        refund_lines_list = []
        do_not_order_process_ids = []
        mismatch_log_lines = []
        shopify_instance = credit_note_id.shopify_instance_id
        shopify_location_obj = self.env["shopify.location.ept"]
        refunded_qty_dict = {}

        # get refunded qty
        for refund_data in order_data.get('refunds'):
            for refund_data_line in refund_data.get('refund_line_items'):
                line_item_id = refund_data_line.get('line_item_id')
                refund_qty = refund_data_line.get('quantity')
                if line_item_id in refunded_qty_dict and refund_qty:
                    refund_qty += refunded_qty_dict.get(line_item_id)
                refunded_qty_dict.update({line_item_id: refund_qty})

        for invoice_line_id in credit_note_id.invoice_line_ids:
            if invoice_line_id.product_id.type == 'service':
                continue
            shopify_line_id = invoice_line_id.sale_line_ids.shopify_line_id
            if order_data.get('financial_status') == 'partially_refunded':
                refunded_qty = refunded_qty_dict.get(int(shopify_line_id)) if refunded_qty_dict.get(
                    int(shopify_line_id)) else 0
                refund_line_dict = {'line_item_id': int(shopify_line_id),
                                    'quantity': abs(int(invoice_line_id.quantity - refunded_qty)),
                                    'restock_type': restock_type}
            else:
                refund_line_dict = {'line_item_id': int(shopify_line_id),
                                    'quantity': int(invoice_line_id.quantity),
                                    'restock_type': restock_type}

            if restock_type in ['cancel', 'return']:
                order_id = credit_note_id.invoice_line_ids.sale_line_ids.order_id
                shopify_location_id = order_id.shopify_location_id or False
                if not shopify_location_id and restock_type == 'cancel':
                    shopify_instance = order_id.shopify_instance_id
                    shopify_location_id = shopify_location_obj.search([("is_primary_location", "=", True),
                                                                       ("instance_id", "=", shopify_instance.id)])
                if not shopify_location_id:
                    if restock_type == 'cancel':
                        log_message = "Primary Location not found for instance %s while refund in shopify." % (
                            shopify_instance.name)
                    else:
                        log_message = "Location is not set in order (%s).Unable to refund in shopify.\n You can see " \
                                      "order location here: Order => Shopify Info => Shopify Location " % order_id.name
                    log_line = self.env["common.log.lines.ept"].create_common_log_line_ept(
                        shopify_instance_id=shopify_instance.id, module="shopify_ept", message=log_message,
                        model_name='sale.order',
                        order_ref=order_id.name)
                    mismatch_log_lines.append(log_line.id)
                    do_not_order_process_ids.append(order_id.id)
                    continue
                refund_line_dict.update(
                    {'location_id': int(shopify_location_id.shopify_location_id)})
            refund_lines_list.append(refund_line_dict)

        return refund_lines_list, do_not_order_process_ids, mismatch_log_lines

    def create_refund_in_shopify(self, orders, credit_note_id, refund_lines_list, model,
                                 do_not_order_process_ids, instance):
        """This method used to create a refund in Shopify.
            @param : self
            @return:
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20/11/2019.
            Task Id : 157911
        """
        in_picking_total_qty = 0
        out_picking_total_qty = 0
        shipping = {}
        mismatch_logline = []
        for order in orders:
            if order.id in do_not_order_process_ids:
                continue
            outgoing_picking_ids = order.mapped('picking_ids').filtered(
                lambda picking: picking.picking_type_id.code == 'outgoing' and picking.state == 'done')
            incoming_picking_ids = order.mapped('picking_ids').filtered(
                lambda picking: picking.picking_type_id.code == 'incoming' and picking.state == 'done')
            if incoming_picking_ids:
                in_picking_total_qty = sum(
                    incoming_picking_ids.mapped('move_ids').mapped('quantity_done'))
            if outgoing_picking_ids:
                out_picking_total_qty = sum(
                    outgoing_picking_ids.mapped('move_ids').mapped('quantity_done'))

            if in_picking_total_qty == out_picking_total_qty:
                shipping.update({"full_refund": True})
            else:
                shipping.update({'amount': 0.0})
            refund_amount = credit_note_id.amount_total
            if self.payment_ids:
                refund_amount = float(sum(self.payment_ids.mapped('refund_amount')))
            # This used for amount validation.
            parent_id, gateway, transactions = self.refund_amount_validation(order, refund_amount)
            # This method is used to prepare a refund vals for refund order in shopify.
            if gateway == 'gift_card':
                refund_lines_list = []
            order_payment_dict, refund_payment_dict = self.prepare_payment_data(transactions)
            final_payment_data = self.prepare_final_payment_data(order_payment_dict, refund_payment_dict)
            parent_id, payment_gateway = self.find_feasible_payment_gateway(final_payment_data, refund_amount, transactions)
            gateway = payment_gateway
            parent_id = parent_id
            vals = self.prepare_shopify_refund_vals(parent_id, gateway, refund_amount, order, shipping,
                                                    refund_lines_list)
            refund_in_shopify = shopify.Refund()
            try:
                result = refund_in_shopify.create(vals)
            except Exception as error:
                log_message = "When creating refund in Shopify for order (%s), issue arrive in " \
                              "request (%s)" % (order.name, error)
                log_line = self.env["common.log.lines.ept"].create_common_log_line_ept(
                    shopify_instance_id=instance.id, module="shopify_ept", message=log_message,
                    model_name=model,
                    order_ref=order.name)
                mismatch_logline.append(log_line.id)
                continue
            if not bool(result.id):
                log_message = "When creating refund in Shopify for order (%s), issue arrive in " \
                              "request (%s)" % (order.name, result.errors.errors.get('base'))
                log_line = self.env["common.log.lines.ept"].create_common_log_line_ept(
                    shopify_instance_id=instance.id, module="shopify_ept", message=log_message,
                    model_name=model,
                    order_ref=order.name)
                mismatch_logline.append(log_line.id)
                continue
            credit_note_id.write({'is_refund_in_shopify': True, 'shopify_refund_id': result.id if result else False})

        return mismatch_logline

    def prepare_payment_data(self, transactions):
        """
        This method is used to prepare a dict for order and refund payment against payment gateway.
        :param transactions: Record of Transaction
        @return: order_payment, refund_payment
        @author: Yagnik Joshi @Emipro Technologies Pvt. Ltd on date 31 January 2024 .
        Task_id: 7539
        """
        order_payment = {}
        refund_payment = {}
        for transaction in transactions:
            result = transaction.to_dict()
            gateway = result.get('gateway')
            amount = float(result.get('amount'))
            status = result.get('status')
            kind = result.get('kind')
            if status == 'success':
                if kind != 'refund':
                    order_payment[gateway] = order_payment.get(gateway, 0) + amount
                else:
                    refund_payment[gateway] = refund_payment.get(gateway, 0) + amount
        return order_payment, refund_payment

    def prepare_final_payment_data(self, order_payment_dict, refund_payment_dict):
        final_payment_data = {}
        final_payment_data.update(order_payment_dict)
        for gateway, refund_amount in refund_payment_dict.items():
            if gateway in final_payment_data:
                final_payment_data[gateway] = round(float(final_payment_data[gateway]) - float(refund_amount), 2)
        final_payment_data = {gateway: str(amount) for gateway, amount in final_payment_data.items()}
        return final_payment_data

    def find_feasible_payment_gateway(self ,final_payment_data, refund_amount, transactions):
        parent_id = False
        payment_gateway = False
        for transaction in transactions:
            result = transaction.to_dict()
            for payment_gateway, remaining_amount_str in final_payment_data.items():
                remaining_amount = float(remaining_amount_str)
                if (remaining_amount >= refund_amount) and (payment_gateway == result.get('gateway')):
                    payment_gateway = payment_gateway
                    parent_id = result.get('id')
        return parent_id, payment_gateway

    def refund_amount_validation(self, order, refund_amount):
        """ This method is used to refund the amount validation for particular order.
            :param ordre: Record of sale order.
            :param refund_amount: Refund amount(credit note amount)
            @return: parent_id, gateway
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 24 October 2020 .
            Task_id: 167537
        """
        total_refund_in_shopify = 0.0
        total_order_amount = order.amount_total
        transactions = shopify.Transaction().find(order_id=order.shopify_order_id)
        parent_id = False
        gateway = False
        refund_payment_gateway = False
        refund_parent_id = False
        for transaction in transactions:
            result = transaction.to_dict()
            if result.get('kind') in ['sale', 'authorization']:
                if result.get('gateway') == 'gift_card':
                    refund_payment_gateway = result.get('gateway')
                    refund_parent_id = result.get('id')
                parent_id = result.get('id')
                gateway = result.get('gateway')
            if result.get('kind') == 'refund' and result.get('status') == 'success':
                refunded_amount = result.get('amount')
                total_refund_in_shopify = round(total_refund_in_shopify + float(refunded_amount), 2)
        total_refund_amount = total_refund_in_shopify + refund_amount
        maximum_refund_allow = refund_amount - total_refund_in_shopify
        if maximum_refund_allow < 0:
            maximum_refund_allow = 0.0
        if refund_payment_gateway and total_refund_amount > total_order_amount:
            return refund_parent_id, refund_payment_gateway
        if total_refund_amount > total_order_amount:
            raise UserError(
                _("You can't refund then actual payment, requested amount for refund %s, maximum refund allow %s") % (
                    refund_amount, maximum_refund_allow))
        return parent_id, gateway, transactions

    def prepare_shopify_refund_vals(self, parent_id, gateway, refund_amount, order, shipping, refund_lines_list):
        """ This method is used to prepare a refund order vals.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 24 October 2020 .
            Task_id: 167537
        """
        multi_payments = order.shopify_payment_ids
        if multi_payments:
            transactions = []
            for order_payment in multi_payments.filtered(
                    lambda payment_gateway: payment_gateway.is_want_to_refund == True):
                parent_id = int(order_payment.payment_transaction_id)
                transaction = self.preapre_refund_transaction_vals(parent_id, order_payment.refund_amount,
                                                                   order_payment.payment_gateway_id.code)
                transactions.append(transaction)
                remaining_refund_amount = order_payment.remaining_refund_amount - order_payment.refund_amount
                is_fully_refunded = True if remaining_refund_amount == 0.0 else False
                order_payment.write(
                    {'remaining_refund_amount': round(remaining_refund_amount, 2),
                     'is_fully_refunded': is_fully_refunded})
        else:
            transactions = self.preapre_refund_transaction_vals(parent_id, refund_amount, gateway)
            transactions = [transactions]
        note = self.note
        notify = self.notify_by_email
        vals = {'notify': notify,
                "shipping": shipping,
                "note": note,
                "order_id": order.shopify_order_id,
                "refund_line_items": refund_lines_list,
                "transactions": transactions,
                "currency": order.currency_id.name,
                }
        return vals

    def preapre_refund_transaction_vals(self, parent_id, refund_amount, gateway):
        """
        This method is used to prepare a refund transaction vals.
        @return: Refund Vals
        @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 16/11/2021 .
        Task_id: 179257
        """
        transactions = {
            "parent_id": parent_id,
            "amount": refund_amount,
            "kind": "refund",
            "gateway": gateway,
        }
        return transactions
