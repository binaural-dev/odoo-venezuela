# Copyright (C) Softhealer Technologies.
# Part of Softhealer Technologies.

from odoo import models, fields, api

class PosOrderInherit (models.Model):
    _inherit = 'pos.order'

    sh_pos_order_analytic_account = fields.Many2one(
        'account.analytic.account', string="Analytic Account")


    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        # pass analytic accuount data in pos order
        if res:
            if ui_order.get('sh_pos_order_analytic_account'):
                res.update({'sh_pos_order_analytic_account': ui_order.get(
                    'sh_pos_order_analytic_account')})
          
        return res

    def _payment_fields(self, order, ui_paymentline):
        # pass analyic account data  in payment lines.
        res = super()._payment_fields(order, ui_paymentline)
        res['sh_analytic_account'] = ui_paymentline.get('sh_analytic_account')
        return res

    # def _prepare_invoice_line(self, order_line):
    #     res = super()._prepare_invoice_line(order_line)
    #     if self.sh_pos_order_analytic_account:
    #         res['analytic_account_id'] = self.sh_pos_order_analytic_account
        
    #     return res


class PosOrderlineInherit(models.Model):
    _inherit = 'pos.order.line'

    sh_pos_order_analytic_account = fields.Many2one(
        'account.analytic.account', string="Analytic Account")
