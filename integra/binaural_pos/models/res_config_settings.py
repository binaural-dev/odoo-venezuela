from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    module_binaural_pos_igtf = fields.Boolean(
        related="company_id.module_binaural_pos_igtf", readonly=False
    )
    module_binaural_base_igtf = fields.Boolean(
        related="company_id.module_binaural_base_igtf", readonly=False
    )
    module_binaural_pos_mf = fields.Boolean(
        related="company_id.module_binaural_pos_mf", readonly=False
    )
    pos_tax_inside = fields.Boolean(related="company_id.pos_tax_inside", readonly=False)
    receipt_journal_id = fields.Many2one(
        "account.journal", related="pos_config_id.receipt_journal_id", readonly=False
    )
    always_invoice = fields.Boolean(related="pos_config_id.always_invoice", readonly=False)

    # @api.onchange("module_binaural_pos_igtf")
    # def _onchange_module_binaural_pos_igtf(self):
    #     if self.module_binaural_pos_igtf and self.company_id.taxpayer_type == "ordinary":
    #         raise ValidationError(
    #             _("You cannot turn on the igtf in pos if the company is an ordinary taxpayer")
    #         )
