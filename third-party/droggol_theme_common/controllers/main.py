# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import http
from odoo.http import request


class DroggolThemeCommon(http.Controller):

    @http.route(['/droggol_theme_common/design_content/<model("dr.website.content"):content>'], type='http', website=True, auth='user')
    def design_content(self, content, **post):
        return request.render('droggol_theme_common.design_content', {'content': content, 'no_header': True, 'no_footer': True})
