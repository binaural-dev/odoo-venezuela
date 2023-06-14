# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date
import logging
_logger = logging.getLogger(__name__)
from datetime import date, datetime


class MercadolibrePublicInvoiceWizard(models.TransientModel):
    _name = 'mercadolibre.public.wizard'
    _description = 'Mercadolibre publicar ordenes - Wizard'


    def _default_count(self):
        context = self.env.context
        if 'active_ids' in context:
            return len(self.env.context['active_ids'])
        else:
            return 1

    count = fields.Integer(default=_default_count)

    def public_product(self,context=None):
        context = context or self.env.context
        active_ids = ('active_ids' in context and context['active_ids']) or []
        model = context['active_model']
        order_ids = self.env[model].sudo().browse(active_ids)
        if order_ids:
            for o in order_ids:
                if o.meli_orders:
                    for mo in o.meli_orders:
                        _logger.info("Orden: %s" % (mo.order_id))
                        if not mo.invoice_posted:
                            _logger.info("Orden a publicar: %s" % (mo.order_id))
                            mo.sudo().orders_post_invoice()

