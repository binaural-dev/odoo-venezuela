import logging
from lxml import etree

from odoo.models import TransientModel
from odoo.fields import (
    Char,
    Many2many
)
from odoo import api

_logger = logging.getLogger(__name__)


class InvoiceCommissionSummaryWizard(TransientModel):
    _name = 'invoice.commission.summary.wizard'
    _description = 'Invoice Commission Summary Wizard'

    name = Char(
        "Name",
        required=True
    )
    
    invoice_line_ids = Many2many(
        'account.move.line',
        'commission_sumary_rel',
        string="Invoice Lines"
    )
    
