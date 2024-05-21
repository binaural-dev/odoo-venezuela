from odoo import fields, models, api

import logging

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    megasoft_iot_id = fields.Many2one(related="pos_config_id.megasoft_iot_id", readonly=False)

    change_p2c = fields.Boolean(string="Change c2p method", related='company_id.change_p2c', readonly=False)
    verificate_p2c = fields.Boolean(string="Verificate p2c payment", related='company_id.verificate_p2c', readonly=False)
    pdv_option = fields.Boolean(string="Pdv options", related='company_id.pdv_option', readonly=False)
    url_megasoft = fields.Char(related='company_id.url_megasoft', readonly=False)
    port_megasoft = fields.Char(related='company_id.port_megasoft', readonly=False)
    pre_close_megasoft = fields.Boolean(related='pos_config_id.pre_close', readonly=False)

    @api.onchange('change_p2c')
    def _onchange_change_p2c(self):
        if not self.change_p2c:
            pos_payment_methods = self.env['pos.payment.method'].search([("is_change","=","True")])
            for method in pos_payment_methods:
                method.is_change = False

    @api.onchange('verificate_p2c')
    def _onchange_verificate_p2c(self):
        if not self.verificate_p2c:
            pos_payment_methods = self.env['pos.payment.method'].search([("is_payment_p2c","=","True")])
            for method in pos_payment_methods:
                method.is_payment_p2c = False

    @api.onchange('pdv_option')
    def _onchange_pdv_option(self):
        if not self.pdv_option:
            pos_payment_methods = self.env['pos.payment.method'].search([("is_payment_pdv","=","True")])
            for method in pos_payment_methods:
                method.is_payment_pdv = False

