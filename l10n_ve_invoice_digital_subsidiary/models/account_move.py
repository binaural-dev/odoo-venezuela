from odoo import models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    def get_document_identification(self, document_type, document_number, series):
        result = super().get_document_identification(document_type, document_number, series)
        _logger.info("Sucursales con facturacion digital")
        for record in self:
            if self.company_id.subsidiary:
                if record.account_analytic_id and record.account_analytic_id.code:
                    result['sucursal'] = record.account_analytic_id.code
                else:
                    raise UserError(_("The selected subsidiary does not contain a reference"))
        return result

