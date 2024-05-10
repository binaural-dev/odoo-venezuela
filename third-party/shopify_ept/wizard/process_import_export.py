# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.

import base64
import csv
import logging
import time
import os
from io import StringIO, BytesIO
from datetime import datetime, timedelta
import xlrd

from odoo.exceptions import UserError
from odoo.tools.misc import split_every

from odoo import models, fields, api, _
from odoo.addons.web_editor.tools import get_video_embed_code
from .. import shopify
from ..shopify.pyactiveresource.connection import ClientError

_logger = logging.getLogger("Shopify Operations")


class ShopifyProcessImportExport(models.TransientModel):
    _name = 'shopify.process.import.export'
    _description = 'Shopify Process Import Export'

    shopify_instance_id = fields.Many2one("shopify.instance.ept", string="Instance")
    shopify_operation = fields.Selection(
        [("sync_product", "Import Products"),
         ("sync_product_by_remote_ids", "Import Specific Product(s)"),
         ("import_customers", "Import Customers"),
         ("import_unshipped_orders", "Import Unshipped Orders"),
         ("import_shipped_orders", "Import Shipped Orders"),
         ("import_buy_with_prime_orders", "Import Buy with Prime Orders"),
         ("import_cancel_orders", "Import Cancel Orders"),
         ("import_orders_by_remote_ids", "Import Specific Order(s)"),
         ("update_order_status", "Export Shippment Information/Update Order Status"),
         ("import_stock", "Import Stock"),
         ("export_stock", "Export Stock"),
         ("import_location", "Import Locations"),
         ("import_products_from_csv", "Map Products"),
         ("import_payout_report", "Import Payout Report")
         ],
        default="sync_product", string="Operation")
    orders_from_date = fields.Datetime(string="From Date")
    orders_to_date = fields.Datetime(string="To Date")
    shopify_instance_ids = fields.Many2many("shopify.instance.ept", "shopify_instance_import_export_rel",
                                            "process_id", "shopify_instance_id", "Instances")
    shopify_is_set_price = fields.Boolean(string="Set Price ?",
                                          help="If is a mark, it set the price with product in the Shopify store.",
                                          default=False)
    shopify_is_set_stock = fields.Boolean(string="Set Stock ?",
                                          help="If is a mark, it set the stock with product in the Shopify store.",
                                          default=False)
    shopify_is_publish = fields.Selection(
        [('publish_product_web', 'Publish Web Only'), ('publish_product_global', 'Publish Web and POS'),
         ('unpublish_product', 'Unpublish')],
        string="Publish In Website ?",
        help="If is a mark, it publish the product in website.",
        default='publish_product_web')
    shopify_is_set_image = fields.Boolean(string="Set Image ?",
                                          help="If is a mark, it set the image with product in the Shopify store.",
                                          default=False)
    shopify_is_set_basic_detail = fields.Boolean(string="Set Basic Detail ?",
                                                 help="If is a mark, it set the product basic detail in shopify store",
                                                 default=True)
    shopify_is_update_basic_detail = fields.Boolean(string="Update Basic Detail ?", default=False,
                                                    help="If is a mark, it update the product basic detail in "
                                                         "shopify store")
    shopify_is_update_price = fields.Boolean(string="set Price ?")
    shopify_template_ids = fields.Text(string="Template Ids",
                                       help="Based on template ids get product from shopify and import in odoo")
    shopify_order_ids = fields.Text(string="Order Ids",
                                    help="Based on template ids get product from shopify and import products in odoo")
    export_stock_from = fields.Datetime(help="It is used for exporting stock from Odoo to Shopify.")
    payout_start_date = fields.Date(string="Start Date")
    payout_end_date = fields.Date(string="End Date")
    skip_existing_product = fields.Boolean(string="Do Not Update Existing Products",
                                           help="Check if you want to skip existing products.")
    csv_file = fields.Binary(help="Select CSV file to upload.")
    file_name = fields.Char(help="Name of CSV file.")
    cron_process_notification = fields.Text(string="Shopify Note: ", store=False,
                                            help="Used to display that cron will be run after some time")
    is_hide_operation_execute_button = fields.Boolean(default=False, store=False,
                                                      help="Used to hide the execute button from operation wizard "
                                                           "while selected operation cron is running in backend")
    import_products_based_on_date = fields.Selection([("create_date", "Create Date"), ("update_date", "Update Date")],
                                                     default="update_date", string="Import Based On")
    is_auto_validate_inventory = fields.Boolean(default=False, string='Auto Validate Inventory',
                                                help="If you mark it, the inventory will be applied automatically.")

    shopify_video_url = fields.Char('Video URL',
                                    help='URL of a video for showcasing by operations.')
    shopify_video_embed_code = fields.Html(compute="_compute_shopify_video_embed_code", sanitize=False)
    is_import_draft_product = fields.Boolean(default=False, string='Import Draft products',
                                             help="If you mark it, It will be import draft products")

    @api.depends('shopify_video_url')
    def _compute_shopify_video_embed_code(self):
        for image in self:
            image.shopify_video_embed_code = get_video_embed_code(image.shopify_video_url)

    def shopify_execute(self):
        """This method used to execute the operation as per given in wizard.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 25/10/2019.
        """
        product_data_queue_obj = self.env["shopify.product.data.queue.ept"]
        order_date_queue_obj = self.env["shopify.order.data.queue.ept"]
        queue_ids = False

        instance = self.shopify_instance_id
        if self.shopify_operation == "sync_product":
            product_queue_ids = product_data_queue_obj.with_context(
                queue_created_by="manual").shopify_create_product_data_queue(
                instance, self.import_products_based_on_date, self.orders_from_date, self.orders_to_date,
                self.skip_existing_product, "", self.is_import_draft_product)
            if product_queue_ids:
                queue_ids = product_queue_ids
                action_name = "shopify_ept.action_shopify_product_data_queue"
                form_view_name = "shopify_ept.product_synced_data_form_view_ept"

        elif self.shopify_operation == "sync_product_by_remote_ids":
            product_queue_ids = product_data_queue_obj.with_context(
                queue_created_by="manual").shopify_create_product_data_queue(
                instance, skip_existing_product=self.skip_existing_product, template_ids=self.shopify_template_ids)
            if product_queue_ids:
                queue_ids = product_queue_ids
                action_name = "shopify_ept.action_shopify_product_data_queue"
                form_view_name = "shopify_ept.product_synced_data_form_view_ept"

            # if product_queue_ids:
            #     queue_ids = product_queue_ids
            #     product_data_queue = product_data_queue_obj.browse(queue_ids)
            #     product_data_queue.product_data_queue_lines.process_product_queue_line_data()
            #     _logger.info("Processed product queue : %s of Instance : %s Via Product Template ids Successfully .",
            #                  product_data_queue.name, instance.name)
            #     if not product_data_queue.product_data_queue_lines:
            #         product_data_queue.unlink()
            #     action_name = "shopify_ept.action_shopify_product_data_queue"
            #     form_view_name = "shopify_ept.product_synced_data_form_view_ept"

        elif self.shopify_operation == "import_customers":
            customer_queues = self.sync_shopify_customers()
            if customer_queues:
                queue_ids = customer_queues
                action_name = "shopify_ept.action_shopify_synced_customer_data"
                form_view_name = "shopify_ept.shopify_synced_customer_data_form_view_ept"

        elif self.shopify_operation == "import_unshipped_orders":
            order_queues = order_date_queue_obj.with_context(
                queue_created_by="manual").shopify_create_order_data_queues(instance, self.orders_from_date,
                                                                            self.orders_to_date,
                                                                            order_type="unshipped")
            if order_queues:
                queue_ids = order_queues
                action_name = "shopify_ept.action_shopify_order_data_queue_ept"
                form_view_name = "shopify_ept.view_shopify_order_data_queue_ept_form"

        elif self.shopify_operation == "import_shipped_orders":
            order_queues = order_date_queue_obj.with_context(
                queue_created_by="manual").shopify_create_order_data_queues(instance,
                                                                            self.orders_from_date,
                                                                            self.orders_to_date,
                                                                            order_type="shipped")
            if order_queues:
                queue_ids = order_queues
                action_name = "shopify_ept.action_shopify_shipped_order_data_queue_ept"
                form_view_name = "shopify_ept.view_shopify_order_data_queue_ept_form"

        elif self.shopify_operation == "import_buy_with_prime_orders":
            if not instance.import_buy_with_prime_shopify_order:
                raise UserError(_('Import Buy with Prime Configuration is not Active'))
            order_queues = order_date_queue_obj.with_context(
                queue_created_by="manual").shopify_create_order_data_queues(instance,
                                                                            self.orders_from_date,
                                                                            self.orders_to_date,
                                                                            order_type="buy_with_prime")
            if order_queues:
                queue_ids = order_queues
                action_name = "shopify_ept.action_shopify_shipped_order_data_queue_ept"
                form_view_name = "shopify_ept.view_shopify_order_data_queue_ept_form"

        elif self.shopify_operation == "import_cancel_orders":
            sale_order_obj = self.env["sale.order"]
            sale_order_obj.import_shopify_cancel_order(instance, self.orders_from_date, self.orders_to_date)

        elif self.shopify_operation == "import_orders_by_remote_ids":
            order_queues = order_date_queue_obj.with_context(
                queue_created_by="manual").import_order_process_by_remote_ids(instance, self.shopify_order_ids)
            if order_queues:
                queue_ids = order_queues
                action_name = "shopify_ept.action_shopify_order_data_queue_ept"
                form_view_name = "shopify_ept.view_shopify_order_data_queue_ept_form"

        elif self.shopify_operation == "export_stock":
            # self.update_stock_in_shopify(ctx={})
            exprot_stock_queue_id = self.with_context(queue_created_by="manual").shopify_export_stock_queue(ctx={})
            if exprot_stock_queue_id:
                queue_ids = exprot_stock_queue_id.ids
                action_name = "shopify_ept.action_shopify_export_stock_queue"
                form_view_name = "shopify_ept.export_stock_form_view_ept"

        elif self.shopify_operation == "import_stock":
            self.import_stock_in_odoo()
            # inventory_records = self.import_stock_in_odoo()
            # if inventory_records:
            #     queue_ids = inventory_records
            #     action_name = "stock.action_inventory_form"
            #     form_view_name = "stock.view_inventory_form"

        elif self.shopify_operation == "update_order_status":
            self.update_order_status()

        elif self.shopify_operation == "import_payout_report":
            if self.payout_end_date and self.payout_start_date:
                if self.payout_end_date < self.payout_start_date:
                    raise UserError("The start date must be precede its end date")
                self.env["shopify.payout.report.ept"].get_payout_report(self.payout_start_date, self.payout_end_date,
                                                                        instance)

        elif self.shopify_operation == "import_products_from_csv":
            self.import_products_from_file()

        elif self.shopify_operation == "import_location":
            shopify_locations = self.import_shopify_location()
            if shopify_locations:
                queue_ids = shopify_locations
                action_name = "shopify_ept.action_shopify_location_data"
                form_view_name = "shopify_ept.shopify_synced_locations_data_form_view_ept"

        if queue_ids and isinstance(queue_ids, list) and action_name and form_view_name:
            action = self.env.ref(action_name).sudo().read()[0]
            form_view = self.sudo().env.ref(form_view_name)

            if len(queue_ids) == 1:
                action.update({"view_id": (form_view.id, form_view.name), "res_id": queue_ids[0],
                               "views": [(form_view.id, "form")]})
            else:
                action["domain"] = [("id", "in", queue_ids)]
            return action

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def manual_export_product_to_shopify(self):
        """ This method is used to call child method for export products from shopify layer products to Shopify store.
            It calls from the Shopify layer product screen.
        """
        start = time.time()
        shopify_product_template_obj = self.env["shopify.product.template.ept"]
        shopify_product_obj = self.env['shopify.product.product.ept']
        instance_obj = self.env['shopify.instance.ept']

        shopify_products = self._context.get('active_ids', [])

        template = shopify_product_template_obj.browse(shopify_products)
        templates = template.filtered(lambda x: not x.exported_in_shopify)
        if templates and len(templates) > 80:
            raise UserError(_("Error:\n- System will not export more then 80 Products at a "
                              "time.\n- Please select only 80 product for export."))
        shopify_instances = instance_obj.search([])
        for instance in shopify_instances:
            shopify_templates = templates.filtered(lambda product: product.shopify_instance_id == instance)
            if shopify_templates:
                shopify_product_obj.shopify_export_products(instance,
                                                            self.shopify_is_set_basic_detail,
                                                            self.shopify_is_set_price,
                                                            self.shopify_is_set_image,
                                                            self.shopify_is_publish,
                                                            shopify_templates)
        end = time.time()
        _logger.info("Export Processed %s Products in %s seconds.", str(len(templates)), str(end - start))
        return True

    def manual_update_product_to_shopify(self):
        """ This method is used to call child method for update products values from shopify layer products to Shopify
            store. It calls from the Shopify layer product screen.
        """
        if not self.shopify_is_update_basic_detail and not self.shopify_is_publish and not self.shopify_is_set_price \
                and not self.shopify_is_set_image:
            raise UserError("Please Select Any Option To Update Product.")

        shopify_product_template_obj = self.env['shopify.product.template.ept']
        shopify_product_obj = self.env['shopify.product.product.ept']
        instance_obj = self.env['shopify.instance.ept']

        start = time.time()
        shopify_products = self._context.get('active_ids', [])

        template = shopify_product_template_obj.browse(shopify_products)
        templates = template.filtered(lambda x: x.exported_in_shopify)
        if templates and len(templates) > 80:
            raise UserError(_("Error:\n- System will not update more then 80 Products at a "
                              "time.\n- Please select only 80 product for export."))
        shopify_instances = instance_obj.search([])
        for instance in shopify_instances:
            shopify_templates = templates.filtered(lambda product: product.shopify_instance_id == instance)
            if shopify_templates:
                shopify_product_obj.update_products_in_shopify(instance, shopify_templates,
                                                               self.shopify_is_set_price,
                                                               self.shopify_is_set_image,
                                                               self.shopify_is_publish,
                                                               self.shopify_is_update_basic_detail)
        end = time.time()
        _logger.info("Update Processed %s Products in %s seconds.", str(len(template)), str(end - start))
        return True

    def shopify_export_variant_vals(self, instance, variant, shopify_template):
        """This method used prepare a shopify template vals for export product process,
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17/10/2019.
        """
        shopify_variant_vals = {
            'shopify_instance_id': instance.id,
            'product_id': variant.id,
            'shopify_template_id': shopify_template.id,
            'default_code': variant.default_code,
            'name': variant.name,
        }
        return shopify_variant_vals

    def shopify_export_template_vals(self, instance, odoo_template):
        """This method used prepare a shopify template vals for export product process,
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 17/10/2019.
        """
        shopify_template_vals = {
            'shopify_instance_id': instance.id,
            'product_tmpl_id': odoo_template.id,
            'name': odoo_template.name,
            'description': odoo_template.description_sale,
            'shopify_product_category': odoo_template.categ_id.id,
        }
        return shopify_template_vals

    def sync_shopify_customers(self):
        """
        This method used to sync the customers data from Shopify to Odoo.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 23/10/2019.
        :Task ID: 157065
        @change: Maulik Barad on Date 09-Sep-2020.
        """
        customer_queues_ids = []

        self.shopify_instance_id.connect_in_shopify()
        if not self.shopify_instance_id.shopify_last_date_customer_import:
            customer_ids = shopify.Customer().find(limit=250)
        else:
            customer_ids = shopify.Customer().find(
                updated_at_min=self.shopify_instance_id.shopify_last_date_customer_import, limit=250)
        if customer_ids:
            customer_queues_ids = self.create_customer_data_queues(customer_ids)
            if len(customer_ids) == 250:
                customer_queues_ids += self.shopify_list_all_customer(customer_ids)

            self.shopify_instance_id.shopify_last_date_customer_import = datetime.now()
        if not customer_ids:
            _logger.info("Customers not found while the import customers from Shopify")
        return customer_queues_ids

    def create_customer_data_queues(self, customer_data):
        """
        It creates customer data queue from data of Customer.
        @author: Maulik Barad on Date 09-Sep-2020.
        @param customer_data: Data of Customer.
        """
        customer_queue_list = []
        customer_data_queue_obj = self.env["shopify.customer.data.queue.ept"]
        customer_data_queue_line_obj = self.env["shopify.customer.data.queue.line.ept"]
        bus_bus_obj = self.env["bus.bus"]

        if len(customer_data) > 0:
            for customer_id_chunk in split_every(125, customer_data):
                customer_queue = customer_data_queue_obj.create_customer_queue(self.shopify_instance_id,
                                                                               "import_process")
                customer_data_queue_line_obj.shopify_create_multi_queue(customer_queue, customer_id_chunk)

                message = "Customer Queue created %s" % ', '.join(customer_queue.mapped('name'))
                bus_bus_obj._sendone(self.env.user.partner_id, "simple_notification",
                                     {"title": "Shopify Notification", "message": message, "sticky": False,
                                      "warning": True})
                _logger.info(message)
                if not customer_queue.synced_customer_queue_line_ids:
                    customer_queue.unlink()
                else:
                    customer_queue_list.append(customer_queue.id)
            self._cr.commit()
        return customer_queue_list

    def webhook_customer_create_process(self, res, instance):
        """
        This method is used for create customer queue and queue line while the customer create form the webhook method.
        :param res: Response of customer which receive from the webhook.
        :param instance: Record of the instance.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 13/01/2020.
        """
        data_queue_obj = self.env['shopify.customer.data.queue.ept']

        customer_queue_id = data_queue_obj.search([("record_created_from", "=", "webhook"), ("state", "=", "draft"),
                                                   ("shopify_instance_id", "=", instance.id)])
        if customer_queue_id:
            message = "Customer %s added into Queue %s." % (res.get("first_name"), customer_queue_id.name)
        else:
            customer_queue_id = data_queue_obj.create_customer_queue(instance, "webhook")
            message = "Customer Queue %s created." % customer_queue_id.name
        _logger.info(message)

        customer_queue_id.synced_customer_queue_line_ids.shopify_customer_data_queue_line_create(res, customer_queue_id)
        if len(customer_queue_id.synced_customer_queue_line_ids) == 50:
            customer_queue_id.synced_customer_queue_line_ids.sync_shopify_customer_into_odoo()
        if not customer_queue_id.synced_customer_queue_line_ids:
            customer_queue_id.unlink()
        return True

    def shopify_list_all_customer(self, result):
        """
        This method used to call the page wise data import for customers from Shopify to Odoo.
        @author: Angel Patel @Emipro Technologies Pvt. Ltd on date 14/10/2019.
        :Task ID: 157065
        Modify by Haresh Mori on date 26/12/2019, Taken Changes for the pagination and API version.
        """
        catch = ""
        customer_queue_list = []
        while result:
            page_info = ""
            link = shopify.ShopifyResource.connection.response.headers.get(
                "Link") if shopify.ShopifyResource.connection.response.headers.get(
                "Link") else shopify.ShopifyResource.connection.response.headers.get("link")
            if not link or not isinstance(link, str):
                return customer_queue_list
            for page_link in link.split(','):
                if page_link.find('next') > 0:
                    page_info = page_link.split(';')[0].strip('<>').split('page_info=')[1]
                    try:
                        result = shopify.Customer().find(page_info=page_info, limit=250)
                    except ClientError as error:
                        if hasattr(error, "response"):
                            if error.response.code == 429 and error.response.msg == "Too Many Requests":
                                time.sleep(int(float(error.response.headers.get('Retry-After', 5))))
                                result = shopify.Customer().find(page_info=page_info, limit=250)
                    except Exception as error:
                        raise UserError(error)
                    if result:
                        customer_queue_list += self.create_customer_data_queues(result)
            if catch == page_info:
                break
        return customer_queue_list

    def import_cancel_order_cron_action(self, ctx=False):
        """This method is used to import cancel orders from the auto-import cron job.
        """
        sale_order_obj = self.env["sale.order"]
        if not isinstance(ctx, dict):
            return True
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        from_date = instance.last_cancel_order_import_date
        to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(3)
        sale_order_obj.import_shopify_cancel_order(instance, from_date, to_date)
        return True

    @api.model
    def update_stock_in_shopify(self, ctx=False):
        """
        This method used to export stock from odoo to shopify.
        @author: Maulik Barad on Date 15-Sep-2020.
        """
        if not isinstance(ctx, dict):
            return True
        shopify_instance_obj = self.env['shopify.instance.ept']
        product_obj = self.env['product.product']
        shopify_product_obj = self.env['shopify.product.product.ept']

        if self.shopify_instance_id:
            instance = self.shopify_instance_id
        elif ctx.get('shopify_instance_id'):
            instance_id = ctx.get('shopify_instance_id')
            instance = shopify_instance_obj.browse(instance_id)

        if not instance:
            raise UserError(_("Shopify instance not found.\nPlease select one, if you are processing from Operations"
                              " wizard.\nOtherwise please check the code of cron, if it has been modified."))
        if self.export_stock_from:
            last_update_date = self.export_stock_from
            _logger.info("Exporting Stock from Operations wizard for instance - %s", instance.name)
        else:
            last_update_date = instance.shopify_last_date_update_stock or datetime.now() - timedelta(30)
            _logger.info("Exporting Stock by Cron for instance - %s", instance.name)

        products = product_obj.get_products_based_on_movement_date_ept(last_update_date,
                                                                       instance.shopify_company_id)
        if products:
            shopify_products = shopify_product_obj.export_stock_in_shopify(instance, products)
            if shopify_products:
                instance.write({'shopify_last_date_update_stock': datetime.now() - timedelta(hours=2)})
        else:
            instance.shopify_last_date_update_stock = datetime.now() - timedelta(hours=2)
            _logger.info("No products found to export stock from %s.....", last_update_date)

        return True

    @api.model
    def shopify_export_stock_queue(self, ctx=False):
        """
        This method used to export stock from odoo to shopify.
        """
        shopify_instance_obj = self.env['shopify.instance.ept']
        product_obj = self.env['product.product']
        shopify_product_obj = self.env['shopify.product.product.ept']

        instance = self.shopify_instance_id if self.shopify_instance_id else False
        if not instance and ctx.get('shopify_instance_id'):
            instance_id = ctx.get('shopify_instance_id')
            instance = shopify_instance_obj.browse(instance_id)

        if not instance:
            raise UserError(_("Shopify instance not found.\nPlease select one, if you are processing from Operations"
                              " wizard.\nOtherwise please check the code of cron, if it has been modified."))

        if self.export_stock_from:
            last_update_date = self.export_stock_from
            _logger.info("Exporting Stock from Operations wizard for instance - %s", instance.name)
        else:
            last_update_date = instance.shopify_last_date_update_stock or datetime.now() - timedelta(30)
            _logger.info("Exporting Stock by Cron for instance - %s", instance.name)

        products = product_obj.get_products_based_on_movement_date_ept(last_update_date,
                                                                       instance.shopify_company_id)

        # find shopify product which has Fixed Stock Export boolean is true
        fixed_stock_products = self.search_product_for_fixed_stock_export(instance)
        products = products + fixed_stock_products

        if products:
            export_stock_queue = shopify_product_obj.export_stock_queue(instance, products)
            if export_stock_queue:
                return export_stock_queue
        else:
            instance.shopify_last_date_update_stock = datetime.now()
            _logger.info("No products found to export stock from %s.....", last_update_date)

        return False

    def search_product_for_fixed_stock_export(self, instance):
        """
        This method is used for find shopify product which have fix export stock boolean is true.
        @author: Yagnik Joshi @Emipro Technologies Pvt. Ltd on date 27 November 2023 .
        Task_id:3816
        """
        result = []
        shopify_variants_product_obj = self.env['shopify.product.product.ept']
        shopify_products = shopify_variants_product_obj.search([
            ('fixed_stock_export', '=', True),
            ('shopify_instance_id', '=', instance.id)
        ])

        ids = shopify_products.product_id.ids
        return list(set(ids))

    def shopify_selective_product_stock_export(self):
        """
        This method export stock of particular selected products in list view or from form view's action menu.
        @author: Maulik Barad on Date 10-Oct-2020.
        """
        shopify_product_obj = self.env['shopify.product.product.ept']
        shopify_template_ids = self._context.get('active_ids')
        export_stock_data_obj = self.env['shopify.export.stock.queue.ept']
        shopify_instances = self.env['shopify.instance.ept'].search([])
        for instance in shopify_instances:
            shopify_products = shopify_product_obj.search([('shopify_instance_id', '=', instance.id),
                                                           ('shopify_template_id', 'in', shopify_template_ids)])
            odoo_product_ids = shopify_products.product_id.ids
            if odoo_product_ids:
                # shopify_product_obj.with_context(is_process_from_selected_product=True).export_stock_in_shopify(
                #     instance, odoo_product_ids)
                export_stock_queue_id = shopify_product_obj.with_context(
                    is_process_from_selected_product=True).export_stock_queue(instance, odoo_product_ids)
                if export_stock_queue_id:
                    queue_ids = export_stock_queue_id.ids
                    export_stock_data_queue = export_stock_data_obj.browse(queue_ids)
                    export_stock_data_queue.export_stock_queue_line_ids.process_export_stock_queue_data()
                    _logger.info(
                        "Processed product queue : %s of Instance : %s Via Product Template ids Successfully .",
                        export_stock_data_queue.name, instance.name)
                    if not export_stock_data_queue.export_stock_queue_line_ids:
                        export_stock_data_queue.unlink()
                    action_name = "shopify_ept.action_shopify_export_stock_queue"
                    form_view_name = "shopify_ept.export_stock_form_view_ept"
                    if queue_ids and action_name and form_view_name:
                        action = self.env.ref(action_name).sudo().read()[0]
                        form_view = self.sudo().env.ref(form_view_name)

                        if len(queue_ids) == 1:
                            action.update({"view_id": (form_view.id, form_view.name), "res_id": queue_ids[0],
                                           "views": [(form_view.id, "form")]})
                        else:
                            action["domain"] = [("id", "in", queue_ids)]
                        return action
        return True

    def import_stock_in_odoo(self):
        """
        Import stock from shopify to odoo.
        :Task id: 157905
        """
        instance = self.shopify_instance_id
        shopify_product_obj = self.env['shopify.product.product.ept']
        # inventory_records = shopify_product_obj.import_shopify_stock(instance, self.is_auto_validate_inventory)
        # return inventory_records
        shopify_product_obj.import_shopify_stock(instance, self.is_auto_validate_inventory)

    def update_order_status(self, instance=False):
        """This method is used to call child method for update order status from Odoo to Shopify.
            @author: Angel Patel @Emipro Technologies Pvt.
            :Task ID: 157905
            Migration done by Haresh Mori on October 2021
        """
        sale_order_obj = self.env['sale.order']
        if not instance:
            instance = self.shopify_instance_id
        if instance.active:
            sale_order_obj.update_order_status_in_shopify(instance)
        else:
            _logger.info(_("Your instance '%s' is in active.", instance.name))
        return True

    def update_order_status_cron_action(self, ctx=False):
        """
        This method is while update order status cron is active.
        @author: Angel Patel @Emipro Technologies Pvt.
        :Task ID: 157716
        """
        if not isinstance(ctx, dict):
            return True
        instance_id = ctx.get('shopify_instance_id')
        instance = self.env['shopify.instance.ept'].browse(instance_id)
        _logger.info(
            _("Auto cron update order status process start with instance: '%s'"), instance.name)
        self.update_order_status(instance)
        return True

    @api.onchange("shopify_instance_id", "shopify_operation")
    def onchange_shopify_instance_id(self):
        """
        This method sets field values, when the Instance will be changed.
        Author: Bhavesh Jadav 23/12/2019
        """
        instance = self.shopify_instance_id
        self.cron_process_notification = False
        self.is_hide_operation_execute_button = False
        current_time = datetime.now()
        if instance:
            # Attach Shopify Operations Videos
            self.set_shopify_video_based_on_operation()

            if self.shopify_operation == "import_unshipped_orders":
                self.orders_from_date = instance.last_date_order_import or False
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_import_order_instance_')
            elif self.shopify_operation == "import_shipped_orders":
                self.orders_from_date = instance.last_shipped_order_import_date or False
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_import_shipped_order_instance_')
            elif self.shopify_operation == "import_cancel_orders":
                self.orders_from_date = instance.last_cancel_order_import_date or False
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_import_cancel_order_instance_')
            elif self.shopify_operation == "import_buy_with_prime_orders":
                self.orders_from_date = instance.last_buy_with_prime_order_import_date or False
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_import_buy_with_prime_order_instance_')
            elif self.shopify_operation == "sync_product":
                self.orders_from_date = instance.shopify_last_date_product_import or False
            elif self.shopify_operation == 'update_order_status':
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_update_order_status_instance_')
            elif self.shopify_operation == 'export_stock':
                self.shopify_check_running_schedulers('ir_cron_shopify_auto_export_inventory_instance_')
            self.orders_to_date = current_time
            self.export_stock_from = instance.shopify_last_date_update_stock or datetime.now() - timedelta(30)
            if instance.payout_last_import_date:
                self.payout_start_date = instance.payout_last_import_date
            self.payout_end_date = current_time

    def set_shopify_video_based_on_operation(self):
        """
        This method is used to set video link based on operation
        @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 28 June 2022.
        Task_id: 193395 - Add video link while perform operation
        """
        if self.shopify_operation in ['sync_product', 'import_products_from_csv']:
            self.shopify_video_url = 'https://www.youtube.com/watch?v=NbYkqmiUFFs&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=3'

        if self.shopify_operation == 'import_customers':
            self.shopify_video_url = 'https://www.youtube.com/watch?v=_X6ZbxMOMC8&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=15'

        if self.shopify_operation == 'import_unshipped_orders':
            self.shopify_video_url = 'https://www.youtube.com/watch?v=7aboj1fLYrA&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=8'

        if self.shopify_operation == 'import_shipped_orders':
            self.shopify_video_url = 'https://www.youtube.com/watch?v=iiSQINGFY5U&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=10'

        if self.shopify_operation == 'update_order_status':
            self.shopify_video_url = 'https://www.youtube.com/watch?v=qOFObt6qpSw&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=9'

        if self.shopify_operation == 'import_stock':
            self.shopify_video_url = 'https://www.youtube.com/watch?v=BPcGRZ7BKNE&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=14'

        if self.shopify_operation == 'export_stock':
            self.shopify_video_url = 'https://www.youtube.com/watch?v=Ea6ppXEpEXA&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=13'

        if self.shopify_operation == 'import_location':
            self.shopify_video_url = 'https://www.youtube.com/watch?v=41qTs4UQ1QU&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=5'

    def import_products_from_file(self):
        """
        This method is use to import product from csv,xlsx,xls.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2 December 2021 .
        Task_id: 180489 - Prepare for export changes
        """
        try:
            if os.path.splitext(self.file_name)[1].lower() not in ['.csv', '.xls', '.xlsx']:
                raise UserError(_("Invalid file format. You are only allowed to upload .csv, .xlsx file."))
            if os.path.splitext(self.file_name)[1].lower() == '.csv':
                self.import_products_from_csv()
            else:
                self.import_products_from_xlsx()
        except Exception as error:
            raise UserError(_("Receive the error while import file. %s", error))

    def import_products_from_csv(self):
        """
        This method used to import product using csv file in shopify third layer.
        @author: Maulik Barad on Date 12-Oct-2020.
        """
        file_data = self.read_file()
        self.validate_required_csv_header(file_data.fieldnames)
        self.create_products_from_file(file_data)
        return True

    def import_products_from_xlsx(self):
        """
        This method used to import product using xlsx file in shopify layer.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2 December 2021 .
        Task_id: 180489 - Prepare for export changes
        """
        header, product_data = self.read_xlsx_file()
        self.validate_required_csv_header(header)
        self.create_products_from_file(product_data)
        return True

    def validate_required_csv_header(self, header):
        """ This method is used to validate required csv header while csv file import for products.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        required_fields = ["template_name", "product_name", "product_default_code",
                           "shopify_product_default_code", "product_description",
                           "PRODUCT_TEMPLATE_ID", "PRODUCT_ID", "CATEGORY_ID"]

        for required_field in required_fields:
            if required_field not in header:
                raise UserError(_("Required column is not available in File."))

    def create_products_from_file(self, file_data):
        """
        This method is used to create products in Shopify product layer from the file.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2 December 2021 .
        Task_id:180489 - Prepare for export changes
        """
        prepare_product_for_export_obj = self.env["shopify.prepare.product.for.export.ept"]
        common_log_line_obj = self.env["common.log.lines.ept"]
        model = "shopify.product.product.ept"
        instance = self.shopify_instance_id
        sequence = 0
        row_no = 0
        shopify_template_id = False
        for record in file_data:
            row_no += 1
            message = ""
            if not record["PRODUCT_TEMPLATE_ID"] or not record["PRODUCT_ID"] or not record["CATEGORY_ID"]:
                message += "PRODUCT_TEMPLATE_ID Or PRODUCT_ID Or CATEGORY_ID Not As Per Odoo Product in file at row " \
                           "%s " % row_no
                common_log_line_obj.create_common_log_line_ept(shopify_instance_id=instance.id, module="shopify_ept",
                                                               message=message,
                                                               model_name=model)
                continue

            shopify_template, shopify_template_id, sequence = self.create_or_update_shopify_template_from_csv(instance,
                                                                                                              record,
                                                                                                              shopify_template_id,
                                                                                                              sequence)

            shopify_variant = self.create_or_update_shopify_variant_from_csv(instance, record, shopify_template_id,
                                                                             sequence)
            prepare_product_for_export_obj.create_shopify_variant_images(shopify_template, shopify_variant)

        return True

    def create_or_update_shopify_template_from_csv(self, instance, record, shopify_template_id, sequence):
        """ This method is used to create or update shopify template while process from csv file import.
            :param record: One row data of csv file.
            @return: shopify_template, shopify_template_id, sequence
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        shopify_product_template = self.env["shopify.product.template.ept"]
        prepare_product_for_export_obj = self.env["shopify.prepare.product.for.export.ept"]
        shopify_template = shopify_product_template.search(
            [("shopify_instance_id", "=", instance.id),
             ("product_tmpl_id", "=", int(record["PRODUCT_TEMPLATE_ID"]))], limit=1)

        shopify_product_template_vals = {"product_tmpl_id": int(record["PRODUCT_TEMPLATE_ID"]),
                                         "shopify_instance_id": instance.id,
                                         "shopify_product_category": int(record["CATEGORY_ID"]),
                                         "name": record["template_name"]}
        if self.env["ir.config_parameter"].sudo().get_param("shopify_ept.set_sales_description"):
            shopify_product_template_vals.update({"description": record["product_description"]})
        if not shopify_template:
            shopify_template = shopify_product_template.create(shopify_product_template_vals)
            sequence = 1
            shopify_template_id = shopify_template.id
        elif shopify_template_id != shopify_template.id:
            shopify_template.write(shopify_product_template_vals)
            shopify_template_id = shopify_template.id

        prepare_product_for_export_obj.create_shopify_template_images(shopify_template)

        if shopify_template and shopify_template.shopify_product_ids and \
                shopify_template.shopify_product_ids[0].sequence:
            sequence += 1

        return shopify_template, shopify_template_id, sequence

    def create_or_update_shopify_variant_from_csv(self, instance, record, shopify_template_id, sequence):
        """ This method is used to create or update Shopify variants while processing from CSV file import operation.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        shopify_product_obj = self.env["shopify.product.product.ept"]
        shopify_variant = shopify_product_obj.search(
            [("shopify_instance_id", "=", instance.id),
             ("product_id", "=", int(record["PRODUCT_ID"])),
             ("shopify_template_id", "=", shopify_template_id)])
        shopify_variant_vals = {"shopify_instance_id": instance.id,
                                "product_id": int(record["PRODUCT_ID"]),
                                "shopify_template_id": shopify_template_id,
                                "default_code": record["shopify_product_default_code"],
                                "name": record["product_name"],
                                "sequence": sequence}
        if not shopify_variant:
            shopify_variant = shopify_product_obj.create(shopify_variant_vals)
        else:
            shopify_variant.write(shopify_variant_vals)

        return shopify_variant

    def read_file(self):
        """
        This method reads .csv file
        @author: Nilesh Parmar @Emipro Technologies Pvt. Ltd on date 08/11/2019
        """
        import_file = BytesIO(base64.decodebytes(self.csv_file))
        file_read = StringIO(import_file.read().decode())
        reader = csv.DictReader(file_read, delimiter=",")

        return reader

    def read_xlsx_file(self):
        """
        This method is use to read the xlsx file data.
        @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 2 December 2021 .
        Task_id: 180489 - Prepare for export changes
        """
        validation_header = []
        product_data = []
        sheets = xlrd.open_workbook(file_contents=base64.b64decode(self.csv_file.decode('UTF-8')))
        header = dict()
        is_header = False
        for sheet in sheets.sheets():
            for row_no in range(sheet.nrows):
                if not is_header:
                    headers = [d.value for d in sheet.row(row_no)]
                    validation_header = headers
                    [header.update({d: headers.index(d)}) for d in headers]
                    is_header = True
                    continue
                row = dict()
                [row.update({k: sheet.row(row_no)[v].value}) for k, v in header.items() for c in
                 sheet.row(row_no)]
                product_data.append(row)
        return validation_header, product_data

    def import_shopify_location(self):
        """ This method is used to call the child method to import the Shopify location from Shopify to Odoo.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 10 November 2020 .
            Task_id: 168214 - Import locations process
        """
        shopify_location_obj = self.env["shopify.location.ept"]
        shopify_locations = shopify_location_obj.import_shopify_locations(self.shopify_instance_id)
        return shopify_locations

    def shopify_check_running_schedulers(self, cron_xml_id):
        """ This method is used to check that selected operation cron is running or not.
            :param cron_xml_id: Xml id of the scheduler action.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 12 November 2020 .
            Task_id: 167717 - Manual operation & cron execution conflict
        """
        try:
            cron_id = self.env.ref('shopify_ept.%s%d' % (cron_xml_id, self.shopify_instance_id.id))
        except:
            return
        if cron_id and cron_id.sudo().active:
            res = cron_id.try_cron_lock()
            if res == None:
                res = {}
            if res and res.get('reason') or res.get('result') == 0:
                message = "You are not allowed to run this process.The Scheduler is already started the Process."
                self.cron_process_notification = message
                self.is_hide_operation_execute_button = True
            if res and res.get('result'):
                self.cron_process_notification = "This process is also performed by a scheduler, and the next " \
                                                 "schedule for this process will run in %s minutes." % res.get('result')
            elif res and res.get('reason'):
                self.cron_process_notification = res.get('reason')
