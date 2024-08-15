from odoo import api, Command, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """DELETE FROM ir_ui_view
           WHERE id IN (
                select res_id 
                from ir_model_data 
                where module = 'binaural_accountant' 
                AND name IN (
                    'view_partner_property_form_inherit_binaural'
                )
            )
        """
    )
