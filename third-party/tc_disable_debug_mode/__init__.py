
from . import controllers

def pre_init_check(cr):
    from odoo.service import common
    from odoo.exceptions import UserError
    version_info = common.exp_version()
    server_serie =version_info.get('server_serie')
    if server_serie!='16.0':raise UserError('Module support Odoo series 16.0 found {}.'.format(server_serie))
    return True