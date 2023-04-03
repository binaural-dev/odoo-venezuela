from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveIgtf(models.Model):
    _inherit = "account.move"

    def default_is_igtf(self):
        return self.env.company.is_igtf or False

    default_is_igtf_config = fields.Boolean(default=default_is_igtf)

    def get_fields(self):
        for move in self:
           _logger.warning("get_fields")
           _logger.warning(move.read())


    def js_assign_outstanding_line(self, line_id):
        res = super(AccountMoveIgtf, self).js_assign_outstanding_line(line_id)
        _logger.warning("js_assign_outstanding_line")
        _logger.warning(res)
        _logger.warning(self.bi_igtf)
        return res

    def js_remove_outstanding_partial(self, partial_id):
        self._compute_tax_totals()
        _logger.warning("Tax totals: %s" % self.tax_totals)
        partial = self.env['account.partial.reconcile'].browse(partial_id)
        self.get_fields()
        res = super().js_remove_outstanding_partial(partial_id)


        return res
    