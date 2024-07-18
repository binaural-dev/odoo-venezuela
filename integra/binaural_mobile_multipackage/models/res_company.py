import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    use_multiple_packaging = fields.Boolean(
        string="Multiple Packaging",
        compute="_compute_use_multiple_packaging",
        readonly=False,
        store=True
    )

    @api.depends('group_stock_packaging')
    def _compute_use_multiple_packaging(self):
        for record in self:
            record.use_multiple_packaging = record.group_stock_packaging and record.use_multiple_packaging

