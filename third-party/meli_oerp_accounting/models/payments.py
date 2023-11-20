from odoo import fields, models, api
from odoo.exceptions import ValidationError
from datetime import datetime
from odoo.addons.meli_oerp_accounting.models.versions import *
import logging
_logger = logging.getLogger(__name__)

class MeliPayment(models.Model):
    _inherit = 'mercadolibre.payments'

    def _get_config( self, config=None ):
        config = config or (self and self.order_id and self.order_id._get_config(config=config))
        #(self.order_id and self.order_id.company_id) or (self.order_id and self.order_id.sale_order and self.order_id.sale_order.company_id) or self.env.user.company_id
        return config

    def _get_ml_receiptbook( self, config=None, partner_type=None ):
        receiptbook_id = None
        if partner_type=='supplier':
            receiptbook_id = config and "mercadolibre_account_payment_supplier_receiptbook_id" in config._fields and config.mercadolibre_account_payment_supplier_receiptbook_id
        else:
            partner_type='customer'
            receiptbook_id = config and "mercadolibre_account_payment_receiptbook_id" in config._fields and config.mercadolibre_account_payment_receiptbook_id

        if not receiptbook_id and partner_type:
            receiptbook_id = self.env["account.payment.receiptbook"].search([("partner_type",'=',partner_type)], limit=1)
        return receiptbook_id

    def _get_ml_journal(self, config=None):
        config = config or (self and self.order_id and self.order_id._get_config(config=config))
        journal_id = config and config.mercadolibre_process_payments_journal
        if not journal_id:
            journal_id = self.env['account.journal'].search([('code','=','ML')])
        if not journal_id:
            journal_id = self.env['account.journal'].search([('code','=','MP')])
        return journal_id

    def _get_ml_partner(self, config=None):
        config = config or (self and self.order_id and self.order_id._get_config(config=config))
        partner_id = config and config.mercadolibre_process_payments_res_partner
        if not partner_id:
            partner_id = self.env['res.partner'].search([('ref','=','MELI')])
        if not partner_id:
            partner_id = self.env['res.partner'].search([('name','=','MercadoLibre')])
        return partner_id

    def _get_ml_customer_partner(self):
        sale_order = self._get_ml_customer_order()
        return (sale_order and sale_order.partner_id)

    def _get_ml_customer_order(self):
        mlorder = self.order_id
        mlshipment = mlorder.shipment
        return (mlorder and mlorder.sale_order) or (mlshipment and mlshipment.sale_order)

    def meli_amount_to_invoice(self, config=None, meli=None):
        total_config = (config and "mercadolibre_order_total_config" in config._fields) and config.mercadolibre_order_total_config

        if not config or not total_config:
            return self.transaction_amount;

        if total_config in ['manual']:
            #resolve always as conflict
            return 0

        if total_config in ['manual_conflict']:
            if abs(self.transaction_amount - self.total_paid_amount)<1.0:
                return self.total_paid_amount
            else:
                #conflict if do not match
                return 0

        if total_config in ['paid_amount']:
            #return self.total_paid_amount
            so = self._get_ml_customer_order()
            #return (so and so.meli_paid_amount) or (self.transaction_amount)
            #return (self.total_paid_amount)
            return self.transaction_amount

        #without shipment amount
        if total_config in ['total_amount']:
            return self.transaction_amount

        return 0

    def create_payment( self, meli=None, config=None ):
        self.ensure_one()

        if not config:
            config = self._get_config(config=config)
            if not config:
                return None

        if self.account_payment_id:
            raise ValidationError('Ya esta creado el pago')
        if self.status != 'approved':
            return None
        journal_id = self._get_ml_journal(config=config)
        payment_method_id = self.env['account.payment.method'].search([('code','=','electronic'),('payment_type','=','inbound')], limit=1)
        if not journal_id or not payment_method_id:
            raise ValidationError('Debe configurar el diario/metodo de pago')
        partner_id = self._get_ml_customer_partner()
        currency_id = self.env['res.currency'].search([('name','=',self.currency_id)])
        if not currency_id:
            raise ValidationError('No se puede encontrar la moneda del pago')

        communication = self.payment_id
        if self._get_ml_customer_order():
            communication = ""+str(self._get_ml_customer_order().name)+" OP "+str(self.payment_id)+str(" TOT")

        #total_amount = self.transaction_amount
        #TODO: using meli_amount_to_invoice to foreach item/order not from total
        #total_amount = self._get_ml_customer_order().meli_amount_to_invoice( meli=meli, config=config )
        total_amount = self.meli_amount_to_invoice( meli=meli, config=config )
        #self.total_paid_amount

        vals_payment = {
                'partner_id': partner_id.id,
                'payment_type': 'inbound',
                'payment_method_id': payment_method_id.id,
                'journal_id': journal_id.id,
                'meli_payment_id': self.id,
                'currency_id': currency_id.id,
                'partner_type': 'customer',
                'amount': total_amount,
                }
        if "l10n_mx_edi.payment.method" in self.env:
            if "mercadolibre_customer_payment_method_id" in config._fields and config.mercadolibre_customer_payment_method_id:
                vals_payment["mercadolibre_customer_payment_method_id"] = config.mercadolibre_customer_payment_method_id.id

        vals_payment[acc_pay_ref] = communication
        acct_payment_id = None
        if 'account.payment.group' in self.env:
            vals_group = {
                'company_id': self.order_id and self.order_id.company_id and self.order_id.company_id.id,
                'receiptbook_id': (self._get_ml_receiptbook(config=config) and self._get_ml_receiptbook(config=config).id),
                'partner_id': partner_id.id,
                #'journal_id': journal_id.id,
                'currency_id': currency_id.id,
                'partner_type': 'customer',
                'payment_ids': [(0,0,vals_payment)]
            }
            if "payment_on_account_amount" in self.env['account.payment.group']._fields:
                vals_group["payment_on_account_amount"] = total_amount
            if acc_pay_group_ref in self.env['account.payment.group']._fields:
                vals_group[acc_pay_group_ref] = communication
            _logger.info("create_payment group: "+str(vals_group))
            acct_payment_group_id = self.env['account.payment.group'].create( vals_group )
            if acct_payment_group_id:
                acct_payment_id = acct_payment_group_id.payment_ids and acct_payment_group_id.payment_ids[0].id
                self.account_payment_id = acct_payment_id
                self.account_payment_group_id = acct_payment_group_id.id
                #if self.channel_binding_id and ("account_payment_receipt_validation" in self.channel_binding_id._fields) and self.channel_binding_id.account_payment_receipt_validation:
                #    if self.channel_binding_id.account_payment_receipt_validation in ['validate']:
                payment_group_post( acct_payment_group_id )

        else:
            _logger.info("create_payment default: "+str(vals_payment))
            acct_payment_id = self.env['account.payment'].create(vals_payment)
            self.account_payment_id = (acct_payment_id and acct_payment_id.id)
            #if self.channel_binding_id and ("account_payment_receipt_validation" in self.channel_binding_id._fields) and self.channel_binding_id.account_payment_receipt_validation:
            #    if self.channel_binding_id.account_payment_receipt_validation in ['validate']:
            payment_post( acct_payment_id )

    def create_supplier_payment(self, meli=None, config=None ):
        self.ensure_one()

        if not config:
            config = self._get_config(config=config)
            if not config:
                return None

        if self.status != 'approved':
            return None
        if self.account_supplier_payment_id:
            raise ValidationError('Ya esta creado el pago')
        journal_id = self._get_ml_journal(config=config)
        payment_method_id = self.env['account.payment.method'].search([('code','=','outbound_online'),('payment_type','=','outbound')], limit=1)
        if not journal_id or not payment_method_id:
            raise ValidationError('Debe configurar el diario/metodo de pago')
        partner_id = self._get_ml_partner()
        if not partner_id:
            raise ValidationError('No esta dado de alta el proveedor MercadoLibre')
        currency_id = self.env['res.currency'].search([('name','=',self.currency_id)])
        if not currency_id:
            raise ValidationError('No se puede encontrar la moneda del pago')

        communication = self.payment_id
        if self._get_ml_customer_order():
            communication = ""+str(self._get_ml_customer_order().name)+" OP "+str(self.payment_id)+str(" FEE")

        vals_payment = {
                'partner_id': partner_id.id,
                'payment_type': 'outbound',
                'payment_method_id': payment_method_id.id,
                'journal_id': journal_id.id,
                'meli_payment_id': self.id,
                'currency_id': currency_id.id,
                'partner_type': 'supplier',
                'amount': self.fee_amount,
                }

        if "l10n_mx_edi.payment.method" in self.env:
            if "mercadolibre_provider_payment_method_id" in config._fields and config.mercadolibre_provider_payment_method_id:
                vals_payment["mercadolibre_provider_payment_method_id"] = config.mercadolibre_provider_payment_method_id.id

        vals_payment[acc_pay_ref] = communication
        acct_payment_id = None
        if 'account.payment.group' in self.env:
            vals_group = {
                'company_id': self.order_id and self.order_id.company_id and self.order_id.company_id.id,
                'receiptbook_id': (self._get_ml_receiptbook(config=config,partner_type='supplier') and self._get_ml_receiptbook(config=config,partner_type='supplier').id),
                'partner_id': partner_id.id,
                #'journal_id': journal_id.id,
                'currency_id': currency_id.id,
                'partner_type': 'supplier',
                'payment_ids': [(0,0,vals_payment)]
            }
            if "payment_on_account_amount" in self.env['account.payment.group']._fields:
                vals_group["payment_on_account_amount"] = self.fee_amount
            if acc_pay_group_ref in self.env['account.payment.group']._fields:
                vals_group[acc_pay_group_ref] = communication
            _logger.info("create_supplier_payment group: "+str(vals_group))
            acct_payment_group_id = self.env['account.payment.group'].create( vals_group )
            if acct_payment_group_id:
                acct_payment_id = acct_payment_group_id.payment_ids and acct_payment_group_id.payment_ids[0].id
                self.account_supplier_payment_id = acct_payment_id
                self.account_supplier_group_payment_id = acct_payment_group_id.id
                #if self.channel_binding_id and ("account_payment_receipt_validation" in self.channel_binding_id._fields) and self.channel_binding_id.account_payment_receipt_validation:
                #    if self.channel_binding_id.account_payment_receipt_validation in ['validate']:
                payment_group_post( acct_payment_group_id )

        else:
            _logger.info("create_supplier_payment default: "+str(vals_payment))
            acct_payment_id = self.env['account.payment'].create(vals_payment)
            self.account_supplier_payment_id = (acct_payment_id and acct_payment_id.id)
            #if self.channel_binding_id and ("account_payment_receipt_validation" in self.channel_binding_id._fields) and self.channel_binding_id.account_payment_receipt_validation:
            #    if self.channel_binding_id.account_payment_receipt_validation in ['validate']:
            payment_post( acct_payment_id )

    def create_supplier_payment_shipment(self, meli=None, config=None ):
        self.ensure_one()

        if not config:
            config = self._get_config(config=config)
            if not config:
                return None

        if self.status != 'approved':
            return None
        if self.account_supplier_payment_shipment_id:
            raise ValidationError('Ya esta creado el pago')
        journal_id = self._get_ml_journal(config=config)

        payment_method_out_id = self.env['account.payment.method'].search([('code','=','outbound_online'),('payment_type','=','outbound')], limit=1)
        if not journal_id or not payment_method_out_id:
            raise ValidationError('Debe configurar el diario/metodo de pago OUT')

        payment_method_in_id = self.env['account.payment.method'].search([('code','=','electronic'),('payment_type','=','inbound')], limit=1)
        if not journal_id or not payment_method_in_id:
            raise ValidationError('Debe configurar el diario/metodo de pago IN')

        partner_id = self._get_ml_partner()
        if not partner_id:
            raise ValidationError('No esta dado de alta el proveedor MercadoLibre')

        customer_id = self._get_ml_customer_partner()
        if not customer_id:
            raise ValidationError('No esta dado de alta el cliente')

        currency_id = self.env['res.currency'].search([('name','=',self.currency_id)])
        if not currency_id:
            raise ValidationError('No se puede encontrar la moneda del pago')
        if (not self.order_id or not self.order_id.shipping_list_cost>0.0):
            raise ValidationError('No hay datos de costo de envio')

        communication = self.payment_id
        so = self._get_ml_customer_order()
        mlorder = self.order_id
        mlshipment = mlorder and mlorder.shipment
        if so:
            communication = ""+str(self._get_ml_customer_order().name)+" OP "+str(self.payment_id)+str(" SHP")


        shipping_amount_out = self.shipping_amount
        if not shipping_amount_out:
            return False
        vals_payment = {
                'partner_id': customer_id.id,
                #'payment_type': 'outbound',
                'payment_type': 'inbound',
                'payment_method_id': payment_method_in_id.id,
                'journal_id': journal_id.id,
                'meli_payment_id': self.id,
                'currency_id': currency_id.id,
                'partner_type': 'customer',
                #'partner_type': 'supplier',
                #'amount': self.order_id.shipping_list_cost,
                'amount': shipping_amount_out,
                }

        vals_payment[acc_pay_ref] = communication
        acct_payment_id = None
        if 'account.payment.group' in self.env:
            vals_group = {
                'company_id': self.order_id and self.order_id.company_id and self.order_id.company_id.id,
                'receiptbook_id': (self._get_ml_receiptbook(config=config) and self._get_ml_receiptbook(config=config).id),
                'partner_id': customer_id.id,
                #'journal_id': journal_id.id,
                'currency_id': currency_id.id,
                #'partner_type': 'supplier',
                'partner_type': 'customer',
                'payment_ids': [(0,0,vals_payment)]
            }
            if "payment_on_account_amount" in self.env['account.payment.group']._fields:
                vals_group["payment_on_account_amount"] = self.order_id.shipping_list_cost
            if acc_pay_group_ref in self.env['account.payment.group']._fields:
                vals_group[acc_pay_group_ref] = communication
            _logger.info("create_supplier_payment_shipment group: "+str(vals_group))
            acct_payment_group_id = self.env['account.payment.group'].create( vals_group )
            if acct_payment_group_id:
                acct_payment_id = acct_payment_group_id.payment_ids and acct_payment_group_id.payment_ids[0].id
                self.account_supplier_payment_shipment_id = acct_payment_id
                self.account_supplier_group_payment_shipment_id = acct_payment_group_id.id
                #if self.channel_binding_id and ("account_payment_receipt_validation" in self.channel_binding_id._fields) and self.channel_binding_id.account_payment_receipt_validation:
                #    if self.channel_binding_id.account_payment_receipt_validation in ['validate']:
                payment_group_post( acct_payment_group_id )

        else:
            _logger.info("create_supplier_payment_shipment default: "+str(vals_payment))
            acct_payment_id = self.env['account.payment'].create(vals_payment)
            self.account_supplier_payment_shipment_id = (acct_payment_id and acct_payment_id.id)
            #if self.channel_binding_id and ("account_payment_receipt_validation" in self.channel_binding_id._fields) and self.channel_binding_id.account_payment_receipt_validation:
            #    if self.channel_binding_id.account_payment_receipt_validation in ['validate']:
            payment_post( acct_payment_id )



    account_payment_id = fields.Many2one('account.payment',string='Pago')
    account_supplier_payment_id = fields.Many2one('account.payment',string='Pago a Proveedor')
    account_supplier_payment_shipment_id = fields.Many2one('account.payment',string='Pago Envio a Proveedor')

    #account_payment_group_id = fields.Many2one('account.payment.group',string='Pago agrupado')
    #account_supplier_group_payment_id = fields.Many2one('account.payment.group',string='Pago agrupado a Proveedor')
    #account_supplier_group_payment_shipment_id = fields.Many2one('account.payment.group',string='Pago agrupado Envio a Proveedor')


class AccountPayment(models.Model):

    _inherit = 'account.payment'

    meli_payment_id = fields.Many2one('mercadolibre.payments',string='Pago de MP')

class AccountPaymentMethod(models.Model):
    _inherit = 'account.payment.method'

    @api.model
    def _get_payment_method_information(self):
        res = super()._get_payment_method_information()
        res['outbound_online'] = {'mode': 'multi', 'domain': [('type', '=', 'bank')]}
        res['electronic'] = {'mode': 'multi', 'domain': [('type', '=', 'bank')]}
        return res
