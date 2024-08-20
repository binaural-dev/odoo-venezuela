import logging
import copy
from bs4 import BeautifulSoup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
JOURNAL_DOMAIN = [
    ("active", "=", True),
    ("type", "=", "sale"),
]


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _get_journal_id(self):
        self.ensure_one()

        subsidiary_id = self.subsidiary_id
        
        if self.tax_included:
            return subsidiary_id.dairy_fiscal if subsidiary_id.dairy_fiscal else self.env.company.dairy_fiscal
        
        return subsidiary_id.dairy_no_fiscal if subsidiary_id.dairy_no_fiscal else self.env.company.dairy_no_fiscal