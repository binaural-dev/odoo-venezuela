from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)

class AccountPaymentRegisterIgtf(models.TransientModel):
    _inherit = "account.payment.register"

    def action_create_payments(self):
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            self = self.sudo()
            _logger.warning("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
            res =  super().action_create_payments()
            _logger.warning("EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE")
            return res
        return super().action_create_payments()
    
    def _init_payments(self, to_process, edit_mode=False):
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            self = self.sudo()
            _logger.warning("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            res =  super()._init_payments(to_process, edit_mode)
            _logger.warning("despues de init payment")
            return res
        return super()._init_payments(to_process, edit_mode)
    
    def _post_payments(self, to_process, edit_mode=False):
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            self = self.sudo()
            _logger.warning("333333333333333333333333333333333333333333333333333333333333333")
            res =  super()._post_payments(to_process, edit_mode)
            _logger.warning("despues de pos payment")
            return res
        return super()._post_payments(to_process, edit_mode)
    
    def _reconcile_payments(self, to_process, edit_mode=False):
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            self = self.sudo()
            _logger.warning("___________________________________________________________")
            res =  super()._reconcile_payments(to_process, edit_mode)
            _logger.warning("despues de reconcile_payments")
            return res
        return super()._reconcile_payments(to_process, edit_mode)
    
    def _create_payments(self):
        if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
            self = self.sudo()
            _logger.warning("__________________----------------------_________________________________________")
            res =  super()._create_payments()
            _logger.warning("despues de _create_payments")
            return res
        return super()._create_payments()


    # def action_create_payments(self):
    #     payments = self._create_payments()

    #     if self._context.get('dont_redirect_to_payments'):
    #         return True

    #     action = {
    #         'name': _('Payments'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'account.payment',
    #         'context': {'create': False},
    #     }
    #     if len(payments) == 1:
    #         action.update({
    #             'view_mode': 'form',
    #             'res_id': payments.id,
    #         })
    #     else:
    #         action.update({
    #             'view_mode': 'tree,form',
    #             'domain': [('id', 'in', payments.ids)],
    #         })
    #     return action
    
    # def _init_payments(self, to_process, edit_mode=False):
    #     if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
    #         self = self.sudo()
    #         _logger.warning("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    #         res =  super()._init_payments(to_process, edit_mode)
    #         _logger.warning("despues de init payment")
    #         return res
    #     return super()._init_payments(to_process, edit_mode)
    
    # def _post_payments(self, to_process, edit_mode=False):
    #     if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
    #         self = self.sudo()
    #         _logger.warning("333333333333333333333333333333333333333333333333333333333333333")
    #         res =  super()._post_payments(to_process, edit_mode)
    #         _logger.warning("despues de pos payment")
    #         return res
    #     return super()._post_payments(to_process, edit_mode)
    
    # def _reconcile_payments(self, to_process, edit_mode=False):
    #     if self.env.user.has_group("binaural_fiscal_inspector.group_fiscal_inspectorate_editable"):
    #         self = self.sudo()
    #         _logger.warning("___________________________________________________________")
    #         res =  super()._reconcile_payments(to_process, edit_mode)
    #         _logger.warning("despues de reconcile_payments")
    #         return res
    #     return super()._reconcile_payments(to_process, edit_mode)
    