# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

_logger = logging.getLogger(__name__)


class WizardConfirmAccountMove(models.TransientModel):

    _name = 'wizard.confirm.account.move'
    _description = 'Confirm Wizard'

    account_move_id = fields.Many2one('account.move')
    journal_id = fields.Many2one('account.journal')

    def action_post(self):

        if self.account_move_id:
            self.account_move_id.with_context(do_original_method=True).action_post()


