# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api


class SaleWorkflowProcess(models.Model):
    _name = "sale.workflow.process.ept"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "sale workflow process"

    @api.model
    def _default_journal(self):
        """
        It will return sales journal of company passed in context or user's company.
        Migration done by Haresh Mori on September 2021
        """
        account_journal_obj = self.env['account.journal']
        company_id = self._context.get('company_id', self.env.company.id)
        domain = [('type', '=', "sale"), ('company_id', '=', company_id)]
        return account_journal_obj.search(domain, limit=1)

    name = fields.Char(size=64)
    validate_order = fields.Boolean("Confirm Quotation", default=False,
                                    help="If it's checked, Order will be Validated.", tracking=True)
    create_invoice = fields.Boolean('Create & Validate Invoice', default=False,
                                    help="If it's checked, Invoice for Order will be Created and Posted.", tracking=True)
    register_payment = fields.Boolean(default=False, help="If it's checked, Payment will be registered for Invoice.", tracking=True)
    invoice_date_is_order_date = fields.Boolean('Force Accounting Date',
                                                help="if it is checked then, the account journal entry will be "
                                                     "generated based on Order date and if unchecked then, "
                                                     "the account journal entry will be generated based on Invoice Date", tracking=True)
    journal_id = fields.Many2one('account.journal', string='Payment Journal', domain=[('type', 'in', ['cash', 'bank'])], tracking=True)
    sale_journal_id = fields.Many2one('account.journal', string='Sales Journal', default=_default_journal,
                                      domain=[('type', '=', 'sale')], tracking=True)
    picking_policy = fields.Selection([('direct', 'Deliver each product when available'),
                                       ('one', 'Deliver all products at once')], string='Shipping Policy',
                                      default="one", tracking=True)
    inbound_payment_method_id = fields.Many2one('account.payment.method', string="Debit Method",
                                                domain=[('payment_type', '=', 'inbound')],
                                                help="Means of payment for collecting money. Odoo modules offer various"
                                                     "payments handling facilities, but you can always use the 'Manual'"
                                                     "payment method in order to manage payments outside of the"
                                                     "software.", tracking=True)

    @api.onchange("validate_order")
    def onchange_validate_order(self):
        """
        Onchange of Confirm Quotation field.
        If 'Confirm Quotation' is unchecked, the 'Create & Validate Invoice' will be unchecked too.
        """
        for record in self:
            if not record.validate_order:
                record.create_invoice = False

    @api.onchange("create_invoice")
    def onchange_create_invoice(self):
        """
       Onchange of Create & Validate Invoice field.
       If 'Create & Validate Invoice' is unchecked, the 'Register Payment' and 'Force Invoice Date' will be unchecked
       too.
       """
        for record in self:
            if not record.create_invoice:
                record.register_payment = False

    @api.model
    def auto_workflow_process_ept(self, auto_workflow_process_id=False, order_ids=[]):
        """
        This method will find draft sale orders which are not having invoices yet, confirmed it and done the payment
        according to the auto invoice workflow configured in sale order.
        :param auto_workflow_process_id: auto workflow process id
        :param order_ids: ids of sale orders
        Migration done by Haresh Mori on September 2021
        """
        sale_order_obj = self.env['sale.order']
        workflow_process_obj = self.env['sale.workflow.process.ept']
        if not auto_workflow_process_id:
            work_flow_process_records = workflow_process_obj.search([])
        else:
            work_flow_process_records = workflow_process_obj.browse(auto_workflow_process_id)

        if not order_ids:
            orders = sale_order_obj.search([('auto_workflow_process_id', 'in', work_flow_process_records.ids),
                                            ('state', 'not in', ('done', 'cancel', 'sale')),
                                            ('invoice_status', '!=', 'invoiced')])
        else:
            orders = sale_order_obj.search([('auto_workflow_process_id', 'in', work_flow_process_records.ids),
                                            ('id', 'in', order_ids)])
        orders.process_orders_and_invoices_ept()

        return True

    def shipped_order_workflow_ept(self, orders):
        """
        This method is for processing the shipped orders.
        """
        self.ensure_one()
        stock_location_obj = self.env["stock.location"]
        product_product_obj = self.env["product.product"]

        mrp_module = product_product_obj.search_installed_module_ept('mrp')
        customer_location = stock_location_obj.search([("usage", "=", "customer")], limit=1)

        shipped_orders = orders.filtered(lambda x: x.order_line)

        for order in shipped_orders:
            order.state = 'sale'
            order.auto_shipped_order_ept(customer_location, mrp_module)

        shipped_orders.validate_and_paid_invoices_ept(self)
        return True
