# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)

import pdb
import requests
from odoo.addons.meli_oerp.models.versions import *
from odoo.addons.meli_oerp_accounting.models.versions import *


class SaleOrder(models.Model):

    _inherit = "sale.order"

    def action_invoice_create(self, grouped=False, final=False):

        _invoices = order_create_invoices( super(SaleOrder,self), grouped=grouped, final=final )

        #Colombia pragmatic
        for order in self:
            _logger.info(order)
            for inv in _invoices:
                _logger.info(inv)
                Invoice = self.env[acc_inv_model].browse([inv])
                if "fecha_entrega" in Invoice._fields:
                    _logger.info(Invoice)
                    if not Invoice.fecha_entrega:
                        Invoice.fecha_entrega =  order.commitment_date or order.expected_date
                        _logger.info(Invoice.fecha_entrega)
        return _invoices

    def meli_create_invoice( self, meli=None, config=None):
        _logger.info("meli_oerp_accounting meli_create_invoice started.")

        so = self
        #solo ordenes confirmadas o terminadas
    # TODO check meli_status_brief: if (self.meli_status_brief and "delivered" in self.meli_status_brief
        if so.state in ['sale','done']:
            #cond = so.invoice_status not in ['invoiced','no','upselling']
            received_amount = so.meli_amount_to_invoice( meli=meli, config=config )
            cond = True and abs( received_amount - so.amount_total ) < 1.0
            picking_dones = False
            picking_cancels = False
            picking_drafts = False
            if cond:
                if so.picking_ids:
                    for spick in so.picking_ids:
                        _logger.info(str(spick)+" state:"+str(spick.state))
                        if spick.state in ['done']:
                            picking_dones = True
                        elif spick.state in ['cancel']:
                            picking_cancels = True
                        else:
                            picking_drafts = True
                else:
                    picking_dones = False

                if picking_drafts:
                    #if a drafts then nothing is fully done
                    picking_dones = False

                _logger.info("Creating invoice... picking_dones:"+str(picking_dones))
                invoices = self.env[acc_inv_model].search( [(invoice_origin,'=',so.name)] )
                _logger.info("Creating invoice... invoices:"+str(invoices))

                invoice_confirmation = config.mercadolibre_order_confirmation_invoice
                invoice_confirmation_full = config.mercadolibre_order_confirmation_invoice_full

                #si no esta definido factura...
                invoice_creation = not invoice_confirmation or ( invoice_confirmation and not "manual" in invoice_confirmation)
                invoice_creation_full = not invoice_confirmation_full or ( invoice_confirmation_full and not "manual" in invoice_confirmation_full)

                invoice_create = invoice_creation

                journal_id_invoice = "mercadolibre_invoice_journal_id" in config._fields and config.mercadolibre_invoice_journal_id
                journal_id_invoice_full = "mercadolibre_invoice_journal_id_full" in config._fields and config.mercadolibre_invoice_journal_id_full

                if (so.meli_shipment_logistic_type and "fulfillment" in so.meli_shipment_logistic_type):
                    invoice_create = invoice_creation_full
                    invoice_confirmation = invoice_confirmation_full
                    journal_id_invoice = journal_id_invoice_full or journal_id_invoice
                    _logger.info("Creating invoice... invoice_creation_full:"+str(invoice_creation_full))

                if ("_delivered" in invoice_confirmation and not picking_dones):
                    invoice_create = False
                    _logger.info("Creating invoices not processed, shipment not complete: dones:"+str(picking_dones)+" drafts: "+str(picking_drafts)+" cancels:"+str(picking_cancels))


                _logger.info("Creating invoice... invoice_create:"+str(invoice_create)+" invoice_confirmation:"+str(invoice_confirmation))
                if not invoices and invoice_create:
                    _logger.info("Fixing order to invoice")
                    if so.invoice_status in ['invoiced']:
                        so.invoice_status = 'to invoice'
                    for oline in so.order_line:
                        oline.qty_invoiced = 0.0
                        oline.qty_to_invoice = oline.product_uom_qty
                        oline.invoice_status = 'to invoice'
                    _logger.info("Creating invoices")
                    result = so.action_invoice_create()
                    _logger.info("result:"+str(result))
                    invoices = self.env[acc_inv_model].search([(invoice_origin,'=',so.name)])
                    _logger.info("Created invoices: "+str(invoices))
                    for inv in invoices:
                        if inv.journal_id and journal_id_invoice and inv.journal_id.id!=journal_id_invoice.id:
                            inv.journal_id = journal_id_invoice
                    self.env.cr.commit()
                    _logger.info("Commited: "+str(invoices))

                if invoices and invoice_create:
                    if len(invoices)>1:
                        _logger.error("meli_create_invoice > more than one invoice document do NOTHING! Wait for manual resolution!")
                        return {}

                    for inv in invoices:
                        if inv.state in ['cancel']:
                            _logger.error("meli_create_invoice > at least one cancelled invoice, do NOTHING! Wait for manual resolution!")
                            return {}

                    for inv in invoices:
                        #fix journal_id
                        if inv.journal_id and journal_id_invoice and inv.journal_id.id!=journal_id_invoice.id:
                            if (inv.state not in posted_statuses):
                                inv.journal_id = journal_id_invoice

                        #try:
                        if inv.state in ['draft']:
                            draft_validation = not config.mercadolibre_order_confirmation_invoice or ( config.mercadolibre_order_confirmation_invoice and not "_draft" in config.mercadolibre_order_confirmation_invoice)
                            draft_validation_full = not config.mercadolibre_order_confirmation_invoice_full or ( config.mercadolibre_order_confirmation_invoice_full and not "_draft" in config.mercadolibre_order_confirmation_invoice_full)
                            draft_validate = draft_validation
                            if (so.meli_shipment_logistic_type and "fulfillment" in so.meli_shipment_logistic_type):
                                draft_validate = draft_validation_full
                            if draft_validate:
                                _logger.info("Validate invoice: "+str(inv.name))
                                inv.action_post()
                                _logger.info("Created invoices and validated!")

                        if inv.state in posted_statuses and config and config.mercadolibre_post_invoice:
                            _logger.info("Send to MercadoLibre: "+str(inv.name))
                            mo = so and so.meli_orders and so.meli_orders[0]
                            if mo:
                                mo.invoice_created = True
                                try:
                                    mo.orders_post_invoice( meli=meli, config=config )
                                except Exception as e:
                                    _logger.info("Post To ML Invoice Exception")
                                    _logger.error(e, exc_info=True)
                                    pass;

            else:
                _logger.error("meli_create_invoice > conditions not met.")
        #_logger.info("meli_oerp_accounting meli_create_invoice ended.")

    def confirm_ml( self, meli=None, config=None ):
        #_logger.info("meli_oerp_accounting confirm_ml: config:"+str(config and config.name))
        company = (config and 'company_id' in config._fields and config.company_id) or self.env.user.company_id
        config = config or company
        try:
            super(SaleOrder, self).confirm_ml(meli=meli,config=config)
            if (self.meli_orders):

                #process payments
                for meli_order in self.meli_orders:

                    for payment in meli_order.payments:
                        try:
                            if config.mercadolibre_process_payments_customer:

                                if 1==2 and payment.account_payment_id:
                                    fix = payment.account_payment_id and (payment.transaction_amount!=payment.total_paid_amount)
                                    fix = fix and (payment.account_payment_id.amount!=payment.transaction_amount)
                                    fix = fix and str(payment.account_payment_id.payment_date) == '2021-07-05'

                                    if (fix):
                                        _logger.info("payment fixing: "+str(payment.account_payment_id))
                                        #self.account_payment_id.cancel()
                                        payment.account_payment_id.action_draft()
                                        payment.account_payment_id.unlink()
                                        payment.account_payment_id = False

                                if not payment.account_payment_id:
                                    payment.create_payment( meli=meli, config=config )
                        except Exception as e:
                            _logger.info("Error creating customer payment")
                            _logger.info(e, exc_info=True)
                        try:
                            if config.mercadolibre_process_payments_supplier_fea and not payment.account_supplier_payment_id:
                                payment.create_supplier_payment( meli=meli, config=config )
                        except Exception as e:
                            _logger.info("Error creating supplier fee payment")
                            _logger.info(e, exc_info=True)
                        try:
                            if config.mercadolibre_process_payments_supplier_shipment and not payment.account_supplier_payment_shipment_id and (payment.order_id and payment.order_id.shipping_list_cost>0.0):
                                payment.create_supplier_payment_shipment( meli=meli, config=config )
                        except Exception as e:
                            _logger.info("Error creating supplier shipment payment")
                            _logger.info(e, exc_info=True)

                self.meli_reconcile()

        except Exception as e:
            _logger.info("Confirm Payment Exception")
            _logger.error(e, exc_info=True)
            pass
        #_logger.info("meli_oerp_accounting confirm_ml registering payments ended.")

        so = self
        if config and config.mercadolibre_order_confirmation and "_invoice" in config.mercadolibre_order_confirmation:
            mo = so and so.meli_orders and so.meli_orders[0]
            if not mo.invoice_posted:
                self.meli_create_invoice( meli=meli, config=config )

        invoices = self.env[acc_inv_model].search( [(invoice_origin,'=',so.name)] )
        if invoices:
            for inv in invoices:
                if inv.state in posted_statuses and config and config.mercadolibre_post_invoice:
                    _logger.info("Send to MercadoLibre: "+str(inv.name))
                    mo = so and so.meli_orders and so.meli_orders[0]
                    if mo:
                        mo.invoice_created = True
                        try:
                            if not mo.invoice_posted:
                                mo.orders_post_invoice( meli=meli, config=config )
                        except Exception as e:
                            _logger.info("Post To ML Invoice Exception")
                            _logger.error(e, exc_info=True)
                            pass;

        _logger.info("meli_oerp_accounting confirm_ml ended.")

    def meli_reconcile(self):

        return

        for meli_order in self.meli_orders:

            for payment in meli_order.payments:

                if payment.account_payment_id:
                    line_id = payment.account_payment_id.move_id.id
                    if (line_id):
                        lines = self.env['account.move.line'].browse(line_id)
                        lines += self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
                        lines.reconcile()

                if payment.mercadolibre_process_payments_supplier_shipment:
                    line_id = payment.mercadolibre_process_payments_supplier_shipment.move_id.id
                    if (line_id):
                        lines = self.env['account.move.line'].browse(line_id)
                        lines += self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and not line.reconciled)
                        lines.reconcile()

    def _compute_invoice_posted( self ):
        for ord in self:
            ord.invoice_posted = False
            #ord.invoice_type = 'unknown'
            if ord.meli_orders:
                ord.invoice_posted = ord.meli_orders[0].invoice_posted
                #ord.invoice_type = ord.meli_orders[0].invoice_type

    def search_invoice_posted(self, operator, value):
        _logger.info("search_invoice_posted")
        _logger.info(operator)
        _logger.info(value)
        if operator == '=':
            #name = self.env.context.get('name', False)
            #if name is not False:
            id_list = []
            _logger.info(self.env.context)
            #name = self.env.context.get('name', False)
            meli_orders = self.env['mercadolibre.orders'].search([('invoice_posted','=',value)], limit=10000)
            if (meli_orders):
                for mord in meli_orders:
                    if (mord.invoice_posted==value and mord.sale_order):
                        id_list.append(mord.sale_order.id)

            return [('id', 'in', id_list)]
        elif operator == '!=':
            id_list = []
            _logger.info(self.env.context)
            #name = self.env.context.get('name', False)
            meli_orders = self.env['mercadolibre.orders'].search([('invoice_posted','!=',value)], limit=10000)
            if (meli_orders):
                for mord in meli_orders:
                    if (mord.invoice_posted!=value and mord.sale_order):
                        id_list.append(mord.sale_order.id)

            return [('id', 'in', id_list)]
        else:
            _logger.error(
                'The field name is not searchable'
                ' with the operator: {}',format(operator)
            )


    invoice_posted = fields.Boolean( string="Factura enviada", compute=_compute_invoice_posted,search=search_invoice_posted )
