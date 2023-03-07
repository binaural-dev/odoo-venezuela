from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

# def search_account(self, ret_line):
#     """
#     This method search the account to be used in the retention line.

#     :param ret_line: account.retention.line record

#     :return: account.account record
#     """
#     if self.type in ["out_invoice"]:
        