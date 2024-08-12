# Copyright (C) Softhealer Technologies.

from odoo import models, fields,api,_
from odoo.exceptions import UserError, ValidationError


class AfterPages(models.Model):
    _name = 'default.after.pages'
    _description = 'Stores the values of the Default After Pages'

    name = fields.Char("Title", required=True)
    after_datas = fields.Binary("Page Details (PDF only)")
    after_datas_filename = fields.Char()

    @api.constrains('after_datas')
    def _constrains_reconcile(self):
        for rec in self:
            if type(rec.after_datas_filename) != bool:
                if not str(rec.after_datas_filename).endswith('.pdf'):
                    raise UserError(_('Please note that only PDF files are accepted. Kindly select a PDF file to proceed.'))
                return True
            raise UserError(_('Please note that only PDF files are accepted. Kindly select a PDF file to proceed.'))