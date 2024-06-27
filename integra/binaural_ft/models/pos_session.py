from odoo import fields, models
from odoo.osv.expression import OR

import logging
_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = "pos.session"


    def load_pos_data(self):
        res = super().load_pos_data()
        reports = self.env["ir.actions.report"].search([("report_name", '=', "binaural_ft.template_mf")])
        mf = {} 
        _logger.info(reports)
        for device in self.env["iot.device"].search([('report_ids', 'in', reports.ids)]):
            mf[str(device.id)] = device.report_ids.filtered(lambda x: x.report_name ==  "binaural_ft.template_mf").id
            _logger.info(device)
        res["reports_mf"] = mf
        _logger.info(mf)
        _logger.info("xxxxxxxxxxxx")
        return res
