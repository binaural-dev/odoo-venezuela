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

class ResCompany(models.Model):
    _name = "res.company"
    _inherit = "res.company"

    mercadolibre_process_payments_customer = fields.Boolean(string="Process payments from Customer")
    mercadolibre_process_payments_supplier_fea = fields.Boolean(string="Process payments fea to Supplier ML")
    mercadolibre_process_payments_supplier_shipment = fields.Boolean(string="Process payments shipping list cost to Supplier ML")

    mercadolibre_process_payments_journal = fields.Many2one("account.journal",string="Account Journal for MercadoLibre")
    mercadolibre_process_payments_res_partner = fields.Many2one("res.partner",string="MercadoLibre Partner")

    mercadolibre_process_payments_journal_shp = fields.Many2one("account.journal",string="Account Journal for MercadoLibre (SHP)")
    mercadolibre_process_payments_res_partner_shp = fields.Many2one("res.partner",string="MercadoLibre Partner (SHP)")

    mercadolibre_order_confirmation = fields.Selection(selection_add=[("paid_confirm_with_invoice", "Pagado>Facturado"),
                                                ("paid_delivered_with_invoice", "Pagado>Facturado y Entregado")],
                                                ondelete={"paid_confirm_with_invoice": "set default"},
                                                string='Acción al recibir un pedido',
                                                help='Acción al confirmar una orden o pedido de venta')

    mercadolibre_order_confirmation_invoice = fields.Selection([ ("manual", "No facturar"),
                                                ("paid_confirm_invoice", "Pagado > Facturar"),
                                                ("paid_confirm_delivered_invoice", "Entregado > Facturar"),

                                                ("paid_confirm_invoice_draft", "Pagado > Factura borrador"),
                                                ("paid_confirm_delivered_invoice_draft", "Entregado > Factura borrador"),
                                                #("paid_confirm_invoice_deliver", "Pagado > Facturar > Entregar")
                                                ],
                                                string='Acción sobre la factura al confirmar un pedido',
                                                help='Acción sobre la factura al confirmar una orden o pedido de venta')

    mercadolibre_order_confirmation_invoice_full = fields.Selection([ ("manual", "No facturar"),
                                                ("paid_confirm_invoice", "Pagado > Facturar"),
                                                ("paid_confirm_delivered_invoice", "Entregado > Facturar"),

                                                ("paid_confirm_invoice_draft", "Pagado > Factura borrador"),
                                                ("paid_confirm_delivered_invoice_draft", "Entregado > Factura borrador"),
                                                #("paid_confirm_invoice_deliver", "Pagado > Facturar > Entregar")
                                                ],
                                                string='(FULL) Acción sobre la factura al confirmar un pedido',
                                                help='(FULL) Acción sobre la factura al confirmar una orden o pedido de venta')

    mercadolibre_post_invoice = fields.Boolean(string="Post Invoice Automatic",help="Try to post invoice, when order is revisited or refreshed.")
    mercadolibre_post_invoice_dont_send = fields.Boolean(string="Dont really send, just prepare to post invoice.")

    mercadolibre_set_fully_invoice = fields.Boolean( string="Set Fully Invoice", help="Marcar como completamente facturado la orden correspondiente (incluido linea de envio)" )

    mercadolibre_invoice_journal_id = fields.Many2one( "account.journal", string="Diario Facturacion" )
    mercadolibre_invoice_journal_id_full = fields.Many2one( "account.journal", string="Diario Facturacion Full" )

    #mercadolibre_account_payment_receiptbook_id = fields.Many2one( "account.payment.receiptbook", string="Recibos")
    #mercadolibre_account_payment_supplier_receiptbook_id = fields.Many2one( "account.payment.receiptbook", string="Ordenes de pago")
    #mercadolibre_customer_payment_method_id = fields.Many2one( "l10n_mx_edi.payment.method", string="Customer Payment Method")
    #mercadolibre_provider_payment_method_id = fields.Many2one( "l10n_mx_edi.payment.method", string="Provider Payment Method")

    def hi(self):
        return True
