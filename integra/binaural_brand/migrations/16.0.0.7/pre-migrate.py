from odoo import api, Command, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """DELETE FROM ir_ui_view
           WHERE id IN (
                select res_id 
                from ir_model_data 
                where module = 'binaural_brand' 
                AND name IN (
                    'view_view_order_form_inherited_binaural_marca_form', 
                    'view_search_group_by_brand_sale_report',
                    'view_purchase_order_form_inherited_binaural_marcas_form',
                    'report_purchase','report_purchase_pedido',
                    'pos_order_brand_form_inherit',
                    'view_report_pos_order_search_brand',
                    'view_form_move_inherited_binaural_marca_form',
                    'view_product_brand_tree_inherited_stock_valuation'
                )
            )
        """
    )
