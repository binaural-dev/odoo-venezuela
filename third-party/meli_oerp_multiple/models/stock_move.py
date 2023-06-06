# -*- coding: utf-8 -*-

from odoo import fields, osv, models, api
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)
import pdb
import requests
from odoo.exceptions import UserError, ValidationError

class stock_move(models.Model):

    _inherit = "stock.move"

    def _action_done(self,cancel_backorder=None):
        context = self.env.context
        #_logger.info("context: "+str(context))
        company = self.env.user.company_id
        #_logger.info("company: "+str(company))
        #_logger.info("meli_oerp_stock >> stock.move _action_done ")
        ret = super( stock_move, self)._action_done(cancel_backorder=cancel_backorder)
        _logger.info("meli_oerp_multiple >> stock.move _action_done OK. Posting Job Notification ")
        #return
        try:
            model_ids = []
            for st in self:
                #_logger.info("Moved products, put all this product stock state on batch for inmediate update: #"+str(len(st.product_id))+" >> "+str(st.product_id.ids) )

                for p in st.product_id:
                    #_logger.info("post stock for: "+p.display_name)
                    if p.id not in model_ids:
                        #removing duplicates
                        model_ids.append(p.id)

            if model_ids and len(model_ids)>0:
                account = company.mercadolibre_connections and company.mercadolibre_connections[0]
                config = account and account.configuration
                if (config and config.mercadolibre_cron_post_update_stock):
                    internals = {
                        "application_id": company.id,
                        "user_id": self.env.user.id,
                        "company": company.id,
                        "user": self.env.user.id,
                        "topic": "internal_job",
                        "resource": "meli_update_remote_stock #"+str(len(model_ids)),
                        "state": "PROCESSING",
                        "model_ids": str(model_ids),
                        "model_ids_step": 40,
                        "model_ids_count": len(model_ids) or 0,
                        "model_ids_count_processed": 0
                    }
                    _logger.info(internals)
                    noti = self.env["mercadolibre.notification"].start_internal_notification( internals=internals, account=account )      
                    _logger.info(noti)          
        except Exception as e:
            _logger.error(e, exc_info=True)
            raise ValidationError("Error creando proceso de actualizacion de stock de MercadoLibre, intente nuevamente en unos sergundos. Error: "+str(e))

        return ret
