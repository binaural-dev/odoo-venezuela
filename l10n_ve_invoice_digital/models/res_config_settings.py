from odoo import models, fields, api
class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    username_tfhka = fields.Char(related="company_id.username_tfhka", string="Username", readonly=False)
    password_tfhka = fields.Char(related="company_id.password_tfhka", string="Password", readonly=False)
    url_tfhka = fields.Char(related="company_id.url_tfhka", string="URL", readonly=False)
    token_auth_tfhka = fields.Char(related="company_id.token_auth_tfhka", string="Token Auth", readonly=False)
    invoice_digital_tfhka = fields.Boolean(related="company_id.invoice_digital_tfhka", string="Invoice Digital", readonly=False)
    dispatch_guide_digital_tfhka = fields.Boolean(related="company_id.dispatch_guide_digital_tfhka", string="Dispatch Guide Digital", readonly=False)
    sequence_validation_tfhka = fields.Boolean(related="company_id.sequence_validation_tfhka", string="Sequence Validation", readonly=False)
    digitalization_with_payment_tfhka = fields.Boolean(related="company_id.digitalization_with_payment_tfhka", string="Digital invoicing with payment registration", readonly=False)
    # Expone el campo multi-moneda de la compañía en la vista de ajustes.
    multi_currency_invoice_tfhka = fields.Boolean(related="company_id.multi_currency_invoice_tfhka", string="Multi-currency digital invoicing", readonly=False)
    mix_invoicing_tfhka = fields.Boolean(related="company_id.mix_invoicing_tfhka", string="Allow Mixed Invoicing", readonly=False)
    mix_invoicing_type_tfhka = fields.Selection(
        related="company_id.mix_invoicing_type_tfhka",
        readonly=False
    )


    def action_generate_token_tfhka(self):
        self.company_id.generate_token_tfhka()

    @api.onchange('invoice_digital_tfhka')
    def _onchange_invoice_digital_tfhka(self):
        if not self.invoice_digital_tfhka:
            self.dispatch_guide_digital_tfhka = False

    def set_values(self):
        res = super().set_values()
        module_name = 'l10n_ve_dispatch_guide_digital'

        # Buscar el módulo en ir.module.module
        module = self.env['ir.module.module'].sudo().search([('name', '=', module_name)], limit=1)

        if self.dispatch_guide_digital_tfhka:
            # Instalar el módulo si no está instalado
            if module and module.state != 'installed':
                module.button_immediate_install()
        return res