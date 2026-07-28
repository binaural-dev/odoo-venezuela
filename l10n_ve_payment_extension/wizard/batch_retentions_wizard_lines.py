
from odoo import _, api, models, fields
from odoo.fields import Domain

import logging

_logger = logging.getLogger(__name__)


class BatchRetentionsWizardLines(models.TransientModel):
    _name = "batch.retentions.wizard.lines"

    wizard_id = fields.Many2one('batch.retentions.wizard',ondelete='cascade')
    
    post_retention = fields.Boolean(string="Post", default=True)
    
    move_id = fields.Many2one('account.move', string="Invoice",store=True)
    partner_id = fields.Many2one(
        related="move_id.partner_id" , string="partner"
    )
    is_isrl_retention_available = fields.Boolean(
        related="move_id.is_isrl_retention_available", string="Available"
    )
    count_islr_retention = fields.Integer(related="move_id.count_islr_retention", string="Retentions")
    has_emited_islr_retention = fields.Boolean(related="move_id.has_emited_islr_retention")
    state = fields.Selection(related="move_id.state", string="Invoice Status")
    payment_state = fields.Selection(related="move_id.payment_state", string="Invoice Payment status")
    