# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.addons.web_editor.tools import get_video_embed_code
from .. import shopify


class ShopifyInstanceConfig(models.TransientModel):
    _name = "res.config.shopify.instance"
    _description = "Shopify Instance Configuration"

    name = fields.Char(help="Any User friendly name to identify the Shopify store")
    shopify_api_key = fields.Char("API Key", required=True, help="Shopify API Key. You can find "
                                                                 "it under Shopify store control "
                                                                 "panel.")
    shopify_password = fields.Char("Password", required=True, help="Shopify API Password. You can "
                                                                   "find it under Shopify store control panel")
    shopify_shared_secret = fields.Char("Secret Key", required=True, help="Shopify API Shared Secret. You can find it "
                                                                          "under Shopify store control panel")
    shopify_host = fields.Char("Host", required=True,
                               help="Add your shopify store URL, for example, https://my-shopify-store.myshopify.com")
    shopify_company_id = fields.Many2one("res.company", string="Instance Company",
                                         help="Orders and Invoices will be generated of this company.")

    shopify_instance_video_url = fields.Char('Instance Video URL',
                                             default='https://www.youtube.com/watch?v=kWmHTIujBmQ&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=2',
                                             help='URL of a video for showcasing by instance.')
    shopify_instance_video_embed_code = fields.Html(compute="_compute_shopify_instance_video_embed_code",
                                                    sanitize=False)

    shopify_api_video_url = fields.Char('API Video URL',
                                        default='https://www.youtube.com/watch?v=8QgZ4bp-7MA&list=PLZGehiXauylZAowR8580_18UZUyWRjynd&index=1&t=4s',
                                        help='URL of a video for showcasing by instance.')
    shopify_api_video_embed_code = fields.Html(compute="_compute_shopify_instance_video_embed_code",
                                               sanitize=False)

    @api.depends('shopify_instance_video_url', 'shopify_api_video_url')
    def _compute_shopify_instance_video_embed_code(self):
        for image in self:
            image.shopify_instance_video_embed_code = get_video_embed_code(image.shopify_instance_video_url)
            image.shopify_api_video_embed_code = get_video_embed_code(image.shopify_api_video_url)

    def create_pricelist(self, shop_currency):
        """
        This method creates pricelist from currency of the Shopify store.
        @author: Maulik Barad on Date 25-Sep-2020.
        @param shop_currency: Currency got from shopify store.
        """
        currency_obj = self.env["res.currency"]
        pricelist_obj = self.env["product.pricelist"]

        currency_id = currency_obj.search([("name", "=", shop_currency)], limit=1)

        if not currency_id:
            currency_id = currency_obj.search([("name", "=", shop_currency), ("active", "=", False)], limit=1)
            currency_id.write({"active": True})
        if not currency_id:
            currency_id = self.env.user.currency_id

        price_list_name = self.name + " " + "PriceList"
        pricelist = pricelist_obj.search([("name", "=", price_list_name),
                                          ("currency_id", "=", currency_id.id),
                                          ("company_id", "=", self.shopify_company_id.id)],
                                         limit=1)
        if not pricelist:
            pricelist = pricelist_obj.create({"name": price_list_name,
                                              "currency_id": currency_id.id,
                                              "company_id": self.shopify_company_id.id})

        return pricelist.id

    def shopify_test_connection(self):
        """This method used to verify whether Odoo is capable of connecting with Shopify store or not.
            @return : Action of type reload.
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 04/10/2019.
        """
        instance_obj = self.env["shopify.instance.ept"]
        shopify_location_obj = self.env["shopify.location.ept"]
        payment_gateway_obj = self.env["shopify.payment.gateway.ept"]
        financial_status_obj = self.env["sale.auto.workflow.configuration.ept"]

        instance_id = instance_obj.with_context(active_test=False).search(
            ["|", ("shopify_api_key", "=", self.shopify_api_key),
             ("shopify_host", "=", self.shopify_host)], limit=1)
        if instance_id:
            raise UserError(_(
                "An instance already exists for the given details \nShopify API key : '%s' \nShopify Host : '%s'" % (
                    self.shopify_api_key, self.shopify_host)))

        if not self.shopify_host.__contains__('myshopify') or not self.shopify_host.__contains__('https'):
            raise UserError(
                _("A host should contain both 'https' and 'myshopify', for example: 'https://odoo-v16.myshopify.com'. You can refer the host in your Shopify store: Shopify => Settings => Domains"))

        shop_url = instance_obj.prepare_shopify_shop_url(self.shopify_host, self.shopify_api_key, self.shopify_password)

        shopify.ShopifyResource.set_site(shop_url)

        try:
            shop_id = shopify.Shop.current()
        except Exception as error:
            raise UserError(error)

        shop_detail = shop_id.to_dict()

        vals = self.prepare_val_for_instance_creation(shop_detail)

        shopify_instance = instance_obj.create(vals)
        shopify_location_obj.import_shopify_locations(shopify_instance)

        payment_gateway_obj.import_payment_gateway(shopify_instance)
        financial_status_obj.create_financial_status(shopify_instance, "paid")

        if self._context.get('is_calling_from_onboarding_panel', False):
            company = shopify_instance.shopify_company_id
            shopify_instance.write({'is_instance_create_from_onboarding_panel': True})
            company.set_onboarding_step_done('shopify_instance_onboarding_state')
            company.write({'is_create_shopify_more_instance': True})

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def prepare_val_for_instance_creation(self, shop_detail):
        """ This method is used to prepare a vals for instance creation.
            :param shop_detail: Response of shopify.
            @return: vals
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 26 October 2020 .
            Task_id: 167537 - Code refactoring
        """
        warehouse_obj = self.env['stock.warehouse']
        ir_model_obj = self.env["ir.model.fields"]
        shop_currency = shop_detail.get("currency")
        warehouse = warehouse_obj.search([('company_id', '=', self.shopify_company_id.id)], limit=1, order='id')
        pricelist_id = self.create_pricelist(shop_currency)

        stock_field = ir_model_obj.search(
            [("model_id.model", "=", "product.product"), ("name", "=", "free_qty")],
            limit=1)
        vals = {
            "name": self.name,
            "shopify_api_key": self.shopify_api_key,
            "shopify_password": self.shopify_password,
            "shopify_shared_secret": self.shopify_shared_secret,
            "shopify_host": self.shopify_host,
            "shopify_company_id": self.shopify_company_id.id,
            "shopify_warehouse_id": warehouse.id,
            "shopify_store_time_zone": shop_detail.get("iana_timezone"),
            "shopify_pricelist_id": pricelist_id or False,
            "apply_tax_in_order": "create_shopify_tax",
            "shopify_stock_field": stock_field and stock_field.id or False
        }
        return vals

    @api.model
    def action_shopify_open_shopify_instance_wizard(self):
        """ Called by onboarding panel above the Instance."""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "shopify_ept.shopify_on_board_instance_configuration_action")
        action['context'] = {'is_calling_from_onboarding_panel': True}
        instance = self.env['shopify.instance.ept'].search_shopify_instance()
        if instance:
            action.get('context').update({
                'default_name': instance.name,
                'default_shopify_host': instance.shopify_host,
                'default_shopify_api_key': instance.shopify_api_key,
                'default_shopify_password': instance.shopify_password,
                'default_shopify_shared_secret': instance.shopify_shared_secret,
                'default_shopify_company_id': instance.shopify_company_id.id,
                'is_already_instance_created': True,
            })
            company = instance.shopify_company_id
            if company.shopify_instance_onboarding_state != 'done':
                company.set_onboarding_step_done('shopify_instance_onboarding_state')
        return action

    def reset_credentials(self):
        """
        This method set the new credentials and check if connection can be made properly.
        @author: Maulik Barad on Date 01-Oct-2020.
        """
        shopify_instance_obj = self.env["shopify.instance.ept"]
        context = self.env.context
        instance_id = context.get("shopify_instance_id")

        instance = shopify_instance_obj.browse(instance_id)
        if instance.shopify_api_key == self.shopify_api_key or instance.shopify_password == self.shopify_password or \
                instance.shopify_shared_secret == self.shopify_shared_secret:
            raise UserError(_("Entered credentials are same as previous.\nPlease verify the credentials once."))

        vals = {"shopify_api_key": self.shopify_api_key,
                "shopify_password": self.shopify_password,
                "shopify_shared_secret": self.shopify_shared_secret}
        instance.shopify_test_connection(vals)
        if context.get("test_connection"):
            return {"type": "ir.actions.client", "tag": "display_notification",
                    "params": {"title": "Shopify",
                               "message": "New Credentials are working properly!",
                               "sticky": False}}
        instance.write(vals)

        return True


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def _get_shopify_default_financial_statuses(self):
        if self._context.get('default_shopify_instance_id', False):
            financial_status_ids = self.env['sale.auto.workflow.configuration.ept'].search(
                [('shopify_instance_id', '=', self._context.get('default_shopify_instance_id', False))]).ids
            return [(6, 0, financial_status_ids)]

    @api.model
    def _default_buy_with_prime_tag_ids(self):
        """ Set default tag for buy with prime order.
            @author: Nilam Kubavat @Emipro Technologies Pvt. Ltd on date 18 December 2023.
            Task_id: 4726
        """
        tag_ids = self.env.ref('shopify_ept.shopify_product_tag_buy_with_prime')
        return [(6, 0, [tag_ids.id])] if tag_ids else False

    @api.model
    def _get_default_return_location(self):
        shopify_location_obj = self.env['shopify.location.ept']
        shopify_warehouse = shopify_location_obj.search([]).warehouse_for_order
        locations = self.env['stock.location'].search([('location_id', 'child_of', shopify_warehouse.lot_stock_id.ids)])
        return [('id', 'in', locations.ids)]

    shopify_instance_id = fields.Many2one("shopify.instance.ept", "Shopify Instance")
    shopify_company_id = fields.Many2one("res.company", string="Shopify Instance Company",
                                         help="Orders and Invoices will be generated of this company.")
    shopify_warehouse_id = fields.Many2one("stock.warehouse", string="Shopify Warehouse",
                                           domain="[('company_id', '=',shopify_company_id)]")
    auto_import_product = fields.Boolean(string="Auto Create Product if not found?",
                                         help="This option creates a new product in your catalogue if system couldn't "
                                              "find the product based on SKU / Internal Reference / Default Product "
                                              "Code. If you are selling on multiple sales channels and "
                                              "having different SKU / Internal Reference / Default Product Code on "
                                              "each sales channel, it may lead to creation of duplicate products in "
                                              "your product catalogue in your database. So we request you to "
                                              "enable this option, as per your product catalogue configuration.")
    shopify_sync_product_with = fields.Selection([("sku", "Internal Reference(SKU)"), ("barcode", "Barcode"),
                                                  ("sku_or_barcode", "Internal Reference(SKU) and Barcode")],
                                                 string="Sync Product With", default="sku",
                                                 help="While sync products from Shopify to Odoo at the moment it will "
                                                      "sync Odoo and Shopify products base on the selection")
    shopify_pricelist_id = fields.Many2one("product.pricelist", string="Shopify Pricelist",
                                           help="Select Pricelist, This price list used to import the "
                                                "product price and set this pricelist in Shopify sale order")
    shopify_compare_pricelist_id = fields.Many2one("product.pricelist", string="Shopify Compare Price Pricelist",
                                                   help="Select Pricelist, This price list used to import the "
                                                        "product price and set this pricelist in Shopify sale order")
    shopify_stock_field = fields.Many2one("ir.model.fields", string="Stock Field",
                                          help="Select inventory field for shopify products")
    shopify_section_id = fields.Many2one("crm.team", "Shopify Sales Team", help="Set the sales team for shopify orders")
    shopify_is_use_default_sequence = fields.Boolean("Use Odoo Default Sequence in Shopify Orders",
                                                     help="If checked,Then use default sequence of odoo while create "
                                                          "sale order.")
    shopify_order_prefix = fields.Char(size=10, string="Order Prefix", help="Enter your order prefix")
    shopify_apply_tax_in_order = fields.Selection(
        [("odoo_tax", "Odoo Default Tax Behaviour"), ("create_shopify_tax", "Create New Tax If Not Found")],
        copy=False, default="create_shopify_tax", help=""" For Shopify Orders :- \n
                    1) Odoo Default Tax Behaviour - The Taxes will be set based on Odoo's default functional 
                    behaviour i.e. based on Odoo's Tax and Fiscal Position configurations. \n
                    2) Create New Tax If Not Found - System will search the tax data received 
                    from Shopify in Odoo, will create a new one if it fails in finding it.""")
    shopify_invoice_tax_account_id = fields.Many2one("account.account", string="Invoice Tax Account For Shopify Tax",
                                                     help="Set the invoice tax account base on this account we will "
                                                          "set this account in the newly created tax when import orders"
                                                          "from Shopify to Odoo.")
    shopify_credit_tax_account_id = fields.Many2one("account.account", string="Credit Note Tax Account For Shopify Tax",
                                                    help="Set the credit tax account base on this account we will set "
                                                         "this account in the newly created tax when import import "
                                                         "from Shopify to Odoo.")
    shopify_notify_customer = fields.Boolean("Notify Customer about Update Order Status?",
                                             help="If checked,Notify the customer via email about Update Order Status")
    shopify_user_ids = fields.Many2many("res.users", "shopify_res_config_settings_res_users_rel",
                                        "res_config_settings_id", "res_users_id", string="Responsible User")
    shopify_activity_type_id = fields.Many2one("mail.activity.type", string="Shopify Activity Type")
    shopify_date_deadline = fields.Integer("Deadline Lead Days for Shopify", default=1,
                                           help="its add number of  days in schedule activity deadline date ")
    is_shopify_create_schedule = fields.Boolean("Create Schedule activity ? ", default=False,
                                                help="If checked, Then it will create Schedule Activity against "
                                                     "order data queues will any queue line failed, Export stock "
                                                     "queue and update order status")
    # fields for payout schedule activity
    shopify_payout_user_ids = fields.Many2many('res.users', 'shopify_res_config_payout_settings_res_users_rel',
                                               'res_config_settings_id', 'res_users_id',
                                               string='Responsible User For Payout Reports', domain=lambda self: [
            ('groups_id', 'in', self.env.ref('account.group_account_user').id)])
    shopify_sync_product_with_images = fields.Boolean("Sync/Import Images?", default=False,
                                                      help="Check if you want to import images along with products")
    create_shopify_products_webhook = fields.Boolean("Manage Shopify Products via Webhooks",
                                                     help="True : It will create all product related webhooks.\n"
                                                          "False : All product related webhooks will be deactivated.")
    create_shopify_customers_webhook = fields.Boolean("Manage Shopify Customers via Webhooks",
                                                      help="True : It will create all customer related webhooks.\n"
                                                           "False : All customer related webhooks will be deactivated.")
    create_shopify_orders_webhook = fields.Boolean("Manage Shopify Orders via Webhooks",
                                                   help="True : It will create all order related webhooks.\n"
                                                        "False : All order related webhooks will be deactivated.")
    shopify_default_pos_customer_id = fields.Many2one("res.partner", "Default POS customer",
                                                      help="This customer will be set in POS order, when"
                                                           "customer is not found.",
                                                      domain="[('customer_rank','>', 0)]")
    shopify_settlement_report_journal_id = fields.Many2one("account.journal", string="Payout Report Journal",
                                                           help="Creates Bank Statement using this journal while process Payout Report")
    shopify_payout_last_date_import = fields.Date(string="Import Payout Reports",
                                                  help="It is used to store last update shopify payout report")
    shopify_financial_status_ids = fields.Many2many('sale.auto.workflow.configuration.ept',
                                                    'shopify_sale_auto_workflow_conf_rel',
                                                    'financial_onboarding_status_id', 'workflow_id',
                                                    string='Shopify Financial Status',
                                                    default=_get_shopify_default_financial_statuses)
    shopify_set_sales_description_in_product = fields.Boolean("Use Sales Description of Odoo Product for shopify",
                                                              config_parameter="shopify_ept.set_sales_description",
                                                              help="In both odoo products and Woocommerce layer products, "
                                                                   "it is used to set the description. For more details, "
                                                                   "please read the following summary.")
    shopify_order_status_ids = fields.Many2many('import.shopify.order.status',
                                                'shopify_config_settings_order_status_rel',
                                                'shopify_config_id', 'status_id',
                                                "Shopify Import Order Status",
                                                help="Select order status in which you want to import the orders from Shopify to Odoo.")
    auto_fulfill_gift_card_order = fields.Boolean(
        "Automatically fulfill only the gift cards of the order", default=True,
        help="If unchecked, It will fulfill qty from Odoo to shopify in update order status process")

    shopify_import_order_after_date = fields.Datetime(
        help="Connector only imports those orders which have created after a given date.")

    # Analytic
    shopify_analytic_account_id = fields.Many2one('account.analytic.account', string='Shopify Analytic Account',
                                                  domain="['|', ('company_id', '=', False), ('company_id', '=', shopify_company_id)]",
                                                  help="Set the Analytic Account for shopify orders."
                                                       "Note :- The configuration of the analytic account for this "
                                                       "instance will be applied to all sales orders created by the "
                                                       "connector. With this configuration, the Analytic Default Rule "
                                                       "configured in Odoo will not apply to Shopify orders Invoices."
                                                       "If you wish to use Odoo Analytic Default Rule, you will not "
                                                       "have to configure any analytic account here.")
    # shopify_analytic_tag_ids = fields.Many2many('account.analytic.tag', 'shopify_res_config_analytic_account_tag_rel',
    #                                             string='Shopify Analytic Tags',
    #                                             domain="['|', ('company_id', '=', False),
    #                                             ('company_id', '=', shopify_company_id)]")
    shopify_lang_id = fields.Many2one('res.lang', string='Shopify Instance Language',
                                      help="Select language for Shopify customer.")
    # presentment currency
    order_visible_currency = fields.Boolean(string="Import order in customer visible currency?",
                                            help="If checked, It will import orders based on the customer's visible"
                                                 "currency through which the customer has paid the payment for orders.")

    is_delivery_fee = fields.Boolean(string='Are you selling for Colorado State(US)',
                                     help="If checked, the connector will add a delivery fee line to the order.")
    delivery_fee_name = fields.Char(string='Delivery fee name',
                                    help="The name you enter here must match the label on the Shopify order "
                                         "that shows the Colorado delivery fees applied.")

    show_net_profit_report = fields.Boolean(config_parameter="shopify_ept.show_net_profit_report")
    is_shopify_digest = fields.Boolean(help="If checked, Then it will send periodic digest per KPI.")
    is_delivery_multi_warehouse = fields.Boolean(string="Is Delivery from Multiple warehouse?",
                                                 help="If checked, It will update order status based on "
                                                      "multiple warehouse in Shopify store.")
    import_customer_as_company = fields.Boolean(string="Import customer as a Company",
                                                help="If checked, it will create an individual Company type partner "
                                                     "from the Company name and customer will be created as a "
                                                     "child partner of Company.")
    shopify_product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                                             domain="[('category_id.name', '=', 'Weight')]")
    use_default_terms_and_condition_of_odoo = fields.Boolean("Use Default Terms & Condition of Odoo",
                                                             config_parameter="shopify_ept.use_default_terms_and_condition_of_odoo",
                                                             help="If checked, it will set the custom note and default terms and condition in order note")
    ship_order_webhook = fields.Boolean("Want to ship order", help="If checked, it will fulfill order in odoo")
    forcefully_reserve_stock_webhook = fields.Boolean("ForceFully Reserve Stock",
                                                      help="If checked, It will forcefully reserve stock in the picking")
    refund_order_webhook = fields.Boolean("Want to refund order", help="If checked, it will create a refund in odoo")
    customer_order_webhook = fields.Boolean("Want to update customer",
                                            help="If checked, it will update the customer in order")
    update_qty_order_webhook = fields.Boolean("Want to update Quantity",
                                              help="If checked, it will update the customer in order")
    add_new_product_order_webhook = fields.Boolean("Want to Add New Product",
                                                   help="If checked, it will add new product in the order if receive in the webhook")

    import_buy_with_prime_shopify_order = fields.Boolean(string="Import Buy with Prime Orders",
                                                         help="If checked, it will import order of buy with prime orders")
    buy_with_prime_warehouse_id = fields.Many2one("stock.warehouse", string="Shopify Warehouse for Buy with prime",
                                                  domain="[('company_id', '=',shopify_company_id)]")
    buy_with_prime_tag_ids = fields.Many2many("shopify.tags", "buy_with_prime_shopify_tags_rel",
                                              "product_tmpl_id", "tag_id",
                                              "Tags for import buy with prime orders",
                                              default=_default_buy_with_prime_tag_ids)
    Force_transfer_move_of_buy_with_prime_orders = fields.Boolean(string="Force Transfer",
                                                                  help="If checked, it will forcefully done the stock move while stock also not there.")
    return_picking_order = fields.Boolean("Want to return picking", help="If checked, it will create a return in odoo")
    stock_validate_for_return = fields.Boolean("Want to validate return picking",
                                               help="If checked, it will validate a return picking")
    return_location_id = fields.Many2one('stock.location', 'Return Location',
                                         domain=lambda self: self._get_default_return_location())
    update_qty_to_invoice_order_webhook = fields.Boolean("Want to changes to invoice as per update Quantity",
                                                         help="If checked, it will update invoice based on updated quantity")
    credit_note_register_payment = fields.Boolean("Want to create register payment for credit note",
                                                  help="If checked, it will create a payment for credit note")
    credit_note_payment_journal = fields.Many2one("account.journal", string="Credit Note Payment Journal",
                                                           help=" Selected Journal will be set in Credit note Payment journal.")

    @api.onchange("shopify_instance_id")
    def onchange_shopify_instance_id(self):
        instance = self.shopify_instance_id or False
        if instance:
            self.shopify_company_id = instance.shopify_company_id and instance.shopify_company_id.id or False
            self.shopify_warehouse_id = instance.shopify_warehouse_id and instance.shopify_warehouse_id.id or False
            self.auto_import_product = instance.auto_import_product or False
            self.shopify_sync_product_with = instance.shopify_sync_product_with
            self.shopify_pricelist_id = instance.shopify_pricelist_id and instance.shopify_pricelist_id.id or False
            self.shopify_compare_pricelist_id = instance.shopify_compare_pricelist_id and instance.shopify_compare_pricelist_id.id or False
            self.shopify_stock_field = instance.shopify_stock_field and instance.shopify_stock_field.id or False
            self.shopify_section_id = instance.shopify_section_id.id or False
            self.shopify_order_prefix = instance.shopify_order_prefix
            self.shopify_is_use_default_sequence = instance.is_use_default_sequence
            self.shopify_apply_tax_in_order = instance.apply_tax_in_order
            self.shopify_invoice_tax_account_id = instance.invoice_tax_account_id and \
                                                  instance.invoice_tax_account_id.id or False
            self.shopify_credit_tax_account_id = instance.credit_tax_account_id and \
                                                 instance.credit_tax_account_id.id or False
            self.shopify_notify_customer = instance.notify_customer
            self.shopify_user_ids = instance.shopify_user_ids or False
            self.shopify_activity_type_id = instance.shopify_activity_type_id or False
            self.shopify_date_deadline = instance.shopify_date_deadline or False
            self.is_shopify_create_schedule = instance.is_shopify_create_schedule or False
            self.shopify_sync_product_with_images = instance.sync_product_with_images or False
            self.create_shopify_products_webhook = instance.create_shopify_products_webhook
            self.create_shopify_customers_webhook = instance.create_shopify_customers_webhook
            self.create_shopify_orders_webhook = instance.create_shopify_orders_webhook
            self.shopify_default_pos_customer_id = instance.shopify_default_pos_customer_id
            self.shopify_payout_last_date_import = instance.payout_last_import_date or False
            self.shopify_settlement_report_journal_id = instance.shopify_settlement_report_journal_id or False
            self.shopify_order_status_ids = instance.shopify_order_status_ids.ids
            # self.auto_fulfill_gift_card_order = instance.auto_fulfill_gift_card_order
            self.shopify_import_order_after_date = instance.import_order_after_date or False
            self.shopify_analytic_account_id = instance.shopify_analytic_account_id.id or False
            # self.shopify_analytic_tag_ids = instance.shopify_analytic_tag_ids.ids
            self.shopify_lang_id = instance.shopify_lang_id and instance.shopify_lang_id.id or False
            self.order_visible_currency = instance.order_visible_currency or False
            self.is_shopify_digest = instance.is_shopify_digest or False
            self.is_delivery_fee = instance.is_delivery_fee or False
            self.delivery_fee_name = instance.delivery_fee_name
            self.is_delivery_multi_warehouse = instance.is_delivery_multi_warehouse or False
            self.import_customer_as_company = instance.import_customer_as_company or False
            self.shopify_product_uom_id = instance.shopify_product_uom_id and instance.shopify_product_uom_id.id or False
            self.ship_order_webhook = instance.ship_order_webhook
            self.forcefully_reserve_stock_webhook = instance.forcefully_reserve_stock_webhook
            self.refund_order_webhook = instance.refund_order_webhook
            self.customer_order_webhook = instance.customer_order_webhook
            self.update_qty_order_webhook = instance.update_qty_order_webhook
            self.add_new_product_order_webhook = instance.add_new_product_order_webhook
            self.import_buy_with_prime_shopify_order = instance.import_buy_with_prime_shopify_order
            self.buy_with_prime_warehouse_id = instance.buy_with_prime_warehouse_id and instance.buy_with_prime_warehouse_id.id or False
            self.Force_transfer_move_of_buy_with_prime_orders = instance.Force_transfer_move_of_buy_with_prime_orders
            self.buy_with_prime_tag_ids = instance.buy_with_prime_tag_ids.ids
            self.shopify_payout_user_ids = instance.shopify_payout_user_ids or False
            self.return_picking_order = instance.return_picking_order
            self.stock_validate_for_return = instance.stock_validate_for_return
            self.return_location_id = instance.return_location_id and instance.return_location_id.id or False
            self.update_qty_to_invoice_order_webhook = instance.update_qty_to_invoice_order_webhook
            self.credit_note_register_payment = instance.credit_note_register_payment or False
            self.credit_note_payment_journal = instance.credit_note_payment_journal or False

    def execute(self):
        """This method used to set value in an instance of configuration.
            @param : self
            @author: Haresh Mori @Emipro Technologies Pvt. Ltd on date 04/10/2019.
        """
        instance = self.shopify_instance_id
        values = {}
        res = super(ResConfigSettings, self).execute()
        IrModule = self.env['ir.module.module']
        exist_module = IrModule.search([('name', '=', 'shopify_net_profit_report_ept'), ('state', '=', 'installed')])
        if instance:
            values["shopify_warehouse_id"] = self.shopify_warehouse_id and self.shopify_warehouse_id.id or False
            values["auto_import_product"] = self.auto_import_product or False
            values["shopify_sync_product_with"] = self.shopify_sync_product_with
            values["shopify_pricelist_id"] = self.shopify_pricelist_id and self.shopify_pricelist_id.id or False
            values[
                "shopify_compare_pricelist_id"] = self.shopify_compare_pricelist_id and self.shopify_compare_pricelist_id.id or False
            values["shopify_stock_field"] = self.shopify_stock_field and self.shopify_stock_field.id or False
            values["shopify_section_id"] = self.shopify_section_id and self.shopify_section_id.id or False
            values["shopify_order_prefix"] = self.shopify_order_prefix
            values["is_use_default_sequence"] = self.shopify_is_use_default_sequence
            values["apply_tax_in_order"] = self.shopify_apply_tax_in_order
            values["invoice_tax_account_id"] = self.shopify_invoice_tax_account_id and \
                                               self.shopify_invoice_tax_account_id.id or False
            values["credit_tax_account_id"] = self.shopify_credit_tax_account_id and \
                                              self.shopify_credit_tax_account_id.id or False
            values["notify_customer"] = self.shopify_notify_customer
            values["shopify_activity_type_id"] = self.shopify_activity_type_id and self.shopify_activity_type_id.id \
                                                 or False
            values["shopify_date_deadline"] = self.shopify_date_deadline or False
            values.update({"shopify_user_ids": [(6, 0, self.shopify_user_ids.ids)]})
            values["is_shopify_create_schedule"] = self.is_shopify_create_schedule
            values["sync_product_with_images"] = self.shopify_sync_product_with_images or False
            values["create_shopify_products_webhook"] = self.create_shopify_products_webhook
            values["create_shopify_customers_webhook"] = self.create_shopify_customers_webhook
            values["create_shopify_orders_webhook"] = self.create_shopify_orders_webhook
            values["shopify_default_pos_customer_id"] = self.shopify_default_pos_customer_id.id
            values["payout_last_import_date"] = self.shopify_payout_last_date_import or False
            values["shopify_settlement_report_journal_id"] = self.shopify_settlement_report_journal_id or False
            values['shopify_order_status_ids'] = [(6, 0, self.shopify_order_status_ids.ids)]
            # values["auto_fulfill_gift_card_order"] = self.auto_fulfill_gift_card_order
            values["import_order_after_date"] = self.shopify_import_order_after_date
            values["shopify_analytic_account_id"] = self.shopify_analytic_account_id and \
                                                    self.shopify_analytic_account_id.id or False
            # values["shopify_analytic_tag_ids"] = [(6, 0, self.shopify_analytic_tag_ids.ids)]
            values['shopify_lang_id'] = self.shopify_lang_id and self.shopify_lang_id.id or False
            values['order_visible_currency'] = self.order_visible_currency or False
            values['is_shopify_digest'] = self.is_shopify_digest or False
            values["is_delivery_fee"] = self.is_delivery_fee
            values["delivery_fee_name"] = self.delivery_fee_name
            values["is_delivery_multi_warehouse"] = self.is_delivery_multi_warehouse or False
            values["import_customer_as_company"] = self.import_customer_as_company or False
            values['shopify_product_uom_id'] = self.shopify_product_uom_id and self.shopify_product_uom_id.id or False
            values['ship_order_webhook'] = self.ship_order_webhook
            values['forcefully_reserve_stock_webhook'] = self.forcefully_reserve_stock_webhook
            values['refund_order_webhook'] = self.refund_order_webhook
            values['customer_order_webhook'] = self.customer_order_webhook
            values['update_qty_order_webhook'] = self.update_qty_order_webhook
            values['add_new_product_order_webhook'] = self.add_new_product_order_webhook
            values['import_buy_with_prime_shopify_order'] = self.import_buy_with_prime_shopify_order
            values[
                "buy_with_prime_warehouse_id"] = self.buy_with_prime_warehouse_id and self.buy_with_prime_warehouse_id.id or False
            values['Force_transfer_move_of_buy_with_prime_orders'] = self.Force_transfer_move_of_buy_with_prime_orders
            values['buy_with_prime_tag_ids'] = [(6, 0, self.buy_with_prime_tag_ids.ids)]
            values.update({"shopify_payout_user_ids": [(6, 0, self.shopify_payout_user_ids.ids)]})
            values['return_picking_order'] = self.return_picking_order
            values['stock_validate_for_return'] = self.stock_validate_for_return
            values["return_location_id"] = self.return_location_id and self.return_location_id.id or False
            product_webhook_changed = customer_webhook_changed = order_webhook_changed = False
            values['update_qty_to_invoice_order_webhook'] = self.update_qty_to_invoice_order_webhook
            values['credit_note_register_payment'] = self.credit_note_register_payment
            values['credit_note_payment_journal'] = self.credit_note_payment_journal or False
            if instance.create_shopify_products_webhook != self.create_shopify_products_webhook:
                product_webhook_changed = True
            if instance.create_shopify_customers_webhook != self.create_shopify_customers_webhook:
                customer_webhook_changed = True
            if instance.create_shopify_orders_webhook != self.create_shopify_orders_webhook:
                order_webhook_changed = True
            instance.write(values)

            if product_webhook_changed:
                instance.configure_shopify_product_webhook()
            if customer_webhook_changed:
                instance.configure_shopify_customer_webhook()
            if order_webhook_changed:
                instance.configure_shopify_order_webhook()

        if not self.show_net_profit_report and exist_module:
            exist_module.with_user(SUPERUSER_ID).button_immediate_uninstall()

        return res

    def download_shopify_net_profit_report_module(self):
        """
        This Method relocates download zip file of Shopify Net Profit Report module.
        @return: This Method return file download file.
        @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 08 August 2022.
        """
        attachment = self.env['ir.attachment'].search(
            [('name', '=', 'shopify_net_profit_report_ept.zip')])
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'new',
            'nodestroy': False,
        }

    @api.onchange("is_shopify_digest")
    def onchange_is_shopify_digest(self):
        """
        This method is used to create digest record based on Shopify instance.
        @author: Meera Sidapara on date 13-July-2022.
        @task: 194458 - Digest email development
        """
        try:
            digest_exist = self.env.ref('shopify_ept.digest_shopify_instance_%d' % self.shopify_instance_id.id)
        except:
            digest_exist = False
        if self.is_shopify_digest:
            shopify_cron = self.env['shopify.cron.configuration.ept']
            vals = self.prepare_val_for_digest()
            if digest_exist:
                vals.update({'name': digest_exist.name})
                digest_exist.write(vals)
            else:
                core_record = shopify_cron.check_core_shopify_cron(
                    "common_connector_library.connector_digest_digest_default")

                new_instance_digest = core_record.copy(default=vals)
                name = 'digest_shopify_instance_%d' % (self.shopify_instance_id.id)
                self.create_digest_data(name, new_instance_digest)
        else:
            if digest_exist:
                digest_exist.write({'state': 'deactivated'})

    def prepare_val_for_digest(self):
        """ This method is used to prepare a vals for the digest configuration.
            @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 13 July 2022.
            Task_id: 194458 - Digest email development
        """
        vals = {'state': 'activated',
                'name': 'Shopify : ' + self.shopify_instance_id.name + ' Periodic Digest',
                'module_name': 'shopify_ept',
                'shopify_instance_id': self.shopify_instance_id.id,
                'company_id': self.shopify_instance_id.shopify_company_id.id}
        return vals

    def create_digest_data(self, name, new_instance_digest):
        """ This method is used to create a digest record of ir model data
            @author: Meera Sidapara @Emipro Technologies Pvt. Ltd on date 13 July 2022.
            Task_id: 194458 - Digest email development
        """
        self.env['ir.model.data'].create({'module': 'shopify_ept',
                                          'name': name,
                                          'model': 'digest.digest',
                                          'res_id': new_instance_digest.id,
                                          'noupdate': True})

    @api.model
    def action_shopify_open_basic_configuration_wizard(self):
        """
           Usage: return the action for open the basic configurations wizard
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        try:
            view_id = self.env.ref('shopify_ept.shopify_basic_configurations_onboarding_wizard_view')
        except:
            return True
        return self.shopify_res_config_view_action(view_id)

    @api.model
    def action_shopify_open_financial_status_configuration_wizard(self):
        """
           Usage: return the action for open the basic configurations wizard
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        try:
            view_id = self.env.ref('shopify_ept.shopify_financial_status_onboarding_wizard_view')
        except:
            return True
        return self.shopify_res_config_view_action(view_id)

    def shopify_res_config_view_action(self, view_id):
        """
           Usage: return the action for open the configurations wizard
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "shopify_ept.action_shopify_instance_config")
        action_data = {'view_id': view_id.id, 'views': [(view_id.id, 'form')], 'target': 'new',
                       'name': 'Configurations'}
        instance = self.env['shopify.instance.ept'].search_shopify_instance()
        if instance:
            action['context'] = {'default_shopify_instance_id': instance.id}
        else:
            action['context'] = {}
        action.update(action_data)
        return action

    def shopify_save_basic_configurations(self):
        """
           Usage: Save the basic configuration changes in the instance
           @Task:   166992 - Shopify Onboarding panel
           @author: Dipak Gogiya
           :return: True
        """
        instance = self.shopify_instance_id
        if instance:
            basic_configuration_dict = {
                'shopify_company_id': self.shopify_company_id and self.shopify_company_id.id or False,
                'shopify_warehouse_id': self.shopify_warehouse_id and self.shopify_warehouse_id.id or False,
                'auto_import_product': self.auto_import_product or False,
                'sync_product_with_images': self.shopify_sync_product_with_images or False,
                'shopify_sync_product_with': self.shopify_sync_product_with or False,
                'shopify_pricelist_id': self.shopify_pricelist_id and self.shopify_pricelist_id.id or False,
                'shopify_compare_pricelist_id': self.shopify_compare_pricelist_id and self.shopify_compare_pricelist_id.id or False,
                'shopify_section_id': self.shopify_section_id and self.shopify_section_id.id or False,
                'is_use_default_sequence': self.shopify_is_use_default_sequence,
                'shopify_order_prefix': self.shopify_order_prefix or False,
                'shopify_default_pos_customer_id': self.shopify_default_pos_customer_id.id,
                'apply_tax_in_order': self.shopify_apply_tax_in_order,
                'invoice_tax_account_id': self.shopify_invoice_tax_account_id and
                                          self.shopify_invoice_tax_account_id.id or False,
                'credit_tax_account_id': self.shopify_credit_tax_account_id and
                                         self.shopify_credit_tax_account_id.id or False,
                'import_order_after_date': self.shopify_import_order_after_date,
                'shopify_analytic_account_id': self.shopify_analytic_account_id.id or False,
                # 'shopify_analytic_tag_ids': self.shopify_analytic_tag_ids.ids or False,
                'shopify_lang_id': self.shopify_lang_id and self.shopify_lang_id.id or False,
                'is_delivery_fee': self.is_delivery_fee,
                'delivery_fee_name': self.delivery_fee_name,
                'is_delivery_multi_warehouse': self.is_delivery_multi_warehouse or False,
                'import_customer_as_company': self.import_customer_as_company or False,
                'order_visible_currency': self.order_visible_currency or False,
                'shopify_product_uom_id': self.shopify_product_uom_id and self.shopify_product_uom_id.id or False,
            }

            instance.write(basic_configuration_dict)
            company = instance.shopify_company_id
            company.set_onboarding_step_done('shopify_basic_configuration_onboarding_state')
        return True

    def shopify_save_financial_status_configurations(self):
        """
            Usage: Save the changes in the Instance.
            @Task:   166992 - Shopify Onboarding panel
            @author: Dipak Gogiya, 22/09/2020
            :return: True
        """
        instance = self.shopify_instance_id
        if instance:
            product_webhook_changed = customer_webhook_changed = order_webhook_changed = False
            if instance.create_shopify_products_webhook != self.create_shopify_products_webhook:
                product_webhook_changed = True
            if instance.create_shopify_customers_webhook != self.create_shopify_customers_webhook:
                customer_webhook_changed = True
            if instance.create_shopify_orders_webhook != self.create_shopify_orders_webhook:
                order_webhook_changed = True

            instance.write({
                'shopify_stock_field': self.shopify_stock_field,
                'notify_customer': self.shopify_notify_customer,
                'shopify_settlement_report_journal_id': self.shopify_settlement_report_journal_id or False,
                'create_shopify_products_webhook': self.create_shopify_products_webhook,
                'create_shopify_customers_webhook': self.create_shopify_customers_webhook,
                'create_shopify_orders_webhook': self.create_shopify_orders_webhook,
                'is_shopify_digest': self.is_shopify_digest or False,
                "is_shopify_create_schedule": self.is_shopify_create_schedule,
                "shopify_user_ids": [(6, 0, self.shopify_user_ids.ids)],
                "shopify_activity_type_id": self.shopify_activity_type_id and self.shopify_activity_type_id.id or False,
                "shopify_date_deadline": self.shopify_date_deadline or False,
                "credit_note_payment_journal": self.credit_note_payment_journal or False,
            })

            if product_webhook_changed:
                instance.configure_shopify_product_webhook()
            if customer_webhook_changed:
                instance.configure_shopify_customer_webhook()
            if order_webhook_changed:
                instance.configure_shopify_order_webhook()

            company = instance.shopify_company_id
            company.set_onboarding_step_done('shopify_financial_status_onboarding_state')
            financials_status = self.env['sale.auto.workflow.configuration.ept'].search(
                [('shopify_instance_id', '=', instance.id)])
            unlink_for_financials_status = financials_status - self.shopify_financial_status_ids
            unlink_for_financials_status.unlink()
        return True
