from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveIgtf(models.Model):
    _inherit = "account.move"

    def default_is_igtf(self):
        return self.env.company.module_binaural_base_igtf or False

    default_is_igtf_config = fields.Boolean(default=default_is_igtf)

    def js_assign_outstanding_line(self, line_id):
        res = super(AccountMoveIgtf, self).js_assign_outstanding_line(line_id)
        _logger.warning("js_assign_outstanding_line")
        _logger.warning(res)
        _logger.warning(self.bi_igtf)
        return res

    def js_remove_outstanding_partial(self, partial_id):
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        # move = self.env['account.move'].search([('id', '=', self.id)])
        _logger.warning("MOVEEEE")
        _logger.warning(self.bi_igtf)
        # self.bi_igtf = self.bi_igtf - partial.amount
        res = super().js_remove_outstanding_partial(partial_id)


        return res
    