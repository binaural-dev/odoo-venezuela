# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)

import pdb

import requests
from odoo.addons.meli_oerp.melisdk.meli import Meli
from odoo.addons.meli_oerp.models.versions import *

mapping_meli_sku_regex = {
    #"alephcrm": [
    #    {
    #        "regex": r"([a-zA-Z0-9]+[\-]+)([A-Z0-9]+[^x])",
    #        "group": 1,
    #        "test": "A12-848ERZEREx10"
    #    },
    #    {
    #        "regex": r"([A-Z0-9]+[^-x]$)",
    #        "group": 0,
    #        "test": "DF848ERZERE"
    #    }
    #]
}

# Mapping table
# "Cód SKU Propio Mercado Libre": "SKU ODOO"
mapping_meli_sku_defaut_code = {
    #"904254AX50": "Y051",
}

class meli_oerp_sku_rule(models.Model):

    _name = "meli_oerp.sku.rule"
    _description = "Meli Sku Rule"

    name = fields.Char(string="Name",help="Sku Name received",required=True,index=True)
    type = fields.Selection([('map','Map'),('regex','Formula'),('stock','Stock Rule')],string="Rule type", index=True, default='map')

    sku = fields.Char(string="Sku",help="Sku Map in Odoo",required=False,index=True)
    barcode = fields.Char(string="Barcode",help="Barcode Map in Odoo",required=False,index=True)

    formula = fields.Char(string="Formula",help="Sku Regex Formula",required=False,index=True)
    group = fields.Char(string="Group",help="Sku Regex Group",required=False)
    test = fields.Char(string="Test",help="Sku Regex Test",required=False)

    security_virtual_stock_to_pause = fields.Float(string="Virtual Stock", default=False )
    security_quantity_stock_to_pause = fields.Float(string="Quantity Stock", default=False )

    _sql_constraints = [
        ('unique_meli_oerp_sku_rule', 'unique(name)', 'Rule name already exists!')
    ]

    def map_to_sku(self, name ):

        sku = None
        maps = self.search([('name','=',str(name)),('type','=','map')])

        if len(maps)==1:
            sku = maps[0].sku
        #else:
        #    _logger.error("Sku Map duplicates:"+str(name))

        return sku

    def resolve_to_sku(self, name ):
        sku = None
        return sku
