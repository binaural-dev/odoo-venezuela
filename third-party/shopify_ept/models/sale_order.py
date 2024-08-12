# See LICENSE file for full copyright and licensing details.

import json
import logging
from datetime import datetime, timedelta
import time
import pytz

from dateutil import parser

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tests import Form
from ..shopify.pyactiveresource.util import xml_to_dict
from .. import shopify
from ..shopify.pyactiveresource.connection import ClientError

utc = pytz.utc

_logger = logging.getLogger("Shopify Order")


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_shopify_order_status(self):
        """
        Set updated_in_shopify of order from the pickings.
        @author: Maulik Barad on Date 06-05-2020.
        """
        for order in self:
            if order.shopify_instance_id:
                pickings = order.picking_ids.filtered(lambda x: x.state != "cancel")
                if pickings:
                    outgoing_picking = pickings.filtered(
                        lambda x: x.location_dest_id.usage == "customer")
                    if all(outgoing_picking.mapped("updated_in_shopify")):
                        order.updated_in_shopify = True
                        continue
                if order.state != 'draft' and order.moves_count > 0:
                    move_ids = self.env["stock.move"].search([("picking_id", "=", False),
                                                              ("sale_line_id", "in", order.order_line.ids)])
                    state = set(move_ids.mapped('state'))
                    if len(set(state)) == 1 and 'done' in set(state):
                        order.updated_in_shopify = True
                        continue
                order.updated_in_shopify = False
                continue
            order.updated_in_shopify = False

    def _search_shopify_order_ids(self, operator, value):
        query = """select so.id from stock_picking sp
                    inner join sale_order so on so.procurement_group_id=sp.group_id                   
                    inner join stock_location on stock_location.id=sp.location_dest_id and stock_location.usage='customer'
                    where sp.updated_in_shopify %s true and sp.state != 'cancel'
                """ % (operator)
        if operator == '=':
            query += """union all
                    select so.id from sale_order as so
                    inner join sale_order_line as sl on sl.order_id = so.id
                    inner join stock_move as sm on sm.sale_line_id = sl.id
                    where sm.picking_id is NULL and sm.state = 'done' and so.shopify_instance_id notnull"""
        self._cr.execute(query)
        results = self._cr.fetchall()
        order_ids = []
        for result_tuple in results:
            order_ids.append(result_tuple[0])
        order_ids = list(set(order_ids))
        return [('id', 'in', order_ids)]

    shopify_order_id = fields.Char("Shopify Order Ref", copy=False)
    shopify_order_number = fields.Char(copy=False)
    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Shopify Instance", copy=False)
    shopify_order_status = fields.Char(copy=False, tracking=True,
                                       help="Shopify order status when order imported in odoo at the moment order"
                                            "status in Shopify.")
    shopify_payment_gateway_id = fields.Many2one('shopify.payment.gateway.ept',
                                                 string="Payment Gateway", copy=False)
    risk_ids = fields.One2many("shopify.order.risk", 'odoo_order_id', "Risks", copy=False)
    shopify_location_id = fields.Many2one("shopify.location.ept", "Shopify Location", copy=False)
    checkout_id = fields.Char(copy=False)
    is_risky_order = fields.Boolean("Risky Order?", default=False, copy=False)
    updated_in_shopify = fields.Boolean("Updated In Shopify ?", compute=_get_shopify_order_status,
                                        search='_search_shopify_order_ids')
    closed_at_ept = fields.Datetime("Closed At", copy=False)
    canceled_in_shopify = fields.Boolean(default=False, copy=False)
    is_pos_order = fields.Boolean("POS Order ?", copy=False, default=False)
    is_service_tracking_updated = fields.Boolean("Service Tracking Updated", default=False, copy=False)
    is_shopify_multi_payment = fields.Boolean("Multi Payments?", default=False, copy=False,
                                              help="It is used to identify that order has multi-payment gateway or not")
    shopify_payment_ids = fields.One2many('shopify.order.payment.ept', 'order_id',
                                          string="Payment Lines")
    is_buy_with_prime_order = fields.Boolean("Buy with Prime Order", default=False, copy=False)

    _sql_constraints = [('unique_shopify_order',
                         'unique(shopify_instance_id,shopify_order_id,shopify_order_number)',
                         "Shopify order must be Unique.")]

    def prepare_shopify_customer_and_addresses(self, order_response, pos_order, instance, order_data_line):
        """
        Searches for existing customer in Odoo and creates in odoo, if not found.
        @author: Maulik Barad on Date 11-Sep-2020.
        """
        res_partner_obj = self.env["res.partner"]
        shopify_res_partner_obj = self.env["shopify.res.partner.ept"]
        message = False

        if pos_order:
            if order_response.get("customer"):
                partner = res_partner_obj.create_shopify_pos_customer(order_response, instance)
            else:
                partner = instance.shopify_default_pos_customer_id
            if not partner:
                message = "Default POS Customer is not set.\nPlease set Default POS Customer in " \
                          "Shopify Configuration."
        else:
            if not any([order_response.get("customer", {}), order_response.get("billing_address", {}),
                        order_response.get("shipping_address", {})]):
                message = "Customer details are not available in %s Order." % (order_response.get("order_number"))
            else:
                partner = order_response.get("customer") and shopify_res_partner_obj.shopify_create_contact_partner(
                    order_response.get("customer"), instance, False)
        if message:
            self.env["common.log.lines.ept"].create_common_log_line_ept(shopify_instance_id=instance.id,
                                                                        module="shopify_ept",
                                                                        message=message,
                                                                        model_name='sale.order',
                                                                        order_ref=order_response.get('name'),
                                                                        shopify_order_data_queue_line_id=order_data_line.id if order_data_line else False)
            order_data_line.write({"state": "failed", "processed_at": datetime.now()})
            _logger.info(message)
            return False, False, False

        if not partner:
            if order_data_line:
                order_data_line.write({"state": "failed", "processed_at": datetime.now()})
            return False, False, False

        if partner.parent_id:
            partner = partner.parent_id

        invoice_address = order_response.get("billing_address") and \
                          shopify_res_partner_obj.shopify_create_or_update_address(instance,
                                                                                   order_response.get(
                                                                                       "billing_address"), partner,
                                                                                   "invoice") or partner

        delivery_address = order_response.get("shipping_address") and \
                           shopify_res_partner_obj.shopify_create_or_update_address(instance,
                                                                                    order_response.get(
                                                                                        "shipping_address"), partner,
                                                                                    "delivery") or partner

        # Below condition as per the task 169257.
        if not partner and invoice_address and delivery_address:
            partner = invoice_address
        if not partner and not delivery_address and invoice_address:
            partner = invoice_address
            delivery_address = invoice_address
        if not partner and not invoice_address and delivery_address:
            partner = delivery_address
            invoice_address = delivery_address

        return partner, delivery_address, invoice_address

    def set_shopify_location_and_warehouse(self, order_response, instance, pos_order, sale_order):
        """
        This method sets shopify location and warehouse related to that location in order.
        @author: Maulik Barad on Date 11-Sep-2020.
        """
        shopify_location = shopify_location_obj = self.env["shopify.location.ept"]
        if order_response.get("location_id"):
            shopify_location_id = order_response.get("location_id")
        elif order_response.get("fulfillments"):
            shopify_location_id = order_response.get("fulfillments")[0].get("location_id")
        else:
            shopify_location_id = False

        if shopify_location_id:
            shopify_location = shopify_location_obj.search(
                [("shopify_location_id", "=", shopify_location_id),
                 ("instance_id", "=", instance.id)],
                limit=1)

        if shopify_location and shopify_location.warehouse_for_order:
            warehouse_id = shopify_location.warehouse_for_order.id
        else:
            warehouse_id = instance.shopify_warehouse_id.id

        if instance.import_buy_with_prime_shopify_order and sale_order.is_buy_with_prime_order:
            warehouse_id = instance.buy_with_prime_warehouse_id.id if instance.buy_with_prime_warehouse_id else warehouse_id

        return {"shopify_location_id": shopify_location and shopify_location.id or False,
                "warehouse_id": warehouse_id, "is_pos_order": pos_order}

    def create_shopify_order_lines(self, lines, order_response, instance):
        """
        This method creates sale order line and discount line for Shopify order.
        @author: Maulik Barad on Date 11-Sep-2020.
        """
        sale_order_line_obj = self.env["sale.order.line"]
        total_discount = order_response.get("total_discounts", 0.0)
        order_number = order_response.get("order_number")
        for line in lines:
            is_custom_line, is_gift_card_line, product = self.search_custom_tip_gift_card_product(line, instance)
            price = line.get("price")
            if instance.order_visible_currency:
                price = self.get_price_based_on_customer_visible_currency(line.get("price_set"), order_response, price)
            order_line = self.shopify_create_sale_order_line(line, product, line.get("quantity"),
                                                             product.name, price,
                                                             order_response)
            if is_gift_card_line:
                line_vals = {'is_gift_card_line': True}
                if line.get('name'):
                    line_vals.update({'name': line.get('name')})
                order_line.write(line_vals)

            if is_custom_line:
                order_line.write({'name': line.get('name')})

            if line.get('duties'):
                self.create_shopify_duties_lines(line.get('duties'), order_response, instance)

            if float(total_discount) > 0.0:
                discount_amount = 0.0
                for discount_allocation in line.get("discount_allocations"):
                    if instance.order_visible_currency:
                        discount_total_price = self.get_price_based_on_customer_visible_currency(
                            discount_allocation.get("amount_set"), order_response, discount_amount)
                        if discount_total_price:
                            discount_amount += float(discount_total_price)
                    else:
                        discount_amount += float(discount_allocation.get("amount"))

                if discount_amount > 0.0:
                    _logger.info("Creating discount line for Odoo order(%s) and Shopify order is (%s)", self.name,
                                 order_number)
                    self.shopify_create_sale_order_line({}, instance.discount_product_id, 1,
                                                        product.name, float(discount_amount) * -1,
                                                        order_response, previous_line=order_line,
                                                        is_discount=True)
                    _logger.info("Created discount line for Odoo order(%s) and Shopify order is (%s)", self.name,
                                 order_number)
        # add gift card as product in sale order line
        final_transactions_results = self.prepare_final_list_of_transactions(order_response.get('transaction'))
        total_giftcard_price = 0.0
        total_giftcard_qty = 0
        for transaction in final_transactions_results:
            if transaction.get('gateway') == 'gift_card':
                total_giftcard_qty += 1
                total_giftcard_price += float(transaction.get('amount'))
                # if self.order_line.filtered(
                #         lambda line: line.product_id.id == product_id.id and abs(line.price_unit) == float(price)):
                #     continue
        if total_giftcard_price:
            product_id = instance.gift_card_product_id
            line_vals = self.prepare_vals_for_gift_card_sale_order_line(product_id, product_id.name,
                                                                        total_giftcard_price, total_giftcard_qty)
            sale_order_line_obj.create(line_vals)
            _logger.info("Gift card line for Odoo order(%s) and Shopify order is (%s)", self.name, order_number)

    def prepare_vals_for_gift_card_sale_order_line(self, product_id, product_name, price, order_qty):
        uom_id = product_id and product_id.uom_id and product_id.uom_id.id or False
        price_unit = price / order_qty
        line_vals = {
            "product_id": product_id.id,
            "order_id": self.id,
            "company_id": self.company_id.id,
            "product_uom": uom_id,
            "name": "Gift card for " + str(product_name),
            "price_unit": float(price_unit) * -1,
            "product_uom_qty": order_qty
        }
        return line_vals

    def get_price_based_on_customer_visible_currency(self, price_set, order_response, price):
        """
        This method is used to set price based on customer visible currency.
        @author: Meera Sidapara on Date 16-June-2022.
        Task: 193010 - Shopify Multi currency changes
        """
        if float(price_set['shop_money']['amount']) > 0.0 and price_set['shop_money'][
            'currency_code'] == order_response.get('presentment_currency'):
            price = price_set['shop_money']['amount']
        elif float(price_set['presentment_money']['amount']) > 0.0 and price_set['presentment_money'][
            'currency_code'] == order_response.get('presentment_currency'):
            price = price_set['presentment_money']['amount']
        return float(price)

    def create_shopify_duties_lines(self, duties_line, order_response, instance):
        """
        Creates duties lines for shopify orders.
        @author: Meera Sidapara on Date 17-June-2022.
        """
        order_number = order_response.get("order_number")
        product = instance.duties_product_id if instance.duties_product_id else False
        # add duties
        for duties in duties_line:
            duties_amount = 0.0
            if instance.order_visible_currency:
                duties_amount = self.get_price_based_on_customer_visible_currency(duties.get("price_set"),
                                                                                  order_response,
                                                                                  duties_amount)

            if float(duties_amount) > 0.0:
                _logger.info("Creating duties line for Odoo order(%s) and Shopify order is (%s)", self.name,
                             order_number)
                self.shopify_create_sale_order_line(duties, instance.duties_product_id, 1,
                                                    product.name, float(duties_amount),
                                                    order_response, is_duties=True)
                _logger.info("Created duties line for Odoo order(%s) and Shopify order is (%s)", self.name,
                             order_number)

    def search_custom_tip_gift_card_product(self, line, instance):
        """
        Search the products of the custom option, Tip, and Gift card product..
        @author: Haresh Mori on Date 12-June-2021.
        Task: 172889 - TIP order import
        """
        is_custom_line = False
        is_gift_card_line = False
        product = False
        if not line.get('product_id'):
            if line.get('sku'):
                product = self.env["product.product"].search([("default_code", "=", line.get('sku'))], limit=1)
            if not product:
                product = instance.custom_storable_product_id
            is_custom_line = True
        if line.get('name') == 'Tip':
            product = instance.tip_product_id
            is_custom_line = True
        if line.get('gift_card'):
            product = instance.gift_card_product_id
            is_gift_card_line = True
        else:
            if not is_custom_line:
                shopify_product = self.search_shopify_product_for_order_line(line, instance)
                product = shopify_product.product_id

        return is_custom_line, is_gift_card_line, product

    def create_shopify_shipping_lines(self, order_response, instance):
        """
        Creates shipping lines for shopify orders.
        @author: Maulik Barad on Date 11-Sep-2020.
        """
        delivery_carrier_obj = self.env["delivery.carrier"]
        order_number = order_response.get("order_number")
        for line in order_response.get("shipping_lines", []):
            carrier = delivery_carrier_obj.shopify_search_create_delivery_carrier(line, instance)
            shipping_product = instance.shipping_product_id
            if carrier:
                self.write({"carrier_id": carrier.id})
                shipping_product = carrier.product_id
            # Some order in If shipping carrier is not there and Shipping amount is there then create shipping line.
            # Changes suggested by dipesh sir.
            if shipping_product:
                if float(line.get("price")) > 0.0:
                    shipping_price = line.get("price")
                    if instance.order_visible_currency:
                        shipping_price = self.get_price_based_on_customer_visible_currency(line.get("price_set"),
                                                                                           order_response,
                                                                                           shipping_price)
                    order_line = self.shopify_create_sale_order_line(line, shipping_product, 1,
                                                                     shipping_product.name or line.get("title"),
                                                                     shipping_price,
                                                                     order_response, is_shipping=True)
                discount_amount = 0.0
                for discount_allocation in line.get("discount_allocations"):
                    discount_amount += float(discount_allocation.get("amount"))
                if discount_amount > 0.0:
                    _logger.info("Creating discount line for Odoo order(%s) and Shopify order is (%s)", self.name,
                                 order_number)
                    self.shopify_create_sale_order_line({}, instance.discount_product_id, 1,
                                                        shipping_product.name, float(discount_amount) * -1,
                                                        order_response, previous_line=order_line,
                                                        is_discount=True)
                    _logger.info("Created discount line for Odoo order(%s) and Shopify order is (%s)", self.name,
                                 order_number)

    def import_shopify_orders(self, order_data_lines, instance):
        """
        This method used to create a sale orders in Odoo.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 11/11/2019.
        Task Id : 157350
        @change: By Maulik Barad on Date 21-Sep-2020.
        @change: By Meera Sidapara on Date 27-Oct-2021 for Task Id : 179249.
        """
        order_risk_obj = self.env["shopify.order.risk"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        order_ids = []
        commit_count = 0

        instance.connect_in_shopify()

        for order_data_line in order_data_lines:
            if commit_count == 5:
                self._cr.commit()
                commit_count = 0
            commit_count += 1
            order_data = order_data_line.order_data
            order_response = json.loads(order_data)

            order_number = order_response.get("order_number")
            shopify_financial_status = order_response.get("financial_status")
            _logger.info("Started processing Shopify order(%s) and order id is(%s)", order_number,
                         order_response.get("id"))

            date_order = self.convert_order_date(order_response)
            if str(instance.import_order_after_date) > date_order:
                message = "Order %s is not imported in Odoo due to configuration mismatch.\n Received order date is " \
                          "%s. \n Please check the order after date in shopify configuration." % (order_number,
                                                                                                  date_order)
                _logger.info(message)
                common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, module="shopify_ept",
                                                               message=message,
                                                               model_name='sale.order',
                                                               order_ref=order_response.get("name"),
                                                               shopify_order_data_queue_line_id=order_data_line.id if order_data_line else False)
                order_data_line.write({'state': 'failed', 'processed_at': datetime.now()})
                continue

            sale_order = self.search_existing_shopify_order(order_response, instance, order_number)

            if sale_order:
                order_data_line.write({"state": "done", "processed_at": datetime.now(),
                                       "sale_order_id": sale_order.id, "order_data": False})
                _logger.info("Done the Process of order Because Shopify Order(%s) is exist in Odoo and Odoo order is("
                             "%s)", order_number, sale_order.name)
                continue

            pos_order = order_response.get("source_name", "") == "pos"
            partner, delivery_address, invoice_address = self.prepare_shopify_customer_and_addresses(
                order_response, pos_order, instance, order_data_line)
            if not partner:
                continue

            lines = order_response.get("line_items")
            if self.check_mismatch_details(lines, instance, order_number, order_data_line):
                _logger.info("Mismatch details found in this Shopify Order(%s) and id (%s)", order_number,
                             order_response.get("id"))
                order_data_line.write({"state": "failed", "processed_at": datetime.now()})
                continue

            sale_order = self.shopify_create_order(instance, partner, delivery_address, invoice_address,
                                                   order_data_line, order_response, lines, order_number)
            if not sale_order:
                message = "Configuration missing in Odoo while importing Shopify Order(%s) and id (%s)" % (
                    order_number, order_response.get("id"))
                _logger.info(message)
                common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, module="shopify_ept",
                                                               message=message,
                                                               model_name='sale.order',
                                                               order_ref=order_response.get('name'),
                                                               shopify_order_data_queue_line_id=order_data_line.id if order_data_line else False)
                continue
            order_ids.append(sale_order.id)

            location_vals = self.set_shopify_location_and_warehouse(order_response, instance, pos_order, sale_order)

            if instance.is_delivery_multi_warehouse:
                warehouses = sale_order.order_line.filtered(lambda line_item: line_item.warehouse_id_ept).mapped(
                    'warehouse_id_ept')
                if warehouses and len(set(warehouses.ids)) == 1:
                    location_vals.update({"warehouse_id": warehouses.id})

            sale_order.write(location_vals)

            risk_result = shopify.OrderRisk().find(order_id=order_response.get("id"))
            if risk_result:
                order_risk_obj.shopify_create_risk_in_order(risk_result, sale_order)
                risk = sale_order.risk_ids.filtered(lambda x: x.recommendation != "accept")
                if risk:
                    sale_order.is_risky_order = True

            _logger.info("Starting auto workflow process for Odoo order(%s) and Shopify order is (%s)",
                         sale_order.name, order_number)
            message = ""
            try:
                if sale_order.shopify_order_status == "fulfilled":
                    sale_order.auto_workflow_process_id.shipped_order_workflow_ept(sale_order)
                    if order_data_line and order_data_line.shopify_order_data_queue_id.created_by == "scheduled_action":
                        created_by = 'Scheduled Action'
                    else:
                        created_by = self.env.user.name
                    # Below code add for create partially/fully refund
                    message = self.create_shipped_order_refund(shopify_financial_status, order_response, sale_order,
                                                               created_by)
                elif not sale_order.is_risky_order:
                    if sale_order.shopify_order_status == "partial":
                        sale_order.process_order_fullfield_qty(order_response)
                        sale_order.with_context(shopify_order_financial_status=order_response.get(
                            "financial_status")).process_orders_and_invoices_ept()
                        if order_data_line and order_data_line.shopify_order_data_queue_id.created_by == \
                                "scheduled_action":
                            created_by = 'Scheduled Action'
                        else:
                            created_by = self.env.user.name
                        # Below code add for create partially/fully refund
                        message = self.create_shipped_order_refund(shopify_financial_status, order_response, sale_order,
                                                                   created_by)
                    else:
                        sale_order.with_context(shopify_order_financial_status=order_response.get(
                            "financial_status")).process_orders_and_invoices_ept()


            except Exception as error:
                if order_data_line:
                    order_data_line.write({"state": "failed", "processed_at": datetime.now(),
                                           "sale_order_id": sale_order.id})
                message = "Receive error while process auto invoice workflow, Error is:  (%s)" % (error)
                _logger.info(message)
                common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, module="shopify_ept",
                                                               message=message,
                                                               model_name=self._name,
                                                               order_ref=order_response.get("name"),
                                                               shopify_order_data_queue_line_id=order_data_line.id if order_data_line else False)
                continue
            _logger.info("Done auto workflow process for Odoo order(%s) and Shopify order is (%s)", sale_order.name,
                         order_number)

            if message:
                common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, module="shopify_ept",
                                                               message=message,
                                                               model_name=self._name,
                                                               order_ref=order_response.get("name"),
                                                               shopify_order_data_queue_line_id=order_data_line.id if order_data_line else False)
                order_data_line.write({'state': 'failed', 'processed_at': datetime.now()})
            else:
                order_data_line.write({"state": "done", "processed_at": datetime.now(),
                                       "sale_order_id": sale_order.id, "order_data": False})
            _logger.info("Processed the Odoo Order %s process and Shopify Order (%s)", sale_order.name, order_number)

        return order_ids

    def validate_and_paid_invoices_ept(self, work_flow_process_record):
        """
        According to the workflow configuration, It will create invoices, validate them and register payment.
        @param : work_flow_process_record: Record of auto invoice workflow.
        """
        self.ensure_one()
        if not self.shopify_instance_id:
            return super(SaleOrder, self).validate_and_paid_invoices_ept(work_flow_process_record)
        if work_flow_process_record.create_invoice:
            if work_flow_process_record.invoice_date_is_order_date:
                if self.check_fiscal_year_lock_date_ept():
                    return True
            if work_flow_process_record.sale_journal_id:
                invoices = self.with_context(journal_ept=work_flow_process_record.sale_journal_id)._create_invoices()
            else:
                invoices = self._create_invoices()
            self.validate_invoice_ept(invoices)
            if self.shopify_instance_id and self.env.context.get(
                    'shopify_order_financial_status') and self.env.context.get(
                'shopify_order_financial_status') == 'pending':
                return False
            if work_flow_process_record.register_payment:
                self.paid_invoice_ept(invoices)
        return True

    def import_shopify_cancel_order(self, instance, from_date, to_date):
        """ This method is used if Shopify orders imported in odoo and after Shopify store in some orders are canceled
            then this method cancel imported orders and created a log note.
            @param : instance,from_date,to_date
            @return: True
            @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 16 March 2022.
            Task_id: 185873
        """
        shopify_order_data_queue_obj = self.env["shopify.order.data.queue.ept"]
        instance.connect_in_shopify()
        order_ids = shopify_order_data_queue_obj.shopify_order_request(instance, from_date, to_date, order_type="any")
        for order in order_ids:
            order_data = order.to_dict()
            if order_data.get('cancel_reason'):
                message = ""
                if order_data.get('cancel_reason') == "customer":
                    message = "Customer changed/canceled Order"
                elif order_data.get('cancel_reason') == "fraud":
                    message = "Fraudulent order"
                elif order_data.get('cancel_reason') == "inventory":
                    message = "Items unavailable"
                elif order_data.get('cancel_reason') == "declined":
                    message = "Payment declined"
                elif order_data.get('cancel_reason') == "other":
                    message = "Other"
                sale_order = self.search_existing_shopify_order(order_data, instance, order_data.get("order_number"))
                if sale_order and sale_order.state != 'cancel':
                    sale_order.write({'canceled_in_shopify': True})
                    sale_order.message_post(
                        body=_("The reason for the order cancellation on this Shopify store is that %s.", message))
                    sale_order.cancel_shopify_order()
        instance.last_cancel_order_import_date = to_date - timedelta(days=2)
        return True

    def process_picking_return(self, shopify_status, order_data, order, created_by, instance, queue_line):
        common_log_line_obj = self.env["common.log.lines.ept"]
        message = self.create_picking_return(shopify_status, order_data, order, created_by)
        if message:
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, message=message,
                                                           module="shopify_ept",
                                                           model_name='sale.order',
                                                           order_ref=order_data.get('name'),
                                                           shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
            queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
        else:
            queue_line.state = "done"

    def create_picking_return(self, shopify_status, order_data, order, created_by):
        message = ""
        if shopify_status == "refunded" or "partially_refunded" and order_data.get(
                "refunds"):
            is_need_create_return = False
            for refund in order_data.get('refunds'):
                for transaction in refund.get('transactions'):
                    if transaction.get('kind') == 'refund' and transaction.get('status') == 'success':
                        is_need_create_return = True

            if is_need_create_return:
                message = order.create_shopify_order_return(order_data.get("refunds"))
        return message

    def create_shopify_order_return(self, refunds_data):
        """
        This method use for create return base on refund data from shopify.
        @author: Nilam Kubavat @Emipro Technologies Pvt. Ltd on date 17 Jan 2024.
        Task_id: 6264
        """
        product_product_obj = self.env["product.product"]
        message = ""
        refund_line_items = self.prepare_refund_data(refunds_data)
        orig_move_ids = self.picking_ids.move_ids.move_orig_ids if self.picking_ids.move_ids.move_orig_ids else self.picking_ids.move_ids
        orig_done_picking_ids = orig_move_ids.picking_id.filtered(lambda picking: picking.state == "done")
        mrp_module = product_product_obj.search_installed_module_ept('mrp')
        if not orig_done_picking_ids and mrp_module:
            orig_done_picking_ids = orig_move_ids.move_dest_ids.picking_id.filtered(
                lambda picking: picking.state == "done")
        is_return = list(filter(lambda x: x.get('restock_type') == 'return', refunds_data[0].get('refund_line_items')))
        if not orig_done_picking_ids and is_return:
            message = "Done picking is not available, so return can't be generated."
        need_to_remove_lines = []
        for picking_id in orig_done_picking_ids:
            return_picking_ids = self.picking_ids.filtered(lambda x: "Return of" in x.origin)
            stock_return_picking_form = Form(self.env['stock.return.picking'].with_context(
                active_ids=picking_id.ids,
                active_id=picking_id.ids[0],
                active_model='stock.picking'
            ))
            if self.shopify_instance_id.return_location_id:
                stock_return_picking_form.location_id = self.shopify_instance_id.return_location_id
            return_wiz = stock_return_picking_form.save()
            for return_move_line in return_wiz.product_return_moves:
                refund_line = next(
                    (item for item in refund_line_items if item["product_id"] == return_move_line.product_id.id),
                    None)
                # if refund_line and return_move_line.product_id.id == refund_line["product_id"]:
                if refund_line:
                    qty_to_return = refund_line["quantity"]
                    existing_return_qty = return_picking_ids.move_ids.filtered(
                        lambda x: x.product_id.id == refund_line["product_id"]).mapped('product_uom_qty')
                    return_qty = sum(existing_return_qty)

                    if qty_to_return > return_qty:
                        return_move_line.write({
                            'quantity': qty_to_return - return_qty,
                            'to_refund': True
                        })
                    else:
                        need_to_remove_lines.append(return_move_line)
                else:
                    need_to_remove_lines.append(return_move_line)

            for need_to_remove_line in need_to_remove_lines:
                need_to_remove_line.unlink()
            if return_wiz.product_return_moves:
                res = return_wiz.create_returns()
                return_picking = self.env['stock.picking'].browse(res['res_id'])
                return_picking.message_post(
                    body=_("Return Picking is Generated by Webhook as Order is Refunded in Shopify."))
                if return_picking:
                    if self.shopify_instance_id.stock_validate_for_return:
                        action_wizard = return_picking.button_validate()
                        immediate_transfer = Form(
                            self.env[action_wizard['res_model']].with_context(action_wizard['context'])).save()
                        immediate_transfer.process()
                        return_picking.message_post(body=_("Return Picking is Validate by Webhook."))
        return message

    def prepare_refund_data(self, refunds_data):
        refund_line_items = []
        for refund_data_line in refunds_data:
            for refund_line in refund_data_line.get("refund_line_items"):
                if refund_line.get("restock_type") == "return":
                    product_id = self.order_line.filtered(
                        lambda x: x.shopify_line_id == str(refund_line.get("line_item_id"))).product_id
                    bom_lines = self.check_for_bom_product(product_id)
                    for bom_line in bom_lines:
                        bom_product = bom_line[0].product_id
                        bom_product_qty = (bom_line[1].get('qty', 0)) * refund_line.get("quantity")
                        existing_entry = next(
                            (item for item in refund_line_items if item["product_id"] == bom_product.id),
                            None)
                        if existing_entry:
                            existing_entry["quantity"] += bom_product_qty
                        else:
                            refund_line_items.append({"quantity": bom_product_qty, "product_id": bom_product.id})
                    if not bom_lines:
                        existing_entry = next(
                            (item for item in refund_line_items if item["product_id"] == product_id.id),
                            None)
                        if existing_entry:
                            existing_entry["quantity"] += refund_line.get("quantity")
                        else:
                            refund_line_items.append(
                                {"quantity": refund_line.get("quantity"), "product_id": product_id.id})
        return refund_line_items

    def process_order_refund_data_ept(self, shopify_status, order_data, order, created_by, instance, queue_line):
        common_log_line_obj = self.env["common.log.lines.ept"]
        message = self.create_shipped_order_refund(shopify_status, order_data, order, created_by)
        if message:
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, message=message,
                                                           module="shopify_ept",
                                                           model_name='sale.order',
                                                           order_ref=order_data.get('name'),
                                                           shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
            queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
        else:
            queue_line.state = "done"

    def create_shipped_order_refund(self, shopify_financial_status, order_response, sale_order, created_by):
        """ This method is used to create partially or fully refund in shopify order.
            @param : self
            @return: message
            @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 27 November 2021 .
            Task_id: 179249
        """
        message = ""
        if shopify_financial_status == "refunded" or "partially_refunded" and order_response.get(
                "refunds"):
            is_need_create_refund = False
            for refund in order_response.get('refunds'):
                for transaction in refund.get('transactions'):
                    if transaction.get('kind') == 'refund' and transaction.get('status') == 'success':
                        is_need_create_refund = True

            if is_need_create_refund:
                message = sale_order.create_shopify_partially_refund(order_response.get("refunds"),
                                                                     order_response.get('name'), created_by,
                                                                     shopify_financial_status)
            self.prepare_vals_shopify_multi_payment_refund(order_response.get("refunds"), sale_order)
        return message

    def prepare_vals_shopify_multi_payment_refund(self, order_refunds, order):
        """ This method is used to manage multi payment wise remaining refund amount.
            @param : order_refunds,order
            @return: True
            @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 15 Feb 2022.
            Task_id: 183797
        """
        for refund in order_refunds:
            for transaction in refund.get('transactions'):
                for payment_record in order.shopify_payment_ids:
                    if payment_record.payment_gateway_id.name == transaction.get('gateway'):
                        total_amount = payment_record.remaining_refund_amount - float(transaction.get('amount'))
                        payment_record.write({'remaining_refund_amount': abs(total_amount)})
        return True

    def search_existing_shopify_order(self, order_response, instance, order_number):
        """ This method is used to search the existing shopify order.
            @param : self
            @return: sale_order
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 27 October 2020 .
            Task_id: 167537
        """

        sale_order = self.search([("shopify_order_id", "=", order_response.get("id")),
                                  ("shopify_instance_id", "=", instance.id),
                                  ("shopify_order_number", "=", order_number)])
        if not sale_order:
            sale_order = self.search([("shopify_instance_id", "=", instance.id),
                                      ("client_order_ref", "=", order_response.get("name"))])

        return sale_order

    def check_mismatch_details(self, lines, instance, order_number, order_data_queue_line):
        """This method used to check the mismatch details in the order lines.
            @param : self, lines, instance, order_number, order_data_queue_line
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 11/11/2019.
            Task Id : 157350
        """
        shopify_product_template_obj = self.env["shopify.product.template.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        mismatch = False

        for line in lines:
            shopify_variant = self.search_shopify_variant(line, instance)
            if shopify_variant:
                continue
            # Below lines are used for the search gift card product, Task 169381.
            if line.get('gift_card', False):
                product = instance.gift_card_product_id or False
                if product:
                    continue
                message = "Please upgrade the module and then try to import order(%s).\n Maybe the Gift Card " \
                          "product " \
                          "has been deleted, it will be recreated at the time of module upgrade." % order_number
                common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, module="shopify_ept",
                                                               message=message,
                                                               model_name='sale.order', order_ref=order_number,
                                                               shopify_order_data_queue_line_id=order_data_queue_line.id if order_data_queue_line else False)
                mismatch = True
                break

            if not shopify_variant:
                line_variant_id = line.get("variant_id", False)
                line_product_id = line.get("product_id", False)
                if line_product_id and line_variant_id:
                    shopify_product_template_obj.shopify_sync_products(False, line_product_id,
                                                                       instance,
                                                                       order_data_queue_line)
                    shopify_variant = self.search_shopify_variant(line, instance)
                    if not shopify_variant:
                        message = "Product [%s][%s] not found for Order %s" % (
                            line.get("sku"), line.get("name"), order_number)
                        common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id,
                                                                       module="shopify_ept", message=message,
                                                                       model_name='sale.order', order_ref=order_number,
                                                                       shopify_order_data_queue_line_id=order_data_queue_line.id if order_data_queue_line else False)
                        mismatch = True
                        break
        return mismatch

    def search_shopify_variant(self, line, instance):
        """ This method is used to search the Shopify variant.
            :param line: Response of order line.
            @return: shopify_variant.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
            Task_id: 167537
        """
        shopify_variant = False
        shopify_product_obj = self.env["shopify.product.product.ept"]
        sku = line.get("sku") or False
        if line.get("variant_id", None):
            shopify_variant = shopify_product_obj.search(
                [("variant_id", "=", line.get("variant_id")),
                 ("shopify_instance_id", "=", instance.id), ('exported_in_shopify', '=', True)])
        if not shopify_variant and sku:
            shopify_variant = shopify_product_obj.search(
                [("default_code", "=", sku),
                 ("shopify_instance_id", "=", instance.id), ('exported_in_shopify', '=', True)])
        return shopify_variant

    def shopify_create_order(self, instance, partner, shipping_address, invoice_address,
                             order_data_queue_line, order_response, lines, order_number):
        """This method used to create a sale order and it's line.
            @param : self, instance, partner, shipping_address, invoice_address,order_data_queue_line, order_response
            @return: order
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 12/11/2019.
            Task Id : 157350
            @change : if configuration on for Create delivery fee than going to create order line for delivery fee
            @change by : Nilam Kubavat at 09-Aug-2022 for task id : 197829
        """
        payment_gateway_obj = self.env["shopify.payment.gateway.ept"]
        gateway = "no_payment_gateway"
        payment_gateway_names = order_response.get('payment_gateway_names')
        transaction = order_response.get('transaction')
        if payment_gateway_names and payment_gateway_names[0]:
            if len(payment_gateway_names) == 1:
                gateway = payment_gateway_names[0]
            # elif 'gift_card' in payment_gateway_names:
            #     gateway = [val for val in payment_gateway_names if val != 'gift_card'][0]
            else:
                if order_response.get('transaction'):
                    for transaction in order_response.get('transaction'):
                        if transaction.get('status') == 'failure':
                            continue
                        if "Cash on Delivery" in transaction.get("gateway"):
                            gateway = transaction.get("gateway")
                        elif transaction.get('gateway') != 'gift_card' and transaction.get("status") == 'success':
                            gateway = transaction.get("gateway")

        payment_gateway, workflow, payment_term = \
            payment_gateway_obj.shopify_search_create_gateway_workflow(instance, order_data_queue_line, order_response,
                                                                       gateway)

        if not all([payment_gateway, workflow]):
            return False

        order_vals = self.prepare_shopify_order_vals(instance, partner, shipping_address,
                                                     invoice_address, order_response,
                                                     payment_gateway,
                                                     workflow)
        order_vals.update({'payment_term_id': payment_term and payment_term.id or False})
        is_create_order = self.check_sale_order_validation(instance, order_response, order_vals, order_data_queue_line)
        if not is_create_order:
            return False
        payments = []
        if len(order_response.get('payment_gateway_names')) > 1 and order_response.get('financial_status') != 'voided':
            for transaction in order_response.get('transaction'):
                if "Cash on Delivery" in transaction.get("gateway") or transaction.get('status') == 'success':
                    payments.append(transaction.get("gateway"))
            if len(list(set(payments))) > 1:
                payment_vals = self.prepare_vals_shopify_multi_payment(instance, order_data_queue_line, order_response,
                                                                       payment_gateway, workflow)
                if not payment_vals:
                    return False
                order_vals.update({'shopify_payment_ids': payment_vals, 'is_shopify_multi_payment': True})

        order = self.create(order_vals)

        _logger.info("Creating order lines for Odoo order(%s) and Shopify order is (%s).", order.name, order_number)
        order.create_shopify_order_lines(lines, order_response, instance)

        _logger.info("Created order lines for Odoo order(%s) and Shopify order is (%s)", order.name, order_number)

        order.create_shopify_shipping_lines(order_response, instance)
        _logger.info("Created Shipping lines for order (%s).", order.name)

        if instance.is_delivery_fee:
            order.create_shopify_Delivery_Fee_lines(order_response, instance)
            _logger.info("Created Delivery Fee for order (%s).", order.name)

        if instance.is_delivery_multi_warehouse:
            self.set_line_warehouse_based_on_location(order, instance, order_response)
        # self.set_fulfilment_order_id_and_fulfillment_line_id(order, instance, order_response)
        return order

    def check_sale_order_validation(self, instance, order_response, order_vals, order_data_queue_line):
        """
        This method use for Check customer, Order Date, price list, warehouse and picking policy available in Order
        Response.
        :param order_vals:
        @author: Yagnik Joshi on Date 28-12-2023.
        """
        is_create_order = True
        common_log_line_obj = self.env["common.log.lines.ept"]
        error_messages = []

        if order_response.get('shipping_lines', []):
            shipping_product = instance.shipping_product_id

            if not shipping_product:
                is_create_order = False
                error_messages.append(
                    " When creating a new delivery method, the system encountered an issue as it could not find the shipping product in the instance configuration.  " \
                    " \n - This resulted in the failure of the system to create the new delivery method. \n - To resolve this issue, please follow these steps: %s." \
                    " \n 1 Go to Shopify >> Instance >> Default Products.  \n 2 Review whether the shipping product is set. \n 3 If already set, ensure that it is active in Odoo. ")

        if not order_vals.get('pricelist_id'):
            is_create_order = False
            error_messages.append(
                " The order import operation failed because the price list configuration was not found in the instance configuration. " \
                " \n To resolve this issue, navigate to Shopify >> Configuration >> Settings, select instance and configure Instance Price list")

        if not order_vals.get('warehouse_id'):
            is_create_order = False
            error_messages.append(
                " The order import operation failed because the warehouse configuration was not found in the instance configuration. " \
                " \n To resolve this issue, navigate to Shopify >> Configuration >> Settings, select instance and configure warehouse")

        if not order_vals.get('picking_policy'):
            is_create_order = False
            error_messages.append(
                " The order import operation failed because the shipping policy configuration was not found in the auto invoice workflow configuration. " \
                " \n To resolve this issue, navigate to Shopify >> Configuration >> Financial Status. Review whether Auto workflow is configured, and within Auto workflow, ensure that the shipping policy is also configured.")

        # Create a log for each error message
        for message in error_messages:
            common_log_line_obj.create_common_log_line_ept(
                shopify_instance_id=instance.id,
                message=message,
                module="shopify_ept",
                model_name='sale.order',
                order_ref=order_response.get('name'),
                shopify_order_data_queue_line_id=order_data_queue_line.id if order_data_queue_line else False
            )

        return is_create_order

    def set_fulfilment_order_id_and_fulfillment_line_id(self, order, picking):
        """
        This method sets order line warehouse based on Shopify Location.
        @author:Meera Sidapara @Emipro Technologies Pvt. Ltd on date 07 September 2022.
        Task Id : 199989 - Fulfillment location wise order
        """
        shopify_order_id = order.shopify_order_id
        move_ids = picking.move_ids
        stock_moves = move_ids.filtered(lambda move: move.shopify_fulfillment_line_id)
        backorders = picking.backorder_ids.filtered(lambda order: not order.updated_in_shopify)
        if stock_moves and backorders:
            self.set_backorder_fulfillment_data(backorders, stock_moves)
        fulfillment_order_data = []
        fulfillment_order = False
        if not stock_moves:
            try:
                fulfillment_order = shopify.fulfillment.FulfillmentOrders.find(order_id=int(shopify_order_id))
                for order_data in fulfillment_order:
                    order_data = order_data.to_dict()
                    if order_data.get('status') != 'closed':
                        fulfillment_order_data.append(order_data)
            except Exception as Error:
                _logger.info("Error in Request of shopify fulfillment order for the fulfilment. Error: %s", Error)
            for data in fulfillment_order_data:
                for line in data.get('line_items'):
                    if isinstance(data.get('delivery_method'), dict) and data.get('delivery_method').get(
                            'method_type') == 'none':
                        order_line = order.order_line.filtered(
                            lambda line_item: line_item.shopify_line_id == str(line.get('line_item_id')))
                        if order_line:
                            order_line.write(
                                {'shopify_fulfillment_order_id': line.get('fulfillment_order_id'),
                                 'shopify_fulfillment_line_id': line.get('id'),
                                 'shopify_fulfillment_order_status': data.get('status')})
                            self._cr.commit()
                        # continue
                    stock_move = move_ids.filtered(
                        lambda move: not move.shopify_fulfillment_line_id and move.sale_line_id
                                     and move.sale_line_id.shopify_line_id == str(line.get('line_item_id')))
                    if stock_move:
                        stock_move.write(
                            {'shopify_fulfillment_order_id': line.get('fulfillment_order_id'),
                             'shopify_fulfillment_line_id': line.get('id'),
                             'shopify_fulfillment_order_status': data.get('status')})
                        self._cr.commit()
                        if backorders:
                            self.set_backorder_fulfillment_data(backorders, stock_move)
        return fulfillment_order

    def set_backorder_fulfillment_data(self, backorder, stock_moves):
        """
        This method sets backorder Fulfillment data.
        @author: Nilam Kubavat @Emipro Technologies Pvt. Ltd on date 08 August 2023.
        Task Id : 240507
        """
        for stock_move in stock_moves.filtered(lambda move: move.shopify_fulfillment_order_status == 'in_progress'):
            backorder_move = backorder.move_ids.filtered(
                lambda move_line: not move_line.shopify_fulfillment_line_id
                                  and move_line.product_id.id == stock_move.product_id.id)
            backorder_move.write({'shopify_fulfillment_order_id': stock_move.shopify_fulfillment_order_id,
                                  'shopify_fulfillment_line_id': stock_move.shopify_fulfillment_line_id,
                                  'shopify_fulfillment_order_status': stock_move.shopify_fulfillment_order_status})
        return True

    def set_line_warehouse_based_on_location(self, order, instance, order_response):
        """
        This method sets order line warehouse based on Shopify Location.
        @author:Meera Sidapara @Emipro Technologies Pvt. Ltd on date 07 September 2022.
        Task Id : 199989 - Fulfillment location wise order
        """
        shopify_location_obj = self.env['shopify.location.ept']
        shopify_order_id = order.shopify_order_id
        if not order_response.get('fulfillment_data'):
            shopify_order = shopify.Order().find(shopify_order_id)
            order_response["fulfillment_data"] = shopify_order.get('fulfillment_orders')
        fulfillment_data = order_response.get('fulfillment_data')
        for data in fulfillment_data:
            shopify_location_id = data.get('assigned_location_id')
            line_item_ids = [str(line.get('line_item_id')) for line in data.get('line_items')]
            order_line = order.order_line.filtered(lambda line_item: line_item.shopify_line_id in line_item_ids)
            line_warehouse_id = shopify_location_obj.search(
                [('shopify_location_id', '=', shopify_location_id)]).warehouse_for_order
            order_line.write(
                {'warehouse_id_ept': line_warehouse_id.id if line_warehouse_id else instance.shopify_warehouse_id.id})
        return True

    def create_shopify_Delivery_Fee_lines(self, order_response, instance):
        """
        Creates Delivery Fee lines for shopify orders.
        @author: Nilam Kubavat @Emipro Technologies Pvt. Ltd on date 09-Aug-2022
        Task Id : 197829
        """
        shipping_product = instance.shipping_product_id
        for line in order_response.get("tax_lines", []):
            if line.get('title') == instance.delivery_fee_name:
                delivery_fee_price = line.get("price")
                if instance.order_visible_currency:
                    delivery_fee_price = self.get_price_based_on_customer_visible_currency(line.get("price_set"),
                                                                                           order_response,
                                                                                           delivery_fee_price)
                order_line = self.shopify_create_sale_order_line(line, shipping_product, 1,
                                                                 line.get('title'),
                                                                 delivery_fee_price,
                                                                 order_response)
                order_line.name = line.get('title')

    def prepare_shopify_order_vals(self, instance, partner, shipping_address,
                                   invoice_address, order_response, payment_gateway,
                                   workflow):
        """
        This method used to Prepare a order vals.
        @param : self, instance, partner, shipping_address,invoice_address, order_response, payment_gateway,workflow
        @return: order_vals
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 13/11/2019.
        Task Id : 157350
        """
        date_order = self.convert_order_date(order_response)
        pricelist_id = self.shopify_set_pricelist(order_response=order_response, instance=instance)

        ordervals = {
            "company_id": instance.shopify_company_id.id if instance.shopify_company_id else False,
            "partner_id": partner.ids[0],
            "partner_invoice_id": invoice_address.ids[0],
            "partner_shipping_id": shipping_address.ids[0],
            "warehouse_id": instance.shopify_warehouse_id.id if instance.shopify_warehouse_id else False,
            "date_order": date_order,
            "state": "draft",
            "pricelist_id": pricelist_id.id if pricelist_id else False,
            "team_id": instance.shopify_section_id.id if instance.shopify_section_id else False,
        }
        # ordervals = self.create_sales_order_vals_ept(ordervals)
        order_response_vals = self.prepare_order_vals_from_order_response(order_response, instance, workflow,
                                                                          payment_gateway)
        ordervals.update(order_response_vals)
        if not instance.is_use_default_sequence:
            if instance.shopify_order_prefix:
                name = "%s_%s" % (instance.shopify_order_prefix, order_response.get("name"))
            else:
                name = order_response.get("name")
            ordervals.update({"name": name})
        return ordervals

    def create_or_search_sale_tag(self, tag):
        crm_tag_obj = self.env['crm.tag']
        exists_tag = crm_tag_obj.search([('name', '=ilike', tag)], limit=1)
        if not exists_tag:
            exists_tag = crm_tag_obj.create({'name': tag})
        return exists_tag.id

    def convert_order_date(self, order_response):
        """ This method is used to convert the order date in UTC and formate("%Y-%m-%d %H:%M:%S").
            :param order_response: Order response
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
            Task_id: 167537
        """
        if order_response.get("created_at", False):
            order_date = order_response.get("created_at", False)
            date_order = parser.parse(order_date).astimezone(utc).strftime("%Y-%m-%d %H:%M:%S")
        else:
            date_order = time.strftime("%Y-%m-%d %H:%M:%S")
            date_order = str(date_order)

        return date_order

    def prepare_order_vals_from_order_response(self, order_response, instance, workflow, payment_gateway):
        """ This method is used to prepare vals from the order response.
            :param order_response: Response of order.
            :param instance: Record of instance.
            :param workflow: Record of auto invoice workflow.
            :param payment_gateway: Record of payment gateway.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
            Task_id: 167537
            @change : pass tag_ids on vals by Nilam Kubavat for task id : 190111 at 19/05/2022
        """
        utm_source, utm_medium, utm_campaign = self.set_utm_source_medium_campaign(order_response)
        tags = order_response.get("tags").split(",") if order_response.get("tags") != '' else order_response.get("tags")
        tag_ids = []
        for tag in tags:
            tag_ids.append(self.create_or_search_sale_tag(tag))
        order_vals = {
            "checkout_id": order_response.get("checkout_id"),
            "note": order_response.get("note") if order_response.get("note") else '',
            "shopify_order_id": order_response.get("id"),
            "shopify_order_number": order_response.get("order_number"),
            "shopify_payment_gateway_id": payment_gateway and payment_gateway.id or False,
            "shopify_instance_id": instance.id,
            "shopify_order_status": order_response.get("fulfillment_status") or "unfulfilled",
            "picking_policy": workflow.picking_policy or False,
            "auto_workflow_process_id": workflow and workflow.id,
            "client_order_ref": order_response.get("name"),
            "analytic_account_id": instance.shopify_analytic_account_id.id if instance.shopify_analytic_account_id else False,
            "tag_ids": tag_ids,
            "source_id": utm_source and utm_source.id or False,
            "medium_id": utm_medium and utm_medium.id or False,
            "campaign_id": utm_campaign and utm_campaign.id or False,
            "is_buy_with_prime_order": order_response.get("buy_with_prime") or False,
        }
        if self.env["ir.config_parameter"].sudo().get_param("shopify_ept.use_default_terms_and_condition_of_odoo"):
            order_vals = self.prepare_order_note_with_customer_note(order_vals)
        return order_vals

    def set_utm_source_medium_campaign(self, order_response):
        """
        This method use to find or create utm source medium and campaign.
        @author: Yagnik Joshi @Emipro Technologies Pvt. Ltd on date 24th Feb 2023.
        Task id: 218869
        """
        utm_source_obj = self.env['utm.source']
        utm_campaign_obj = self.env['utm.campaign']
        utm_medium_obj = self.env['utm.medium']
        utm_source = False
        utm_medium = False
        utm_campaign = False
        utm_dict = {}
        if order_response.get('landing_site') and order_response.get('landing_site').find('utm') >= 0:
            UTM_data = {sub for sub in order_response.get('landing_site')[1:-1].split("&")}
            for utm_split in UTM_data:
                if utm_split.find('utm') >= 0 and utm_split.find('=') >= 0:
                    utm_dict.update({utm_split.split("=")[0]: utm_split.split("=")[1]})

            if utm_dict.get('utm_source'):
                utm_source = utm_source_obj.search([('name', '=ilike', utm_dict.get('utm_source'))], limit=1)
                if not utm_source:
                    utm_source = utm_source_obj.create({'name': utm_dict.get('utm_source')})

            if utm_dict.get('utm_medium'):
                utm_medium = utm_medium_obj.search([('name', '=ilike', utm_dict.get('utm_medium'))], limit=1)
                if not utm_medium:
                    utm_medium = utm_medium_obj.create({'name': utm_dict.get('utm_medium')})

            if utm_dict.get('utm_campaign'):
                utm_campaign = utm_campaign_obj.search([('name', '=ilike', utm_dict.get('utm_campaign'))], limit=1)
                if not utm_campaign:
                    utm_campaign = utm_campaign_obj.create({'name': utm_dict.get('utm_campaign')})

        if not utm_source:
            utm_source = self.find_or_create_shopify_source(order_response.get('source_name'))

        return utm_source, utm_medium, utm_campaign

    def find_or_create_shopify_source(self, source):
        """
        This method is used to find or create shopify source in utm.source.
        @param source: Shopify order source
        @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 19 April 2022.
        Task_id: 187155
        """
        utm_source_obj = self.env['utm.source']
        source_id = utm_source_obj.search([('name', '=ilike', source)], limit=1)
        if not source_id:
            source_id = utm_source_obj.create({'name': source})
        return source_id

    def shopify_set_pricelist(self, instance, order_response):
        """
        Author:Bhavesh Jadav 09/12/2019 for the for set price list based on the order response currency because of if
        order currency different then the erp currency so we need to set proper pricelist for that sale order
        otherwise set pricelist based on instance configurations
        """
        currency_obj = self.env["res.currency"]
        pricelist_obj = self.env["product.pricelist"]
        order_currency = order_response.get(
            "presentment_currency") if instance.order_visible_currency else order_response.get("currency") or False
        if order_currency:
            currency = currency_obj.search([("name", "=", order_currency)])
            if instance.shopify_pricelist_id.currency_id.id == currency.id:
                return instance.shopify_pricelist_id
            if not currency:
                currency = currency_obj.search(
                    [("name", "=", order_currency), ("active", "=", False)])
            if currency:
                currency.write({"active": True})
                pricelist = pricelist_obj.search(
                    [("currency_id", "=", currency.id), ("company_id", "=", instance.shopify_company_id.id)],
                    limit=1)
                if pricelist:
                    return pricelist
                pricelist_vals = {"name": currency.name,
                                  "currency_id": currency.id,
                                  "company_id": instance.shopify_company_id.id}
                pricelist = pricelist_obj.create(pricelist_vals)
                return pricelist
            pricelist = pricelist_obj.search([("currency_id", "=", currency.id)], limit=1)
            return pricelist
        pricelist = instance.shopify_pricelist_id if instance.shopify_pricelist_id else False
        return pricelist

    def search_shopify_product_for_order_line(self, line, instance):
        """This method used to search shopify product for order line.
            @param : self, line, instance
            @return: shopify_product
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 14/11/2019.
            Task Id : 157350
        """
        shopify_product_obj = self.env["shopify.product.product.ept"]
        variant_id = line.get("variant_id")
        shopify_product = shopify_product_obj.search(
            [("shopify_instance_id", "=", instance.id), ("variant_id", "=", variant_id),
             ('exported_in_shopify', '=', True)], limit=1)
        if not shopify_product:
            shopify_product = shopify_product_obj.search([("shopify_instance_id", "=", instance.id),
                                                          ("default_code", "=", line.get("sku")),
                                                          ('exported_in_shopify', '=', True)], limit=1)
            shopify_product.write({"variant_id": variant_id})
        return shopify_product

    def shopify_create_sale_order_line(self, line, product, quantity, product_name, price,
                                       order_response, is_shipping=False, previous_line=False,
                                       is_discount=False, is_duties=False):
        """
        This method used to create a sale order line.
        @param : self, line, product, quantity,product_name, order_id,price, is_shipping=False
        @return: order_line_id
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 14/11/2019.
        Task Id : 157350
        """
        sale_order_line_obj = self.env["sale.order.line"]
        instance = self.shopify_instance_id
        line_vals = self.prepare_vals_for_sale_order_line(product, product_name, price, quantity)
        # order_line_vals = sale_order_line_obj.create_sale_order_line_ept(line_vals)
        order_line_vals = self.shopify_set_tax_in_sale_order_line(instance, line, order_response, is_shipping,
                                                                  is_discount, previous_line, line_vals,
                                                                  is_duties)
        if is_discount:
            order_line_vals["name"] = "Discount for " + str(product_name)
            if instance.apply_tax_in_order == "odoo_tax" and previous_line:
                order_line_vals["tax_id"] = previous_line.tax_id

        if is_duties:
            order_line_vals["name"] = "Duties for " + str(product_name)
            if instance.apply_tax_in_order == "odoo_tax" and previous_line:
                order_line_vals["tax_id"] = previous_line.tax_id

        # shopify_analytic_tag_ids = instance.shopify_analytic_tag_ids.ids
        order_line_vals.update({
            "shopify_line_id": line.get("id"),
            "is_delivery": is_shipping,
            # "analytic_tag_ids": [(6, 0, shopify_analytic_tag_ids)],
        })
        order_line = sale_order_line_obj.create(order_line_vals)
        order_line.with_context(round=False)._compute_amount()
        return order_line

    def prepare_vals_for_sale_order_line(self, product, product_name, price, quantity):
        """ This method is used to prepare a vals to create a sale order line.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19 October 2020 .
        """
        uom_id = product and product.uom_id and product.uom_id.id or False
        line_vals = {
            "product_id": product and product.ids[0] or False,
            "order_id": self.id,
            "company_id": self.company_id.id,
            "product_uom": uom_id,
            # "name": product_name,
            "price_unit": price,
            "product_uom_qty": quantity
            # "order_qty": quantity,
        }
        return line_vals

    def shopify_set_tax_in_sale_order_line(self, instance, line, order_response, is_shipping, is_discount,
                                           previous_line, order_line_vals, is_duties):
        """ This method is used to set tax in the sale order line base on tax configuration in the
            Shopify setting in Odoo.
            :param line: Response of sale order line.
            :param order_response: Response of order.
            :param is_shipping: It used to identify that it a shipping line.
            :param is_discount: It used to identify that it a discount line.
            :param is_duties: It used to identify that it a duties line.
            :param previous_line: Record of the previously created sale order line.
            :param order_line_vals: Prepared sale order line vals as the previous method.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20 October 2020 .
            Task_id: 167537
        """
        if instance.apply_tax_in_order == "create_shopify_tax":
            taxes_included = order_response.get("taxes_included") or False
            tax_ids = []
            if line and line.get("tax_lines"):
                if line.get("taxable"):
                    # This is used for when the one product is taxable and another product is not
                    # taxable
                    tax_ids = self.shopify_get_tax_id_ept(instance,
                                                          line.get("tax_lines"),
                                                          taxes_included)
                if is_shipping:
                    # In the Shopify store there is configuration regarding tax is applicable on shipping or not,
                    # if applicable then this use.
                    tax_ids = self.shopify_get_tax_id_ept(instance,
                                                          line.get("tax_lines"),
                                                          taxes_included)
                if is_duties:
                    # In the Shopify store there is configuration regarding tax is applicable on line duties or not,
                    # if applicable then this use.
                    tax_ids = self.shopify_get_tax_id_ept(instance,
                                                          line.get("tax_lines"),
                                                          taxes_included)
            elif not line and previous_line:
                # Before modification, connector set order taxes on discount line but as per connector design,
                # we are creating discount line base on sale order line so it should apply sale order line taxes
                # in discount line not order taxes. It creates a problem while the customer is using multi taxes
                # in sale orders. so set the previous line taxes on the discount line.
                tax_ids = [(6, 0, previous_line.tax_id.ids)]
            order_line_vals["tax_id"] = tax_ids
            # When the one order with two products one product with tax and another product
            # without tax and apply the discount on order that time not apply tax on discount
            # which is
            if is_discount and not previous_line.tax_id:
                order_line_vals["tax_id"] = []
        return order_line_vals

    @api.model
    def shopify_get_tax_id_ept(self, instance, tax_lines, tax_included):
        """This method used to search tax in Odoo, If tax is not found in Odoo then it call child method to create a
            new tax in Odoo base on received tax response in order response.
            @return: tax_id
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 18/11/2019.
            Task Id : 157350
        """
        tax_id = []
        taxes = []
        company = instance.shopify_warehouse_id.company_id
        for tax in tax_lines:
            rate = float(tax.get("rate", 0.0))
            price = float(tax.get('price', 0.0))
            title = tax.get("title")
            rate = rate * 100
            if rate != 0.0 and price != 0.0:
                if tax_included:
                    name = "%s_(%s %s included)_%s" % (title, str(rate), "%", company.name)
                else:
                    name = "%s_(%s %s excluded)_%s" % (title, str(rate), "%", company.name)
                tax_id = self.env["account.tax"].search([("price_include", "=", tax_included),
                                                         ("type_tax_use", "=", "sale"), ("amount", "=", rate),
                                                         ("name", "=", name), ("company_id", "=", company.id)], limit=1)
                if not tax_id:
                    tax_id = self.sudo().shopify_create_account_tax(instance, rate, tax_included, company, name)
                if tax_id:
                    taxes.append(tax_id.id)
        if taxes:
            tax_id = [(6, 0, taxes)]
        return tax_id

    @api.model
    def shopify_create_account_tax(self, instance, value, price_included, company, name):
        """This method used to create tax in Odoo when importing orders from Shopify to Odoo.
            @param : self, value, price_included, company, name
            @return: account_tax_id
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 18/11/2019.
            Task Id : 157350
        """
        account_tax_obj = self.env["account.tax"]

        account_tax_id = account_tax_obj.create({"name": name, "amount": float(value),
                                                 "type_tax_use": "sale", "price_include": price_included,
                                                 "company_id": company.id})

        account_tax_id.mapped("invoice_repartition_line_ids").write(
            {"account_id": instance.invoice_tax_account_id.id if instance.invoice_tax_account_id else False})
        account_tax_id.mapped("refund_repartition_line_ids").write(
            {"account_id": instance.credit_tax_account_id.id if instance.credit_tax_account_id else False})

        return account_tax_id

    def prepare_final_list_of_transactions(self, transactions):
        """ This method is used to prepare a final order transactions list.
            @author: Yagnik Joshi @Emipro Technologies Pvt. Ltd on date 2 May 2023.
        """
        final_transactions_result = []
        for result in transactions:
            if result.get('kind') in ['void', 'capture', 'authorization'] and result.get(
                    'status') == 'success' and result.get('parent_id'):
                dict_index = next((index for (index, transaction_data) in enumerate(final_transactions_result) if
                                   transaction_data["id"] == result.get('parent_id')), None)
                if dict_index != None:
                    del final_transactions_result[dict_index]
            if result.get('kind') in ['capture', 'sale', 'authorization'] and result.get('status') == 'success':
                final_transactions_result.append(result)
        return final_transactions_result

    def prepare_vals_shopify_multi_payment(self, instance, order_data_queue_line, order_response,
                                           payment_gateway, workflow):
        """ This method is used to prepare a values for the multi payment.
            @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 16/11/2021 .
            Task_id:179257 - Manage multiple payment.
        """
        payment_gateway_obj = self.env["shopify.payment.gateway.ept"]
        payment_list_vals = []
        final_transactions_results = self.prepare_final_list_of_transactions(order_response.get('transaction'))
        for result in final_transactions_results:
            payment_transaction_id = result.get('id')
            gateway = result.get('gateway')
            amount = result.get('amount')
            # if order_response.get('gateway') == gateway:
            #     payment_list = (0, 0, {'payment_gateway_id': payment_gateway.id, 'workflow_id': workflow.id,
            #                            'amount': amount, 'payment_transaction_id': payment_transaction_id,
            #                            'remaining_refund_amount': amount})
            #     payment_list_vals.append(payment_list)
            #     continue
            new_payment_gateway, new_workflow, payment_term = \
                payment_gateway_obj.shopify_search_create_gateway_workflow(instance,
                                                                           order_data_queue_line,
                                                                           order_response,
                                                                           gateway)
            if not all([new_payment_gateway, new_workflow]):
                return False
            payment_list = (0, 0, {'payment_gateway_id': new_payment_gateway.id, 'workflow_id': new_workflow.id,
                                   'amount': amount, 'payment_transaction_id': payment_transaction_id,
                                   'remaining_refund_amount': amount})
            payment_list_vals.append(payment_list)
        return payment_list_vals

    @api.model
    def closed_at(self, instance):
        """
        This method is used to close orders in the Shopify store after the update fulfillment
        from Odoo to the Shopify store.
        """
        order_id = self.env.context.get('order_id', False)
        if order_id:
            sales_orders = order_id
        else:
            sales_orders = self.search([('warehouse_id', '=', instance.shopify_warehouse_id.id),
                                        ('shopify_order_id', '!=', False),
                                        ('shopify_instance_id', '=', instance.id),
                                        ('state', '=', 'done'), ('closed_at_ept', '=', False)],
                                       order='date_order')

        instance.connect_in_shopify()

        for sale_order in sales_orders:
            order = shopify.Order.find(sale_order.shopify_order_id)
            if order:
                order.close()
                sale_order.write({'closed_at_ept': datetime.now()})
            else:
                _logger.info(_("System have not found order for close at shopify for order reference (%s)"),
                             sale_order.shopify_order_id)

        return True

    def get_shopify_carrier_code(self, picking):
        """
        Gives carrier name from picking, if available.
        @author: Maulik Barad on Date 16-Sep-2020.
        """
        carrier_name = ""
        if picking.carrier_id:
            carrier_name = picking.carrier_id.shopify_tracking_company or picking.carrier_id.shopify_source \
                           or picking.carrier_id.name or ''
        return carrier_name

    def prepare_tracking_numbers_and_lines_for_fulfilment(self, picking):
        """
        This method prepares tracking numbers' list and list of dictionaries of shopify line id and
        fulfilled qty for that.
        @author: Maulik Barad on Date 17-Sep-2020.
        Migration done by Haresh Mori on October 2021
        """
        fulfillment_line_ids = []
        # fulfillment_line_ids = not self.is_service_tracking_updated and self.order_line.filtered(
        #     lambda l: l.shopify_fulfillment_line_id and l.product_id.type == "service" and not l.is_delivery and not
        #     l.is_gift_card_line).mapped("shopify_fulfillment_line_id") or []

        # if picking.shopify_instance_id and not picking.shopify_instance_id.auto_fulfill_gift_card_order:
        #     fulfillment_line_ids = not self.is_service_tracking_updated and self.order_line.filtered(
        #         lambda l: l.shopify_fulfillment_line_id and l.product_id.type == "service" and
        #                   not l.is_delivery).mapped("shopify_fulfillment_line_id") or []
        moves = picking.move_ids.filtered(lambda line: line.shopify_fulfillment_line_id)
        product_moves = moves.filtered(lambda x: x.sale_line_id.product_id.id == x.product_id.id and x.state == "done")
        if picking.mapped("package_ids").filtered(lambda l: l.tracking_no):
            tracking_numbers, line_items = self.prepare_tracking_numbers_and_lines_for_multi_tracking_order(
                moves, product_moves)
        else:
            tracking_numbers, line_items = self.prepare_tracking_numbers_and_lines_for_simple_tracking_order(
                moves, product_moves, picking)
        # for line in fulfillment_line_ids:
        #     quantity = sum(
        #         self.order_line.filtered(lambda l: l.shopify_fulfillment_line_id == line).mapped("product_uom_qty"))
        #     line_items.append({"id": line, "quantity": int(quantity)})
        #     self.write({"is_service_tracking_updated": True})

        return tracking_numbers, line_items

    def prepare_tracking_numbers_and_lines_for_simple_tracking_order(self, moves, product_moves, picking):
        """ This method is used to prepare tracking numbers and line items for the simple tracking order.
            :param moves: Move lines of picking.
            :param product_moves: Filtered moves.
            @return: tracking_numbers, line_items
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20 October 2020 .
            Task_id: 167537
        """
        tracking_numbers = []
        line_items = []
        for move in product_moves.filtered(lambda line: line.product_id.detailed_type in ['product', 'consu']):
            fulfillment_line_id = move.shopify_fulfillment_line_id

            line_items.append({"id": fulfillment_line_id, "quantity": int(move.product_qty)})
            tracking_numbers.append(picking.carrier_tracking_ref or "")

        kit_sale_lines = moves.filtered(
            lambda x: x.sale_line_id.product_id.id != x.product_id.id and x.state == "done").sale_line_id
        for kit_sale_line in kit_sale_lines:
            # if product_moves and moves and product_moves in moves:
            #     kit_filtereded_move = moves - product_moves
            #     if kit_filtereded_move:
            #         moves = kit_filtereded_move
            fulfillment_line_id = kit_sale_line.move_ids[0].shopify_fulfillment_line_id
            line_items.append({"id": fulfillment_line_id, "quantity": int(kit_sale_line.product_qty)})
            tracking_numbers.append(picking.carrier_tracking_ref or "")
        return tracking_numbers, line_items

    def prepare_tracking_numbers_and_lines_for_multi_tracking_order(self, moves, product_moves):
        """ This method is used to prepare tracking numbers and line items for the simple tracking order.
            :param moves: Move lines of picking.
            :param product_moves: Filtered moves.
            @return: tracking_numbers, line_items
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20 October 2020 .
            Task_id: 167537
        """
        tracking_numbers = []
        line_items = []
        for move in product_moves:
            total_qty = 0
            fulfillment_line_id = move.shopify_fulfillment_line_id

            for move_line in move.move_line_ids:
                tracking_no = move_line.result_package_id.tracking_no or ""
                total_qty += move_line.qty_done
                tracking_numbers.append(tracking_no)

            line_items.append({"id": fulfillment_line_id, "quantity": int(total_qty)})

        kit_move_lines = moves.filtered(
            lambda x: x.sale_line_id.product_id.id != x.product_id.id and x.state == "done")
        existing_sale_line_ids = []
        for move in kit_move_lines:
            if move.sale_line_id.id in existing_sale_line_ids:
                continue

            fulfillment_line_id = move.shopify_fulfillment_line_id
            existing_sale_line_ids.append(move.sale_line_id.id)

            tracking_no = move.move_line_ids.result_package_id.mapped("tracking_no") or []
            tracking_no = tracking_no[0] if tracking_no else ""
            line_items.append({"id": fulfillment_line_id, "quantity": int(move.sale_line_id.product_uom_qty)})
            tracking_numbers.append(tracking_no)

        return tracking_numbers, line_items

    def update_order_status_in_shopify(self, instance, picking_ids=[]):
        """
        find the picking with below condition
            1. shopify_instance_id = instance.id
            2. updated_in_shopify = False
            3. state = Done
            4. location_dest_id.usage = customer
        get order line data from the picking and process on that. Process on only those products which type is
        not service get carrier_name from the picking get product qty from move lines. If one move having multiple
        move lines then total qty of all the move lines.
        shopify_line_id wise set the product qty_done set tracking details using shopify Fulfillment API update the
        order status
        @author: Maulik Barad on Date 16-Sep-2020.
        Task Id : 157905
        Migration done by Haresh Mori on October 2021
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        log_lines = []
        notify_customer = instance.notify_customer
        _logger.info(_("Update Order Status process start for '%s' Instance"), instance.name)

        instance.connect_in_shopify()
        if not picking_ids:
            picking_ids = self.shopify_search_picking_for_update_order_status(instance)
        for picking in picking_ids:
            carrier_name = self.get_shopify_carrier_code(picking)
            sale_order = picking.sale_id

            _logger.info("We are processing Sale order '%s' and Picking '%s'", sale_order.name, picking.name)
            is_continue_process, order_response = self.request_for_shopify_order(sale_order)
            if is_continue_process:
                continue
            # order_lines = sale_order.order_line
            # if order_lines and order_lines.filtered(
            #         lambda s: s.product_id.detailed_type != 'service' and not s.shopify_line_id):
            #     message = (_(
            #         "- Order status could not be updated for order %s.\n- Possible reason can be, Shopify order line "
            #         "reference is missing, which is used to update Shopify order status at Shopify store. "
            #         "\n- This might have happen because user may have done changes in order "
            #         "manually, after the order was imported.", sale_order.name))
            #     _logger.info(message)
            #     log_lines.append(
            #         common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id,
            #                                                        module="shopify_ept", message=message,
            #                                                        model_name=self._name,
            #                                                        order_ref=sale_order.client_order_ref))
            #     continue
            fulfillment_order = self.set_fulfilment_order_id_and_fulfillment_line_id(sale_order, picking)

            tracking_numbers, line_items = sale_order.prepare_tracking_numbers_and_lines_for_fulfilment(picking)

            if not line_items:
                message = "No order lines found for the update order shipping status for order [%s]" \
                          % sale_order.name
                _logger.info(message)
                log_lines.append(
                    common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id,
                                                                   module="shopify_ept", message=message,
                                                                   model_name=self._name,
                                                                   order_ref=sale_order.client_order_ref))
                continue

            if not fulfillment_order:
                shopify_order_id = sale_order.shopify_order_id
                fulfillment_order = shopify.fulfillment.FulfillmentOrders.find(order_id=int(shopify_order_id))
            if fulfillment_order and len(fulfillment_order) > 1:
                shopify_location_id, fulfillment_vals = self.prepare_vals_for_multiple_fulfillment(sale_order,
                                                                                                   tracking_numbers,
                                                                                                   picking,
                                                                                                   carrier_name,
                                                                                                   line_items)
                if not shopify_location_id:
                    continue
            else:
                shopify_location_id = self.search_shopify_location_for_update_order_status(sale_order, instance,
                                                                                           line_items,
                                                                                           picking)

                if not shopify_location_id:
                    continue

                fulfillment_vals = self.prepare_vals_for_fulfillment(sale_order, shopify_location_id, tracking_numbers,
                                                                     picking, carrier_name, line_items, notify_customer)

            is_create_mismatch, fulfillment_result, new_fulfillment = self.post_fulfilment_in_shopify(fulfillment_vals,
                                                                                                      sale_order,
                                                                                                      instance)
            if is_create_mismatch:
                continue

            self.process_shopify_fulfilment_result(instance, fulfillment_result, order_response, picking, sale_order,
                                                   new_fulfillment)

            sale_order.shopify_location_id = shopify_location_id

        if log_lines and instance.is_shopify_create_schedule:
            message = []
            count = 0
            for log_line in log_lines:
                count += 1
                if count <= 5:
                    message.append('<' + 'li' + '>' + log_line.message + '<' + '/' + 'li' + '>')
            if count >= 5:
                message.append(
                    '<' + 'p' + '>' + 'Please refer the logline' + '  ' + log_line.name + '  '
                    + 'check it in more detail' + '<' + '/' + 'p' + '>')
            note = "\n".join(message)
            self.create_schedule_activity_against_loglines(log_lines, note)

        self.closed_at(instance)
        return True

    def prepare_vals_for_multiple_fulfillment(self, sale_order, tracking_numbers, picking, carrier_name, line_items):
        """
        This method is used to prepare a vals for the multiple fulfillment.
        @return: fulfillment_vals
        @author: Yagnik Joshi @Emipro Technologies Pvt. Ltd on date 15 December 2023 .
        """
        log_lines = []
        tracking_info = {}
        new_fulfillment_vals = []
        shopify_location_id = False
        shopify_location_obj = self.env["shopify.location.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]

        if carrier_name:
            tracking_info.update({"company": carrier_name})

        if tracking_numbers:
            tracking_info.update({"number": ','.join(set(tracking_numbers)), "url": picking.carrier_tracking_url or ''})

        for pick in picking:
            location_ids_mapping = {}
            for move in pick.move_ids:
                shopify_location_id = shopify_location_obj.search(
                    [('warehouse_for_order', '=', move.warehouse_id.id),
                     ("instance_id", "=", picking.shopify_instance_id.id)], limit=1)
                if shopify_location_id:
                    location_ids_mapping.setdefault(move.shopify_fulfillment_order_id,
                                                    shopify_location_id.shopify_location_id)
                else:
                    message = "The Shopify location could not be found due to the warehouse: %s not configured into the Warehouse in Order, please configure the Warehouse in Order in the Shopify location in order to solve the issue." % (
                        move.warehouse_id.name)
                    _logger.info(message)
                    log_lines.append(
                        common_log_line_obj.create_common_log_line_ept(
                            shopify_instance_id=picking.shopify_instance_id.id,
                            module="shopify_ept", message=message,
                            model_name=self._name,
                            order_ref=sale_order.client_order_ref))
                    return False, False
            for order_id, location_id in location_ids_mapping.items():
                fulfillment_vals = {
                    "notify_customer": False,
                    "location_id": location_id,
                    "line_items_by_fulfillment_order": []
                }
                sale_line_ids = []
                for move in pick.move_ids:
                    if move.sale_line_id.id in sale_line_ids:
                        continue
                    if order_id and move.shopify_fulfillment_order_id == order_id:
                        sale_line_ids.append(move.sale_line_id.id)
                        fulfillment_order_entry = {
                            "fulfillment_order_id": move.shopify_fulfillment_order_id,
                            "fulfillment_order_line_items": [{
                                "id": move.shopify_fulfillment_line_id,
                                "quantity": int(move.product_qty)
                            }]
                        }
                        fulfillment_vals["line_items_by_fulfillment_order"].append(fulfillment_order_entry)
                if tracking_info:
                    fulfillment_vals.update({"tracking_info": tracking_info})
                new_fulfillment_vals.append(fulfillment_vals)
        return shopify_location_id, new_fulfillment_vals

    def shopify_search_picking_for_update_order_status(self, instance):
        """ This method is used to search picking for the update order status.
            @return: picking_ids(Records of picking)
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20 October 2020 .
            Task_id: 167537
            Migration done by Haresh Mori on October 2021
        """
        location_obj = self.env["stock.location"]
        stock_picking_obj = self.env["stock.picking"]
        customer_locations = location_obj.search([("usage", "=", "customer")])
        picking_ids = stock_picking_obj.search([("shopify_instance_id", "=", instance.id),
                                                ("updated_in_shopify", "=", False),
                                                ("state", "=", "done"),
                                                ("location_dest_id", "in", customer_locations.ids),
                                                ('is_cancelled_in_shopify', '=', False)],
                                               order="date")
        return picking_ids

    def request_for_shopify_order(self, sale_order):
        """ This method is used to request for sale order in the shopify store and if order response has
            fufillment_status is fulfilled then continue the update order status for that picking.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20 October 2020 .
            Task_id: 167537
            Migration done by Haresh Mori on October 2021
        """
        try:
            order = shopify.Order.find(sale_order.shopify_order_id)
            order_data = order.to_dict()
            if order_data.get('fulfillment_status') == 'fulfilled':
                shopify_location_id = self.env["shopify.location.ept"].search(
                    [("warehouse_for_order", "=", sale_order.warehouse_id.id),
                     ("instance_id", "=", sale_order.shopify_instance_id.id)], limit=1)
                sale_order.shopify_location_id = shopify_location_id
                _logger.info('Order %s is already fulfilled', sale_order.name)
                sale_order.picking_ids.filtered(lambda l: l.state == 'done').write({'updated_in_shopify': True})
                return True, order_data
            if order_data.get('cancelled_at') and order_data.get('cancel_reason'):
                _logger.info('Order %s is Cancelled', sale_order.name)
                sale_order.picking_ids.filtered(lambda l: l.state == 'done').write({'is_cancelled_in_shopify': True})
                return True, order_data
            return False, order_data
        except Exception as Error:
            _logger.info("Error in Request of shopify order for the fulfilment. Error: %s", Error)
            return True, {}

    def search_shopify_location_for_update_order_status(self, sale_order, instance, line_items, picking):
        """ This method is used to search the shopify location for the update order status from Odoo to shopify store.
            @return: shopify_location_id
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20 October 2020 .
            Task_id:167537
            Migration done by Haresh Mori on October 2021
        """
        shopify_location_obj = self.env["shopify.location.ept"]
        if instance.is_delivery_multi_warehouse:
            line_item_ids = [str(line.get('id')) for line in line_items]
            order_line = picking.move_ids.filtered(
                lambda line: line.shopify_fulfillment_line_id in line_item_ids).sale_line_id
            if order_line.warehouse_id_ept:
                shopify_location_id = shopify_location_obj.search(
                    [('warehouse_for_order', '=', order_line.warehouse_id_ept.id), ("instance_id", "=", instance.id)],
                    limit=1)
                if not shopify_location_id:
                    message = "The Shopify location could not be found due to the warehouse: %s not configured into the Warehouse in Order, please configure the Warehouse in Order in the Shopify location in order to solve the issue." % (
                        order_line.warehouse_id_ept.name)
                    _logger.info(message)
                    self.env["common.log.lines.ept"].create_common_log_line_ept(shopify_instance_id=instance.id,
                                                                                module="shopify_ept",
                                                                                message=message,
                                                                                model_name=self._name,
                                                                                order_ref=sale_order.client_order_ref)
                    return False
            else:
                shopify_location_id = shopify_location_obj.search(
                    [('warehouse_for_order', '=', order_line.warehouse_id_ept.id), ("instance_id", "=", instance.id),
                     ("is_primary_location", "=", True)], limit=1)
            return shopify_location_id
        shopify_location_id = sale_order.shopify_location_id or False
        if not shopify_location_id:
            shopify_location_id = shopify_location_obj.search(
                [("warehouse_for_order", "=", sale_order.warehouse_id.id), ("instance_id", "=", instance.id),
                 ("is_primary_location", "=", True)])
            if not shopify_location_id:
                shopify_location_id = shopify_location_obj.search([("is_primary_location", "=", True),
                                                                   ("instance_id", "=", instance.id)])
            if not shopify_location_id:
                message = "Primary Location not found for instance %s while update order " \
                          "shipping status." % (
                              instance.name)
                _logger.info(message)
                self.env["common.log.lines.ept"].create_common_log_line_ept(shopify_instance_id=instance.id,
                                                                            module="shopify_ept",
                                                                            message=message,
                                                                            model_name=self._name,
                                                                            order_ref=sale_order.client_order_ref)
                return False

        return shopify_location_id

    def prepare_vals_for_fulfillment(self, sale_order, shopify_location_id, tracking_numbers, picking, carrier_name,
                                     line_items, notify_customer):
        """ This method is used to prepare a vals for the fulfillment.
            @return: fulfillment_vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20 October 2020 .
            Task_id: 167537
            Migration done by Haresh Mori on October 2021
        """
        tracking_info = {}
        new_fulfillment_vals = []
        if carrier_name:
            tracking_info.update({"company": carrier_name})
        if tracking_numbers:
            tracking_info.update({"number": ','.join(set(tracking_numbers)), "url": picking.carrier_tracking_url or ''})
        fulfillment_vals = {
            "location_id": int(shopify_location_id.shopify_location_id),
            "notify_customer": notify_customer,
            "line_items_by_fulfillment_order": [
                {
                    "fulfillment_order_id": picking.move_ids[0].shopify_fulfillment_order_id,
                    "fulfillment_order_line_items": line_items
                }]
        }
        if tracking_info:
            fulfillment_vals.update({"tracking_info": tracking_info})
        new_fulfillment_vals.append(fulfillment_vals)

        # get service type product fulfillment data
        service_product_sale_line_ids = sale_order.order_line.filtered(
            lambda x: x.shopify_fulfillment_line_id and x.product_id.type == 'service'
                      and not x.is_delivery and x.shopify_fulfillment_order_status != 'closed')
        if service_product_sale_line_ids:
            service_fulfillment_data = self.prepare_vals_for_service_type_product_fulfillment(
                service_product_sale_line_ids,
                shopify_location_id,
                notify_customer)
            new_fulfillment_vals.extend(service_fulfillment_data)
        return new_fulfillment_vals

    def prepare_vals_for_service_type_product_fulfillment(self, service_product_sale_line_ids, shopify_location_id,
                                                          notify_customer):
        service_line_items = []
        for service_product_data in service_product_sale_line_ids:
            service_fulfillment_vals = {
                "location_id": int(shopify_location_id.shopify_location_id),
                "notify_customer": notify_customer,
                "line_items_by_fulfillment_order": [
                    {
                        "fulfillment_order_id": service_product_data.shopify_fulfillment_order_id,
                        "fulfillment_order_line_items": [{"id": service_product_data.shopify_fulfillment_line_id,
                                                          "quantity": int(service_product_data.product_qty)}]
                    }
                ]
            }
            service_line_items.append(service_fulfillment_vals)
        return service_line_items

    def post_fulfilment_in_shopify(self, fulfillment_vals, sale_order, instance):
        """ This method is used to post the fulfillment from Odoo to Shopify store.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 10 November 2020 .
            Task_id: 167930 - Update order status changes as per v13
            Migration done by Haresh Mori on October 2021
        """
        new_fulfillment = False
        fulfillment_result = False
        for new_fulfillment_vals in fulfillment_vals:
            try:
                new_fulfillment = shopify.fulfillment.FulfillmentV2(new_fulfillment_vals)
                fulfillment_result = new_fulfillment.save()
                if not fulfillment_result:
                    return False, fulfillment_result, new_fulfillment
            except ClientError as error:
                if hasattr(error,
                           "response") and error.response.code == 429 and error.response.msg == "Too Many Requests":
                    time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                    fulfillment_result = new_fulfillment.save()
            except Exception as error:
                message = "%s" % str(error)
                _logger.info(message)
                self.env["common.log.lines.ept"].create_common_log_line_ept(shopify_instance_id=instance.id,
                                                                            module="shopify_ept",
                                                                            message=message,
                                                                            model_name=self._name,
                                                                            order_ref=sale_order.client_order_ref)
                return True, fulfillment_result, new_fulfillment

        return False, fulfillment_result, new_fulfillment

    def process_shopify_fulfilment_result(self, instance, fulfillment_result, order_response, picking, sale_order,
                                          new_fulfillment):
        """ This method is used to process fulfillment result.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 10 November 2020 .
            Task_id:167930 - Update order status changes as per v13
            Migration done by Haresh Mori on October 2021
        """
        if not fulfillment_result:
            if order_response.get('fulfillment_status') == 'partial':
                if not new_fulfillment.errors:
                    picking.write({'updated_in_shopify': True})
            else:
                picking.write({'is_manually_action_shopify_fulfillment': True})
            sale_order.write({'is_service_tracking_updated': False})
            message = "Order(%s) status not updated due to %s:" % (sale_order.name, new_fulfillment.errors.errors)
            _logger.info(message)
            self.env["common.log.lines.ept"].create_common_log_line_ept(shopify_instance_id=instance.id,
                                                                        module="shopify_ept",
                                                                        message=message,
                                                                        model_name=self._name,
                                                                        order_ref=sale_order.client_order_ref)
            return False

        fulfillment_id = ''
        if new_fulfillment:
            # shopify_fullment_result = xml_to_dict(new_fulfillment.to_xml())
            shopify_fulfillment_result = json.loads(new_fulfillment.to_json())
            if shopify_fulfillment_result:
                fulfillment_id = shopify_fulfillment_result.get('fulfillment').get('id') or ''
            for line_item in shopify_fulfillment_result.get('fulfillment')['line_items']:
                service_order_line = sale_order.order_line.filtered(
                    lambda x: x.shopify_line_id == str(line_item.get('id')) and x.product_id.type == 'service'
                              and not x.is_delivery and x.shopify_fulfillment_order_status != 'closed')
                if service_order_line:
                    service_order_line.write({'shopify_fulfillment_order_status': 'closed'})

        picking.write({'updated_in_shopify': True, 'shopify_fulfillment_id': fulfillment_id})

        return True

    @api.model
    def process_shopify_order_via_webhook(self, order_data, instance, update_order=False):
        """
        Creates order data queue and process it.
        This method is for order imported via create and update webhook.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 10-Jan-2020..
        @param order_data: Dictionary of order's data.
        @param instance: Instance of Shopify.
        @param update_order: If update order webhook id called.
        """
        order_queue_obj = self.env["shopify.order.data.queue.ept"]
        order_queue_line_obj = self.env["shopify.order.data.queue.line.ept"]
        queue_type = 'unshipped'
        if order_data.get('fulfillment_status') == 'fulfilled':
            queue_type = 'shipped'
        queue = order_queue_line_obj.create_order_data_queue_line([order_data],
                                                                  instance,
                                                                  queue_type,
                                                                  created_by='webhook')
        if not update_order:
            order_queue_obj.browse(queue).order_data_queue_line_ids.process_import_order_queue_data()
        self._cr.commit()
        return True

    @api.model
    def update_shopify_order(self, queue_lines, created_by, instance):
        """
        This method will update order as per its status got from Shopify.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 13-Jan-2020..
        @param queue_lines: Order Data Queue Line.
        @param created_by: Queue line Created by.
        @return: Updated Sale order.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        orders = self
        for queue_line in queue_lines:
            message = ""
            shopify_instance = queue_line.shopify_instance_id
            order_data = json.loads(queue_line.order_data)
            shopify_status = order_data.get("financial_status")
            shopify_tags = order_data.get("tags", '')
            order = self.search_existing_shopify_order(order_data, shopify_instance, order_data.get("order_number"))

            if not order:
                self.import_shopify_orders(queue_line, shopify_instance)
                return True
            try:
                queue_line.state = "draft" if queue_line.state == "failed" else queue_line.state
                # Below condition use for, In shopify store there is full refund.
                if order_data.get('cancel_reason'):
                    cancelled = order.cancel_shopify_order()
                    if not cancelled:
                        picking_ids = order.picking_ids.filtered(lambda p: p.state == 'done')
                        message = "System can not cancel the order {0} as one of the Delivery Order " \
                                  "related to it is in the 'Done' status.".format(order.name)
                        common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, message=message,
                                                                       module="shopify_ept",
                                                                       model_name='sale.order',
                                                                       order_ref=order_data.get('name'),
                                                                       shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
                        queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
                    else:
                        queue_line.state = "done"

                if shopify_status == 'paid':
                    self.webhook_paid_workflow_process_ept(order, instance, queue_line, order_data,
                                                           shopify_status)

                if shopify_status in ["refunded", "partially_refunded"] and order_data.get(
                        "refunds") and instance.refund_order_webhook:
                    self.process_order_refund_data_ept(shopify_status, order_data, order, created_by, instance,
                                                       queue_line)
                    if instance.return_picking_order:
                        self.process_picking_return(shopify_status, order_data, order, created_by, instance,
                                                    queue_line)
                # Below condition use for, In shopify store there is fulfilled order.
                if order_data.get('fulfillment_status') in (
                        'fulfilled', 'partial') and instance.ship_order_webhook and order_data.get('fulfillments'):
                    self.process_order_fulfillment_ept(order, shopify_instance, order_data, queue_line)

                if instance.customer_order_webhook:
                    order.shopify_change_customer_in_order_webhook(instance, queue_line, order_data)

                if instance.add_new_product_order_webhook and order_data.get('fulfillment_status') != 'fulfilled':
                    order.add_new_product_in_order_webhook_ept(instance, queue_line, order_data)

                if instance.update_qty_order_webhook and order_data.get('fulfillment_status') not in ['fulfilled',
                                                                                                      'partial']:
                    order.update_qty_in_order_webhook_ept(instance, queue_line, order_data)

                if shopify_tags:
                    self.update_tag_in_shopify_order(order, shopify_tags)

                if queue_line.state == 'draft':
                    queue_line.write({'state': 'done', 'processed_at': datetime.now()})
            except Exception as error:
                message = "Receive error while process webhook flow, Error is:  (%s)" % (error)
                _logger.info(message)
                common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, message=message,
                                                               module="shopify_ept",
                                                               model_name='sale.order',
                                                               order_ref=order_data.get('name'),
                                                               shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
                queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
        return orders

    def update_tag_in_shopify_order(self, order, shopify_tags):
        """
        This method is used to update Tags in the order.
        """
        tags = shopify_tags.split(",") if shopify_tags != '' else shopify_tags
        tag_ids = []
        for tag in tags:
            tag_ids.append(self.create_or_search_sale_tag(tag))
        order.write({"tag_ids": tag_ids})

    def update_qty_in_order_webhook_ept(self, instance, queue_line, order_data):
        """
        This method is use to update qty in the order.
        """
        sale_line_obj = self.env['sale.order.line']
        common_log_line_obj = self.env["common.log.lines.ept"]
        response_data, shopify_line_ids = self.prepare_response_data_of_order_qty(order_data)
        existing_order_qty_data = self.prepare_existing_order_data_of_qty(response_data)
        data = []
        is_updated_qty = False
        for shopify_line_id in shopify_line_ids:
            r_qty = response_data.get(shopify_line_id)
            e_o_qty = existing_order_qty_data.get(shopify_line_id) or 0.0
            if not e_o_qty and r_qty == e_o_qty:
                # queue_line.write({'state': 'done', 'processed_at': datetime.now()})
                continue
            effective_qty = r_qty - e_o_qty
            if effective_qty == 0:
                # queue_line.write({'state': 'done', 'processed_at': datetime.now()})
                continue
            order_line = sale_line_obj.search([('order_id', '=', self.id), ('shopify_line_id', '=', shopify_line_id)],
                                              limit=1)
            if effective_qty < 0:
                n_update_qty = -1 * r_qty
                if n_update_qty < 0:
                    n_update_qty = n_update_qty * -1
                delivered_qty = order_line.qty_delivered
                if n_update_qty < delivered_qty:
                    message = "The user manually adjusted the quantity in Shopify. However, it is not possible to automatically adjust the quantity in Odoo because the product %s has already been delivered in order  %s.\n \
        You can take the following actions manually:\n 1. Reserve Order: If the order has not been shipped to the customer from your warehouse yet, you can reserve the order line with same quantity.\n 3. Create Credit Note: If an invoice has already been created, you can generate a credit note accordingly for that quantity." % (
                        order_line.product_id.default_code, self.name)
                    common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, message=message,
                                                                   module="shopify_ept",
                                                                   model_name='sale.order',
                                                                   order_ref=order_data.get('name'),
                                                                   shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
                    queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
                    continue
                data.append([1, order_line.id, {'product_uom_qty': n_update_qty}])
                is_updated_qty = True
            elif effective_qty > 0:
                total_qty = effective_qty + e_o_qty
                data.append([1, order_line.id, {'product_uom_qty': total_qty}])
                is_updated_qty = True
        work_flow_process_record = self.auto_workflow_process_id
        if is_updated_qty and work_flow_process_record:
            # queue_line.write({'state': 'done', 'processed_at': datetime.now()})
            order_lines = self.mapped('order_line').filtered(lambda l: l.product_id.invoice_policy == 'order')
            self.write({'order_line': data})
            if not order_lines.filtered(lambda l: l.product_id.type == 'product') and len(
                    self.order_line) != len(
                order_lines.filtered(lambda l: l.product_id.type in ['service', 'consu'])):
                return True
            if instance.update_qty_to_invoice_order_webhook:
                self.webhook_call_auto_invoice_workflow(work_flow_process_record)

    def prepare_response_data_of_order_qty(self, order_data):
        """
        This method is use to prepare quantity data as received into the response.
        """
        response_data = {}
        shopify_line_ids = []
        for line in order_data.get('line_items'):
            line_id = line.get('id')
            if order_data.get('fulfillment_status') not in ['fulfilled', 'partial']:
                qty = int(line.get('quantity'))
            else:
                qty = int(line.get('fulfillable_quantity'))
            if response_data.get(line_id):
                qty = qty + response_data.get(line_id)
                response_data.update({line_id: qty})
            else:
                response_data.update({line_id: qty})
            shopify_line_ids.append(line_id)
        return response_data, shopify_line_ids

    def prepare_existing_order_data_of_qty(self, response_data):
        """
        This method is use to prepare data of existing order.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 13 October 2023 .
        """
        data = {}
        for line in self.order_line.filtered(lambda ol: ol.shopify_line_id):
            line_id = int(line.shopify_line_id)
            qty = line.product_uom_qty
            if line.qty_delivered > 0:
                remaining = qty - line.qty_delivered
                qty = remaining + line.qty_delivered
            if data.get(line_id):
                qty = qty + data.get(line_id)
                data.update({line_id: qty})
            else:
                data.update({line_id: qty})
        return data

    def webhook_call_auto_invoice_workflow(self, work_flow_process_record):
        """
        This method is use to call the auto invoice workflow process.
        """
        if work_flow_process_record.create_invoice:
            if work_flow_process_record.invoice_date_is_order_date:
                if self.check_fiscal_year_lock_date_ept():
                    return True
            if work_flow_process_record.sale_journal_id:
                invoices = self.with_context(journal_ept=work_flow_process_record.sale_journal_id)._create_invoices(
                    final=True)
            else:
                invoices = self._create_invoices(final=True)
            self.validate_invoice_ept(invoices)
            if work_flow_process_record.register_payment:
                self.paid_invoice_ept(invoices)

    def add_new_product_in_order_webhook_ept(self, instance, queue_line, order_response):
        """
        This method is use to add new product in the order.
        """
        new_line_data = self.prepare_data_for_not_exist_product_in_order(order_response)
        if new_line_data:
            order_number = order_response.get("order_number")
            if self.check_mismatch_details(new_line_data, instance, order_number, queue_line):
                _logger.info("Mismatch details found in this Shopify Order(%s) and id (%s)", order_number,
                             order_response.get("id"))
                queue_line.write({"state": "failed", "processed_at": datetime.now()})
            else:
                _logger.info("Creating order lines for Odoo order(%s) and Shopify order is (%s).", self.name,
                             order_number)
                self.webhook_create_shopify_order_lines(new_line_data, order_response, instance)
                work_flow_process_record = self.auto_workflow_process_id
                if work_flow_process_record:
                    order_lines = self.mapped('order_line').filtered(lambda l: l.product_id.invoice_policy == 'order')
                    if not order_lines.filtered(lambda l: l.product_id.type == 'product') and len(
                            self.order_line) != len(
                        order_lines.filtered(lambda l: l.product_id.type in ['service', 'consu'])):
                        return True
                    self.webhook_call_auto_invoice_workflow(work_flow_process_record)

    def webhook_create_shopify_order_lines(self, lines, order_response, instance):
        total_discount = order_response.get("total_discounts", 0.0)
        order_number = order_response.get("order_number")
        for line in lines:
            is_custom_line, is_gift_card_line, product = self.search_custom_tip_gift_card_product(line, instance)
            price = line.get("price")
            if instance.order_visible_currency:
                price = self.get_price_based_on_customer_visible_currency(line.get("price_set"), order_response, price)
            order_line = self.shopify_create_sale_order_line(line, product, line.get("quantity"),
                                                             product.name, price,
                                                             order_response)
            if is_gift_card_line:
                line_vals = {'is_gift_card_line': True}
                if line.get('name'):
                    line_vals.update({'name': line.get('name')})
                order_line.write(line_vals)

            if is_custom_line:
                order_line.write({'name': line.get('name')})

            if line.get('duties'):
                self.create_shopify_duties_lines(line.get('duties'), order_response, instance)

            if float(total_discount) > 0.0:
                discount_amount = 0.0
                for discount_allocation in line.get("discount_allocations"):
                    if instance.order_visible_currency:
                        discount_total_price = self.get_price_based_on_customer_visible_currency(
                            discount_allocation.get("amount_set"), order_response, discount_amount)
                        if discount_total_price:
                            discount_amount += float(discount_total_price)
                    else:
                        discount_amount += float(discount_allocation.get("amount"))

                if discount_amount > 0.0:
                    _logger.info("Creating discount line for Odoo order(%s) and Shopify order is (%s)", self.name,
                                 order_number)
                    self.shopify_create_sale_order_line({}, instance.discount_product_id, 1,
                                                        product.name, float(discount_amount) * -1,
                                                        order_response, previous_line=order_line,
                                                        is_discount=True)
                    _logger.info("Created discount line for Odoo order(%s) and Shopify order is (%s)", self.name,
                                 order_number)

    def prepare_data_for_not_exist_product_in_order(self, order_data):
        """
        This method is use to prepare not exsit data into the order.
        """
        new_line_data = []
        for response_line in order_data.get('line_items'):
            sl_id = response_line.get('id')
            if self.order_line.filtered(lambda ol: ol.shopify_line_id == str(sl_id)):
                continue
            new_line_data.append(response_line)
        return new_line_data

    def shopify_change_customer_in_order_webhook(self, instance, queue_line, order_data):
        """
        This method is use to update the customer in the order based on the condition it will update.
        """
        common_log_line_obj = self.env["common.log.lines.ept"]
        need_update_shipping_partner = False
        need_update_invoice_partner = False
        need_update_partner = False
        message = ""
        if self.state != 'draft' and self.invoice_ids:
            message = "The user manually updated customer details in Shopify, but the system did not update them because an invoice has already been posted in the system.\n The system will update customer details only under the following conditions:\n 1.The invoice has not been posted.\n 2.The delivery order has not been validated.\n You can take following actions Manually\n 1. Reset to Draft Invoice & Modify Invoice address"
        elif self.state != 'draft' and not self.invoice_ids and self.picking_ids.filtered(
                lambda x: x.location_dest_id.usage == "customer" and x.state == "done"):
            message = "The user manually updated customer details in Shopify, but the system did not update them because an delivery order already done the system.\n The system will update customer details only under the following conditions:\n 1.The invoice has not been posted.\n 2.The delivery order has not been validated.\n You can take the following actions manually:\n 1.Manually Reserve Transfer: If the order has not actually been shipped to the customer, you can reserve the transfer manually.\n 2.Reset Sales Order to Draft: You have the option to reset the sales order to draft status. After doing so, you can modify the shipping address and then confirm the order again."
        pos_order = order_data.get("source_name", "") == "pos"
        partner, delivery_address, invoice_address = self.prepare_shopify_customer_and_addresses(
            order_data, pos_order, instance, queue_line)
        if not partner:
            return False
        if self.partner_id.id != partner.id:
            need_update_partner = True
        if self.partner_invoice_id.id != invoice_address.id:
            need_update_invoice_partner = True
        if self.partner_shipping_id.id != delivery_address.id:
            need_update_shipping_partner = True
        if message and need_update_partner:
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, message=message,
                                                           module="shopify_ept",
                                                           model_name='sale.order',
                                                           order_ref=order_data.get('name'),
                                                           shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
            queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
        elif message and need_update_invoice_partner:
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, message=message,
                                                           module="shopify_ept",
                                                           model_name='sale.order',
                                                           order_ref=order_data.get('name'),
                                                           shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
            queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
        elif message and need_update_shipping_partner:
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, message=message,
                                                           module="shopify_ept",
                                                           model_name='sale.order',
                                                           order_ref=order_data.get('name'),
                                                           shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
            queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
        else:
            if need_update_partner:
                self.write({'partner_id': partner.id})
                note = "<p>Customer has updated via webhook</p>"
                self.message_post(body=note)
            if need_update_invoice_partner:
                self.write({'partner_invoice_id': invoice_address.id})
                note = "<p>Invoice Address has updated via webhook</p>"
                self.message_post(body=note)
            if need_update_shipping_partner:
                self.write({'partner_shipping_id': delivery_address.id})
                transfers = self.picking_ids.filtered(
                    lambda x: x.location_dest_id.usage == "customer" and x.state != ("done", "cancel"))
                transfers.write({'partner_id': delivery_address.id})
                note = "<p>Delivery Address has updated via webhook</p>"
                self.message_post(body=note)
            # queue_line.state = "done"

    def webhook_paid_workflow_process_ept(self, order, instance, queue_line, order_data, shopify_status):
        invoices = order.invoice_ids

        gateway = "no_payment_gateway"
        payment_gateway_names = order_data.get('payment_gateway_names')
        if payment_gateway_names and payment_gateway_names[0]:
            if len(payment_gateway_names) == 1:
                gateway = payment_gateway_names[0]
            # elif 'gift_card' in payment_gateway_names:
            #     gateway = [val for val in payment_gateway_names if val != 'gift_card'][0]
            else:
                if order_data.get('transaction'):
                    for transaction in order_data.get('transaction'):
                        if "Cash on Delivery" in transaction.get("gateway"):
                            gateway = transaction.get("gateway")
                        elif transaction.get('gateway') != 'gift_card' and transaction.get("status") == 'success':
                            gateway = transaction.get("gateway")

        payment_gateway, workflow, payment_term = self.env[
            "shopify.payment.gateway.ept"].shopify_search_create_gateway_workflow(instance, queue_line,
                                                                                  order_data,
                                                                                  gateway)
        if workflow:
            order.auto_workflow_process_id = workflow
            if order.state not in ["sale", "done", "cancel"] and workflow.validate_order:
                order.action_confirm()
            if order.invoice_status in ['no', 'to invoice']:
                order_lines = order.mapped('order_line').filtered(lambda l: l.product_id.invoice_policy == 'order')
                if not order_lines.filtered(lambda l: l.product_id.type == 'product') and len(
                        order.order_line) != len(
                    order_lines.filtered(lambda l: l.product_id.type in ['service', 'consu'])):
                    queue_line.state = "done"
                else:
                    order.with_context(shopify_order_financial_status=shopify_status).validate_and_paid_invoices_ept(
                        workflow)
            elif order.invoice_status == 'invoiced' and workflow.register_payment:
                order.paid_invoice_ept(invoices)

    def process_order_fulfillment_ept(self, order, shopify_instance, order_data, queue_line):
        message = ''
        fulfilled = False
        common_log_line_obj = self.env["common.log.lines.ept"]
        if order_data.get('fulfillment_status') == 'fulfilled':
            fulfilled = order.fulfilled_shopify_order(order_data)
        if order_data.get('fulfillment_status') == 'partial':
            fulfilled = order.partial_fulfilled_shopify_order(order_data, shopify_instance)
        if not fulfilled:
            message = "The order [%s] has been shipped in Shopify, but the system could not validate the delivery order due to inventory unavailability in Odoo. The automatic validation of delivery orders did not occur for the following reasons:\n 1.Inventory Unavailability: The inventory is not available in the Odoo warehouse, and the option to perform a force transfer is not enabled in the webhook configuration.\n 2.Product Traceability: The product traceability relies on lot numbers, and the inventory  is not in Odoo.\n If you have enabled the Force Transfer option for webhook configuration, and the product traceability is set to Lot/Serial while inventory is unavailable, the system will not process those delivery orders." % order_data.get(
                'name')
        if message:
            common_log_line_obj.create_common_log_line_ept(shopify_instance_id=shopify_instance.id, message=message,
                                                           module="shopify_ept",
                                                           model_name='sale.order',
                                                           order_ref=order_data.get('name'),
                                                           shopify_order_data_queue_line_id=queue_line.id if queue_line else False)
            queue_line.write({'state': 'failed', 'processed_at': datetime.now()})
        # else:
        #     queue_line.state = "done"

    def partial_fulfilled_shopify_order(self, order_data, shopify_instance):
        """
        This method is use to allow partial fulfulled.
        """
        transfer_partially = False
        delivery_carrier = self.env['delivery.carrier']
        if self.state not in ["sale", "done", "cancel"]:
            self.action_confirm()
        for fulfillment_data in order_data.get('fulfillments'):
            picking_obj = self.env['stock.picking']
            fulfillment_data_id = fulfillment_data.get('id')
            if picking_obj.search([('shopify_fulfillment_id', '=', fulfillment_data_id),
                                   ('shopify_instance_id', '=', self.shopify_instance_id.id)]):
                continue
            fulfillment_product_data = {}
            for fulfillment_data_line in fulfillment_data.get('line_items'):
                sku = fulfillment_data_line.get('sku')
                quantity = int(fulfillment_data_line.get('quantity'))
                if fulfillment_product_data.get(sku):
                    quantity = quantity + fulfillment_product_data.get(sku)
                    fulfillment_product_data.update({sku: quantity})
                else:
                    fulfillment_product_data.update({sku: quantity})
            carrier_id = delivery_carrier.search_carrier_for_webhook_fulfillment(shopify_instance, fulfillment_data)
            tracking_number = fulfillment_data.get('tracking_number')
            for transfer in self.picking_ids.filtered(
                    lambda x: x.location_dest_id.usage == "customer" and x.state not in ("done", "cancel")):
                if not shopify_instance.forcefully_reserve_stock_webhook:
                    transfer_partially = self.process_assigned_transfer_ept(transfer, fulfillment_product_data)
                    if transfer.state == "done":
                        message = "Picking is done by Webhook as Order is partial fulfilled in Shopify."
                        transfer.message_post(body=_(message))
                        vals = {'updated_in_shopify': True, 'shopify_fulfillment_id': fulfillment_data_id}
                        if carrier_id:
                            vals.update({'carrier_id': carrier_id.id, 'carrier_tracking_ref': tracking_number})
                        transfer.write(vals)
                    else:
                        return False
                else:
                    transfer_partially = self.process_assigned_transfer_ept(transfer, fulfillment_product_data)
                    if transfer.state not in ("assigned", "done") and all(
                            move.product_id.tracking == 'none' for move in transfer.move_ids):
                        need_validate_picking = False
                        for move in transfer.move_ids_without_package:
                            sku = move.product_id.default_code
                            if fulfillment_product_data.get(sku):
                                move._action_assign()
                                move._set_quantity_done(fulfillment_product_data.get(sku))
                                need_validate_picking = True
                        if need_validate_picking:
                            self.transfer_validate_ept(transfer)
                            message = "Picking is forcefully done by Webhook as Order is fulfilled in Shopify."
                    if transfer.state == "done":
                        transfer.message_post(body=_(message))
                        vals = {'updated_in_shopify': True, 'shopify_fulfillment_id': fulfillment_data_id}
                        if carrier_id:
                            vals.update({'carrier_id': carrier_id.id, 'carrier_tracking_ref': tracking_number})
                        transfer.write(vals)
                if not transfer_partially:
                    return False
        return True

    def cancel_shopify_order(self):
        """
        Cancelled the sale order when it is cancelled in Shopify Store with full refund.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 13-Jan-2020..
        """
        if "done" in self.picking_ids.mapped("state"):
            for picking_id in self.picking_ids:
                picking_id.write({'updated_in_shopify': True})
                picking_id.message_post(
                    body=_("Order %s has been canceled in the Shopify store.", self.shopify_order_number))
            return False
        self.with_context(disable_cancel_warning=True).action_cancel()
        self.canceled_in_shopify = True
        return True

    def fulfilled_shopify_order(self, order_data):
        """
        If order is not confirmed yet, confirms it first.
        Make the picking done, when order will be fulfilled in Shopify.
        This method is used for Update order webhook.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 13-Jan-2020..
        """
        if self.state not in ["sale", "done", "cancel"]:
            self.action_confirm()
        return self.fulfilled_picking_for_shopify(self.picking_ids.filtered(lambda x:
                                                                            x.location_dest_id.usage
                                                                            == "customer"), order_data)

    def fulfilled_picking_for_shopify(self, pickings, order_data=False):
        """
        It will make the pickings done.
        This method is used for Update order webhook.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 13-Jan-2020..
        """
        fulfillment_data_id = ''
        carrier_id = False
        if order_data and self.shopify_instance_id:
            delivery_carrier = self.env['delivery.carrier']
            fulfillment_data = order_data.get('fulfillments')[-1] if order_data.get('fulfillments') else {}
            carrier_id = delivery_carrier.search_carrier_for_webhook_fulfillment(self.shopify_instance_id,
                                                                                 fulfillment_data)
            tracking_number = fulfillment_data.get('tracking_number')
            fulfillment_data_id = fulfillment_data.get('id')
        for picking in pickings.filtered(lambda x: x.state not in ['cancel', 'done']):
            if not self.shopify_instance_id.forcefully_reserve_stock_webhook:
                if picking.state != "assigned":
                    if picking.move_ids.move_orig_ids:
                        completed = self.fulfilled_picking_for_shopify(picking.move_ids.move_orig_ids.picking_id)
                        if not completed:
                            return False
                    picking.action_assign()
                    # # Add by Vrajesh Dt.01/04/2020 automatically validate delivery when import POS
                    # order in shopify
                    if picking.sale_id and (
                            picking.sale_id.is_pos_order or picking.sale_id.shopify_order_status == "fulfilled"):
                        for move_id in picking.move_ids_without_package:
                            vals = self.prepare_vals_for_move_line(move_id, picking)
                            picking.move_line_ids.create(vals)
                        picking._action_done()
                        return True
                    if picking.state != "assigned":
                        return False
                self.transfer_validate_ept(picking)
                if picking.state == "done":
                    picking.message_post(body=_("Picking is done by Webhook as Order is fulfilled in Shopify."))
                    vals = {'updated_in_shopify': True, 'shopify_fulfillment_id': fulfillment_data_id}
                    if carrier_id:
                        vals.update({'carrier_id': carrier_id.id, 'carrier_tracking_ref': tracking_number})
                    picking.write(vals)
            else:
                if picking.state in ("done", "cancel"):
                    continue
                if picking.state == "assigned":
                    self.transfer_validate_ept(picking)
                    message = "Picking is done by Webhook as Order is fulfilled in Shopify."
                if picking.state not in ("assigned", "done") and all(
                        move.product_id.tracking == 'none' for move in picking.move_ids):
                    need_validate_transfer = False
                    for move in picking.move_ids_without_package:
                        move._action_assign()
                        move._set_quantity_done(move.product_uom_qty)
                        need_validate_transfer = True
                    if need_validate_transfer:
                        message = "Picking is forcefully done by Webhook as Order is fulfilled in Shopify."
                        self.transfer_validate_ept(picking)
                if picking.state == "done":
                    picking.message_post(body=_(message))
                    vals = {'updated_in_shopify': True, 'shopify_fulfillment_id': fulfillment_data_id}
                    if carrier_id:
                        vals.update({'carrier_id': carrier_id.id, 'carrier_tracking_ref': tracking_number})
                    picking.write(vals)
                else:
                    return False
        return True

    def process_assigned_transfer_ept(self, transfer, fulfillment_product_data):
        """
        This method is use to process ready transfer while receive the partial fulfillment.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 12 October 2023 .
        """
        if all(move.product_id.tracking == 'none' for move in transfer.move_ids):
            need_to_validate_picking = False
            if transfer.state == 'assigned':
                for move in transfer.move_ids_without_package:
                    sku = move.product_id.default_code
                    if fulfillment_product_data.get(sku):
                        move._set_quantity_done(fulfillment_product_data.get(sku))
                        need_to_validate_picking = True
            if need_to_validate_picking:
                self.transfer_validate_ept(transfer)
            return True
        return False

    def transfer_validate_ept(self, transfer):
        """
        This method is use to call button validate of transfer.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 12 October 2023 .
        """
        skip_sms = {"skip_sms": True}
        result = transfer.with_context(**skip_sms).button_validate()
        if isinstance(result, dict):
            dict(result.get("context")).update(skip_sms)
            context = result.get("context")  # Merging dictionaries.
            model = result.get("res_model", "")
            if model:
                record = self.env[model].with_context(context).create({})
                record.process()

    def prepare_vals_for_move_line(self, move_id, picking):
        """ This method used to prepare a vals for move line.
            @return: vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20 October 2020 .
            Task_id: 167537
        """
        vals = {
            'product_id': move_id.product_id.id,
            'product_uom_id': move_id.product_id.uom_id.id,
            'qty_done': move_id.product_uom_qty,
            'location_id': move_id.location_id.id,
            'picking_id': picking.id,
            'location_dest_id': move_id.location_dest_id.id,
        }
        return vals

    def create_shopify_partially_refund(self, refunds_data, order_name, created_by="", shopify_financial_status=""):
        """This method is used to check the required validation before create
            a partial refund and call child methods for a partial refund.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17/05/2021.
            Task Id : 173066 - Manage Partial refund in the Shopify
        """
        account_move_obj = self.env['account.move']
        message = False
        if shopify_financial_status == "refunded":
            shopify_financial_status = "Refunded"
        else:
            shopify_financial_status = "Partially Refunded"
        if not self.invoice_ids:
            message = "- Partially refund can only be generated if it's related order " \
                      "invoice is found.\n- For order [%s], system could not find the " \
                      "related order invoice. " % order_name
            return message
        invoices = self.invoice_ids.filtered(lambda x: x.move_type == "out_invoice")
        for invoice in invoices:
            if not invoice.state == "posted":
                message = "- Partially refund can only be generated if it's related order " \
                          "invoice is in 'Post' status.\n- For order [%s], system found " \
                          "related invoice but it is not in 'Post' status." % order_name
                return message
        refund_invoices = self.invoice_ids.filtered(lambda x: x.move_type == "out_refund" and x.state == "posted")
        if refund_invoices:
            total_refund_amount = 0.0
            for refund_invoice in refund_invoices:
                total_refund_amount += refund_invoice.amount_total
            if total_refund_amount == self.amount_total:
                return
        existing_refund_total_gift_card_amount = 0.0
        need_to_add_gift_card = True
        sale_gift_card_line = self.order_line.filtered(
            lambda l: l.product_id.id == self.shopify_instance_id.gift_card_product_id.id)
        for refund_data_line in refunds_data:
            if refund_data_line.get('refund_line_items') or refund_data_line.get('order_adjustments'):
                existing_refund = account_move_obj.search([("shopify_refund_id", "=", refund_data_line.get('id')),
                                                           ("shopify_instance_id", "=", self.shopify_instance_id.id)])
                if existing_refund:
                    existing_refund_gift_card_line = existing_refund.invoice_line_ids.filtered(
                        lambda l: l.product_id.id == self.shopify_instance_id.gift_card_product_id.id)
                    existing_refund_total_gift_card_amount += existing_refund_gift_card_line.price_unit if existing_refund_gift_card_line.quantity >= 1 else 0
                    continue
                if existing_refund_total_gift_card_amount == sale_gift_card_line.price_unit:
                    need_to_add_gift_card = False
                new_move, payment_id = self.with_context(check_move_validity=False,
                                                         need_to_add_gift_card=need_to_add_gift_card).create_move_and_delete_not_necessary_line(
                    refund_data_line, invoices, created_by, shopify_financial_status)
                if refund_data_line.get('order_adjustments'):
                    self.create_refund_adjustment_line(refund_data_line.get('order_adjustments'), new_move)
                # new_move.with_context(check_move_validity=False)._recompute_dynamic_lines()
                new_move.with_context(**{'check_move_validity': False})._sync_dynamic_lines({'records': new_move})
                if new_move.state == 'draft':
                    new_move.action_post()
                    if payment_id:
                        payment_id.action_post()
                        self.reconcile_payment_ept(payment_id, new_move)
                    existing_refund_gift_card_line = new_move.invoice_line_ids.filtered(
                        lambda l: l.product_id.id == self.shopify_instance_id.gift_card_product_id.id)
                    existing_refund_total_gift_card_amount += existing_refund_gift_card_line.price_unit if existing_refund_gift_card_line.quantity >= 1 else 0
        return message

    def create_move_and_delete_not_necessary_line(self, refunds_data, invoices, created_by, shopify_financial_status):
        """This method is used to create a reverse move of invoice and delete the invoice lines from the newly
            created move which product not refunded in Shopify.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19/05/2021.
            Task Id : 173066 - Manage Partial refund in the Shopify
        """
        payment_id = False
        delete_move_lines = self.env['account.move.line']
        shopify_line_ids = []
        shopify_line_ids_with_qty = {}
        for refund_line in refunds_data.get('refund_line_items'):
            shopify_line_ids.append(refund_line.get('line_item_id'))
            shopify_line_ids_with_qty.update({refund_line.get('line_item_id'): refund_line.get('quantity')})

        refund_date = self.convert_order_date(refunds_data)
        move_reversal = self.env["account.move.reversal"].with_context(
            {"active_model": "account.move", "active_ids": invoices[0].ids}, check_move_validity=False).create(
            {"refund_method": "refund",
             "reason": "Partially Refunded from shopify" if len(refunds_data) > 1 else refunds_data.get("note"),
             "journal_id": invoices[0].journal_id.id, "date": refund_date})

        move_reversal.reverse_moves()
        new_move = move_reversal.new_move_ids
        # code for create payment for credit note
        if self.shopify_instance_id.credit_note_register_payment and self.shopify_instance_id.credit_note_payment_journal:
            payment_id = self.credit_note_register_payment(new_move)
        # code for create payment for credit note
        new_move.write({'is_refund_in_shopify': True, 'shopify_refund_id': refunds_data.get('id')})
        total_qty = 0.0
        total_sale_line_qty = 0.0
        need_to_apply_discount = True
        for new_move_line in new_move.invoice_line_ids:
            sale_line_qty = new_move_line.sale_line_ids.product_uom_qty
            shopify_line_id = new_move_line.sale_line_ids.shopify_line_id
            if shopify_line_id and int(shopify_line_id) not in shopify_line_ids:
                delete_move_lines += new_move_line
                need_to_apply_discount = False
            elif new_move_line.product_id.id == self.shopify_instance_id.gift_card_product_id.id:
                if self._context.get('need_to_add_gift_card'):
                    for transaction in refunds_data.get('transactions'):
                        if transaction.get("gateway") == "gift_card" and transaction.get(
                                "kind") == "refund" and transaction.get("status") == "success":
                            new_move_line.price_unit = -float(transaction.get("amount"))
                else:
                    delete_move_lines += new_move_line
            elif need_to_apply_discount and new_move_line.product_id.id == self.shopify_instance_id.discount_product_id.id:
                new_move_line.price_unit = new_move_line.price_unit / total_sale_line_qty * total_qty
            else:
                new_move_line.quantity = shopify_line_ids_with_qty.get(int(shopify_line_id))
                new_move_line.compute_all_tax_dirty = True
                total_qty = new_move_line.quantity
                total_sale_line_qty = new_move_line.sale_line_ids.product_uom_qty
                need_to_apply_discount = True
                # self.set_price_based_on_refund(new_move_line)

        new_move.message_post(body=_("Credit note generated by %s as Order %s "
                                     "in Shopify. This credit note has been created from "
                                     "<a href=# data-oe-model=sale.order data-oe-id=%d>%s</a>") % (
                                       created_by, shopify_financial_status, self.id, self.name))
        self.message_post(body=_(
            "Credit note created <a href=# data-oe-model=account.move data-oe-id=%d>%s</a> via %s") % (
                                   new_move.id, new_move.name, created_by))

        if delete_move_lines:
            delete_move_lines.with_context(check_move_validity=False).write({'quantity': 0})
            # delete_move_lines.with_context(check_move_validity=False)._onchange_price_subtotal()
            # delete_move_lines.with_context(check_move_validity=False).unlink()
            # new_move.with_context(check_move_validity=False)._recompute_tax_lines()
        return new_move, payment_id

    def credit_note_register_payment(self, new_move):
        """
        This method is used to register payment of the credit note.
        """
        account_payment_obj = self.env['account.payment']
        instance_id = new_move.shopify_instance_id
        if instance_id.credit_note_register_payment and instance_id.credit_note_payment_journal:
            vals = self.prepare_credit_note_payment_dict(instance_id, new_move)
            vals.update({'amount': new_move.amount_total})
            payment_id = account_payment_obj.create(vals)
            return payment_id

    def prepare_credit_note_payment_dict(self, instance_id, new_move):
        """ This method use to prepare a vals dictionary for payment."""
        return {
            'journal_id': new_move.shopify_instance_id.credit_note_payment_journal.id,
            'ref': new_move.payment_reference,
            'currency_id': new_move.currency_id.id,
            'payment_type': 'outbound',
            'date': new_move.date,
            'partner_id': new_move.commercial_partner_id.id,
            'amount': new_move.amount_residual,
            'payment_method_id': self.auto_workflow_process_id.inbound_payment_method_id.id,
            'partner_type': 'customer'
        }

    def set_price_based_on_refund(self, move_line):
        """
        Calculate tax price based on quantity and set in move line amount.
        @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 01/07/2022.
        Task Id : 194381 - Shopify refund issue fix
        """
        total_adjust_amount = 0.0
        for line in move_line.sale_line_ids:
            if move_line.quantity != line.product_uom_qty:
                tax_dict = line.order_id.tax_totals
                sub_total_tax_dict = tax_dict.get('groups_by_subtotal').get('Untaxed Amount')
                total_tax_amount = 0.0
                if sub_total_tax_dict:
                    for tax in sub_total_tax_dict:
                        total_tax_amount += tax.get('tax_group_amount')
                    total_adjust_amount = total_tax_amount / line.product_uom_qty
        move_line.price_unit += total_adjust_amount
        return True

    def create_refund_adjustment_line(self, order_adjustments, move_ids):
        """This method is used to create an invoice line in a new move to manage the adjustment refund.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 19/05/2021.
            Task Id : 173066 - Manage Partial refund in the Shopify
        """
        account_move_line_obj = self.env['account.move.line']
        adjustment_product = self.env.ref('shopify_ept.shopify_refund_adjustment_product', False)
        adjustments_amount = 0.0
        for order_adjustment in order_adjustments:
            adjustments_amount += float(order_adjustment.get('amount', 0.0))
        if abs(adjustments_amount) > 0:
            move_vals = {'product_id': adjustment_product.id, 'quantity': 1, 'price_unit': -adjustments_amount,
                         'move_id': move_ids.id, 'partner_id': move_ids.partner_id.id,
                         'name': adjustment_product.display_name}
            new_move_vals = account_move_line_obj.new(move_vals)
            if self.shopify_instance_id.apply_tax_in_order == 'odoo_tax':
                new_move_vals.with_context(round=False)._compute_totals()
            # new_move_vals._onchange_product_id()
            new_vals = account_move_line_obj._convert_to_write(
                {name: new_move_vals[name] for name in new_move_vals._cache})
            new_vals.update(
                {'quantity': 1, 'price_unit': -adjustments_amount, 'tax_ids': [(6, 0, new_move_vals.tax_ids.ids)]})
            account_move_line_obj.with_context(check_move_validity=False).create(new_vals)

    def _prepare_invoice(self):
        """This method used set a shopify instance in customer invoice.
            @param : self
            @return: inv_val
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20/11/2019.
            Task Id : 157911
        """
        inv_val = super(SaleOrder, self)._prepare_invoice()
        if self.shopify_instance_id:
            inv_val.update({'shopify_instance_id': self.shopify_instance_id.id,
                            'is_shopify_multi_payment': self.is_shopify_multi_payment})
        return inv_val

    def action_open_cancel_wizard(self):
        """This method used to open a wizard to cancel order in Shopify.
            @param : self
            @return: action
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 20/11/2019.
            Task Id : 157911
        """
        view = self.env.ref('shopify_ept.view_shopify_cancel_order_wizard')
        context = dict(self._context)
        context.update({'active_model': 'sale.order', 'active_id': self.id, 'active_ids': self.ids})
        return {
            'name': _('Cancel Order In Shopify'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'shopify.cancel.refund.order.wizard',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'context': context
        }

    def process_order_fullfield_qty(self, order_response):
        """ This method is used to search order line which product qty need to create stock move.
            :param order_response: Response of shopify order.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 31 December 2020 .
            Task_id: 169381 - Gift card order import changes
        """
        module_obj = self.env['ir.module.module']
        mrp_module = module_obj.sudo().search([('name', '=', 'mrp'), ('state', '=', 'installed')])
        lines = order_response.get("line_items")
        bom_lines = []
        for line in lines:
            shopify_line_id = line.get('id')
            sale_order_line = self.order_line.filtered(lambda order_line: int(
                order_line.shopify_line_id) == shopify_line_id and order_line.product_id.detailed_type != 'service')
            if not sale_order_line:
                continue
            fulfilled_qty = float(line.get('quantity')) - float(line.get('fulfillable_quantity'))
            if mrp_module:
                bom_lines = self.check_for_bom_product(sale_order_line.product_id)
            for bom_line in bom_lines:
                self.create_stock_move_of_fullfield_qty(sale_order_line, fulfilled_qty, bom_line)
            if fulfilled_qty > 0 and not mrp_module:
                self.create_stock_move_of_fullfield_qty(sale_order_line, fulfilled_qty)
        return True

    def create_stock_move_of_fullfield_qty(self, order_line, fulfilled_qty, bom_line=False):
        """ This method is used to create stock move which product qty is fullfield.
            :param order_line: Record of sale order line
            :param fulfilled_qty: Qty of product which needs to create a stock move.
            :param bom_line: Record of bom line
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 31 December 2020 .
            Task_id: 169381 - Gift card order import changes
        """
        stock_location_obj = self.env["stock.location"]
        customer_location = stock_location_obj.search([("usage", "=", "customer")], limit=1)
        if bom_line:
            product = bom_line[0].product_id
            product_qty = bom_line[1].get('qty', 0) * fulfilled_qty
            product_uom = bom_line[0].product_uom_id
        else:
            product = order_line.product_id
            product_qty = fulfilled_qty
            product_uom = order_line.product_uom
        if product and product_qty and product_uom:
            move_vals = self.prepare_val_for_stock_move(product, product_qty, product_uom, customer_location,
                                                        order_line)
            if bom_line:
                move_vals.update({'bom_line_id': bom_line[0].id})
            stock_move = self.env['stock.move'].create(move_vals)
            stock_move._action_assign()
            stock_move._set_quantity_done(fulfilled_qty)
            if stock_move.state != "assigned" and self.is_buy_with_prime_order and not self.shopify_instance_id.Force_transfer_move_of_buy_with_prime_orders:
                return True
            stock_move._action_done()
        return True

    def create_and_done_stock_move_ept(self, order_line, customers_location, bom_line=False, vendor_location=False):
        """
        Based on the order line, it will create a stock move and done it.
        @param : order_line: Single record of sale order line.
        @param : customers_location: Browsable record of Customer location.
        @param : bom_line: If mrp is install and product has kit type then pass the bom lines of it.
        @param : vendor_location: Browsable record of vendor location.
        """
        if bom_line:
            product = bom_line[0].product_id
            product_qty = bom_line[1].get('qty', 0) * order_line.product_uom_qty
            product_uom = bom_line[0].product_uom_id
        else:
            product = order_line.product_id
            product_qty = order_line.product_uom_qty
            product_uom = order_line.product_uom

        if product and product_qty and product_uom:
            vals = self.prepare_val_for_stock_move_ept(product, product_qty, product_uom, vendor_location,
                                                       customers_location, order_line, bom_line)
            stock_move = self.env['stock.move'].create(vals)
            stock_move.sudo()._action_assign()
            stock_move.sudo()._set_quantity_done(product_qty)
            if stock_move.state != "assigned" and self.is_buy_with_prime_order and not self.shopify_instance_id.Force_transfer_move_of_buy_with_prime_orders:
                return True
            stock_move.with_context(is_connector=True)._action_done()
        return True

    def prepare_val_for_stock_move(self, product, fulfilled_qty, product_uom, customer_location, order_line):
        """ Prepare vals for the stock move.
            @return vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 31 December 2020 .
            Task_id: 169381 - Gift card order import changes
        """
        vals = {
            'name': _('Auto processed move : %s') % product.display_name,
            'company_id': self.company_id.id,
            'product_id': product.id if product else False,
            'product_uom_qty': fulfilled_qty,
            'product_uom': product_uom.id if product_uom else False,
            'location_id': self.warehouse_id.lot_stock_id.id,
            'location_dest_id': customer_location.id,
            'state': 'confirmed',
            'sale_line_id': order_line.id
        }
        return vals

    def _get_invoiceable_lines(self, final=False):
        """Inherited base method to manage tax rounding in the invoice.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 14 May 2021.
            173531 - shopify tax rounding issue
        """
        if self.shopify_instance_id:
            self.env.context = dict(self._context)
            self.env.context.update({'round': False})
        invoiceable_lines = super(SaleOrder, self)._get_invoiceable_lines(final)
        return invoiceable_lines

    def paid_invoice_ept(self, invoices):
        """
        Override the common connector library method here to create separate payment records.
        Override by Meera Sidapara on date 16/11/2021.
        """
        self.ensure_one()
        account_payment_obj = self.env['account.payment']
        if self.is_shopify_multi_payment:
            for invoice in invoices:
                if invoice.amount_residual:
                    for payment in self.shopify_payment_ids:
                        if payment.payment_gateway_id.code != 'gift_card':
                            vals = invoice.prepare_payment_dict(payment.workflow_id)
                            vals.update({'amount': payment.amount})
                            payment_id = account_payment_obj.create(vals)
                            payment_id.action_post()
                            self.reconcile_payment_ept(payment_id, invoice)
            return True
        super(SaleOrder, self).paid_invoice_ept(invoices)

    def create_schedule_activity_against_loglines(self, log_lines, note):
        """
        Author : Meera Sidapara 27/10/2021 this method use for create schedule activity based on
        log book.
        :model: model use for the model
        :return: True
        Task Id: 179264
        """
        mail_activity_obj = self.env['mail.activity']
        ir_model_obj = self.env['ir.model']
        model_id = ir_model_obj.search([('model', '=', 'common.log.lines.ept')])
        if len(log_lines) > 0:
            for log_line in log_lines:
                activity_type_id = log_line and log_line.shopify_instance_id.shopify_activity_type_id.id
                date_deadline = datetime.strftime(
                    datetime.now() + timedelta(days=int(log_line.shopify_instance_id.shopify_date_deadline)),
                    "%Y-%m-%d")
                for user_id in log_line.shopify_instance_id.shopify_user_ids:
                    mail_activity = mail_activity_obj.search([('res_model_id', '=', model_id.id),
                                                              ('user_id', '=', user_id.id),
                                                              # ('res_name', '=', log_line.name),
                                                              ('activity_type_id', '=', activity_type_id)])
                    note_2 = "<p>" + note + '</p>'
                    if not mail_activity or mail_activity.note != note_2:
                        vals = {'activity_type_id': activity_type_id, 'note': note,
                                # 'summary': log_line.name,
                                'res_id': log_line.id, 'user_id': user_id.id or self._uid,
                                'res_model_id': model_id.id, 'date_deadline': date_deadline}
                        try:
                            mail_activity_obj.create(vals)
                        except Exception as error:
                            _logger.info("Unable to create schedule activity, Please give proper "
                                         "access right of this user :%s  ", user_id.name)
                            _logger.info(error)
        return True

    def _prepare_confirmation_values(self):
        """
        Inherited this method here for the webhook process. sale order data write in the picking date deadline
        and that deadline date write in the stock move as per default flow but the confirm sale order we
        update the order date in the sale order but in picking it is default so there need to set proper date otherwise
        getting issue while merge move process. def _merge_moves(self, merge_into=False) there merge move not found due to dead line date mismatch once
        update the quantity from the order
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 16 October 2023 .
        """
        res = super(SaleOrder, self)._prepare_confirmation_values()
        if self.shopify_instance_id:
            res.update({'date_order': self.date_order})
        return res

    def action_order_ref_redirect(self):
        """
        This method is used to redirect Woocommerce order in WooCommerce Store.
        @author: Meera Sidapara on Date 31-May-2022.
        @Task: 190111 - Shopify APP features
        """
        self.ensure_one()
        url = '%s/admin/orders/%s' % (self.shopify_instance_id.shopify_host, self.shopify_order_id)
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    shopify_line_id = fields.Char("Shopify Line", copy=False)
    is_gift_card_line = fields.Boolean(copy=False, default=False)
    shopify_fulfillment_order_id = fields.Char("Fulfillment Order ID")
    shopify_fulfillment_line_id = fields.Char("Fulfillment Line ID")
    shopify_fulfillment_order_status = fields.Char("Fulfillment Order Status")

    def unlink(self):
        """
        This method is used to prevent the delete sale order line if the order has a Shopify order.
        @author: Haresh Mori on date:17/06/2020
        """
        product_product_obj = self.env['product.product']
        for record in self:
            loyality_module = product_product_obj.search_installed_module_ept('sale_loyalty')
            if loyality_module and record.is_reward_line:
                continue
            if record.order_id.shopify_order_id:
                msg = _(
                    "You can not delete this line because this line is Shopify order line and we need "
                    "Shopify line id while we are doing update order status")
                raise UserError(msg)
        return super(SaleOrderLine, self).unlink()


class ImportShopifyOrderStatus(models.Model):
    _name = "import.shopify.order.status"
    _description = 'Order Status'

    name = fields.Char()
    status = fields.Char()
