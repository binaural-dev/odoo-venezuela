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


class stock_move(models.Model):

    _inherit = "stock.move"

    #cancel_backorder parameter is present in odoo version >= 13.0
    def _action_done(self, cancel_backorder=None ):
        context = self.env.context
        #_logger.info("context: "+str(context))
        company = self.env.user.company_id
        #_logger.info("company: "+str(company))
        #_logger.info("meli_oerp_stock >> stock.move _action_done ")
        ret = super( stock_move, self)._action_done(cancel_backorder=cancel_backorder)
        #_logger.info("meli_oerp_stock >> stock.move _action_done OK ")
        for st in self:
            #_logger.info("Moved products, put all this product stock state on batch for inmediate update: #"+str(len(st.product_id))+" >> "+str(st.product_id.ids) )
            for p in st.product_id:
                _logger.info("post stock for: "+p.display_name)

        return ret

class stock_picking( models.Model):

    _inherit = "stock.picking"

    def action_reassign( self ):

        moves = self.mapped('move_lines').filtered(lambda move: move.state not in ('draft', 'cancel', 'done'))
        if moves:
            #re assign
            _logger.info("meli_oerp_stock reassign: "+str(moves))
            for m in moves:
                mv = m
                qty = mv.product_uom_qty
                _logger.info("action_reassign Move Line: State:"+str(mv.state)
                            +" Product:"+str(mv.product_id and mv.product_id.name)
                            +" Location:"+str(mv.location_id and mv.location_id.name)
                            #+" Lot:"+str(mv.lot_id and mv.lot_id.name)
                            +" Qty Reserved:"+str(mv.product_uom_qty)
                            )
                if m.product_id: # and m.location_id.mercadolibre_active == True:
                    _logger.info("meli_oerp_stock reassign: move: "+str(m))
                    lotids = self.env["stock.location"].search([('location_id','in',[self.location_id])]).mapped('id') or []
                    #quants_by_lot = self.env["stock.quant"].search([('product_id','=',self.product_id.id),('location_id','=',self.location_id.id)])
                    quants = self.env["stock.quant"].search([('product_id','=',m.product_id.id),('location_id','in',lotids)])
                    _logger.info("meli_oerp_stock reassign: quants:"+str(quants))
                    #search max!!!
                    max = 0
                    qs = None
                    for q in quants:
                        #_logger.info("meli_oerp_stock reassign: q:"+str(q.location_id and q.location_id.name))
                        #_logger.info("meli_oerp_stock reassign: q.quantity:"+str(q.quantity))
                        if q.quantity>max and q.location_id.mercadolibre_active == True:
                            qs = q
                            max = qs.quantity
                    if qs:
                        _logger.info("meli_oerp_stock reassign: qs:"+str(qs and qs.location_id and qs.location_id.name)+" quantity:"+str(qs.quantity))
                        m.lot_id = qs and qs.lot_id
                        m.location_id = qs and qs.location_id
                        #m.product_uom_qty = qty
                        #m.state = 'assigned'

    # Comprobar disponibilidad
    def __action_assign( self ):
        _logger.info("meli_oerp_stock re-assign: "+str(self))
        #puede llegar a asignar varios stocks asociados
        ret = super( stock_picking, self).action_assign()

        self.action_reassign()


        return ret


class stock_move_line(models.Model):

    _inherit = "stock.move.line"

    #@api.onchange('location_id')
    def __onchange_location_id_ml(self):
        """ When the user is encoding a move line for a tracked product, we apply some logic to
        help him. This includes:
            - automatically switch `qty_done` to 1.0
            - warn if he has already encoded `lot_name` in another move line
        """
        res = {}
        if self.location_id:
            # and self.location_id.mercadolibre_active == True:
            #
            _logger.info("Location es ML Active "+str(self.location_id))
            #search for the max... check the origin (move_ids.origin)
            # check  and search for lot_id
            # search for stock.quant   related to this location_id, then choose the first bigger lot_id
            if self.product_id:
                #quants_by_lot = self.env["stock.quant"].search([('product_id','=',self.product_id.id),('location_id','=',self.location_id.id)])
                quants = self.env["stock.quant"].search([('product_id','=',self.product_id.id),('location_id','=',self.location_id.id)])
                #search max!!!
                max = 0
                qs = quants and quants[0]
                for q in quants:
                    if q.quantity>max:
                        qs = q
                        max = qs.quantity
                self.lot_id = qs and qs.lot_id


        else:
            message = "Use a MercadoLibre Active Location"
            #if message:
            #    res['warning'] = {'title': _('Warning'), 'message': message}
        return res


    #@api.onchange('lot_id')
    def __onchange_lot_id_ml(self):
        """ When the user is encoding a move line for a tracked product, we apply some logic to
        help him. This includes:
            - automatically switch `qty_done` to 1.0
            - warn if he has already encoded `lot_name` in another move line
        """
        res = {}
        if self.lot_id:
            #
            #_logger.info("Location es ML Active "+str(self.location_id))
            #search for the max... check the origin (move_ids.origin)
            # check  and search for lot_id
            # search for stock.quant   related to this location_id, then choose the first bigger lot_id
            if self.product_id:
                quants = self.env["stock.quant"].search([('product_id','=',self.product_id.id),('lot_id','=',self.lot_id.id)])
                #search max!!!
                max = 0
                qs = quants and quants[0]
                for q in quants:
                    if q.quantity>max:
                        qs = q
                        max = qs.quantity
                self.location_id = qs and qs.location_id


        else:
            message = "Use a Lot"
            #if message:
            #    res['warning'] = {'title': _('Warning'), 'message': message}
        return res

class stock_location(models.Model):

    _inherit = "stock.location"

    mercadolibre_active = fields.Boolean(string="Ubicacion activa para MercadoLibre",index=True)
    mercadolibre_logistic_type = fields.Char(string="Logistic Type Asociado",index=True)

class DeliveryCarrier(models.Model):

    _inherit = "delivery.carrier"

    ml_tracking_url = fields.Char(string="Default tracking url")

    def get_tracking_link(self, picking):
        if self.ml_tracking_url and picking and picking.carrier_tracking_ref:
            return self.ml_tracking_url+str(picking.carrier_tracking_ref)

        return super(DeliveryCarrier, self).get_tracking_link(picking)


#class stock_valuation_layer( models.Model):

#    _inherit = "stock.valuation.layer"

    #unit_cost = fields.Monetary('Unit Value', readonly=False)
    #value = fields.Monetary('Total Value', readonly=False)
