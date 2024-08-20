from odoo import api, Command, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """DELETE FROM ir_ui_view
           WHERE id IN (
                select res_id 
                from ir_model_data 
                where module = 'binaural_mobile' 
                AND name IN (
                    'binaural_movil_app_res_config_settings_view_form'
                )
            )
        """
    )
