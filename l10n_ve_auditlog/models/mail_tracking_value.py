from odoo import models, fields, api, _


class MailTrackingValue(models.Model):
    _inherit = "mail.tracking.value"

    model = fields.Char(compute="_compute_model", string="Model", store=True)

    author_id = fields.Many2one(
        "res.partner", compute="_compute_author", string="Author", store=True
    )

    @api.depends("mail_message_id")
    def _compute_model(self):
        for record in self:
            record.model = record.mail_message_id.model

    @api.depends("author_id")
    def _compute_author(self):
        for record in self:
            record.author_id = record.mail_message_id.author_id
