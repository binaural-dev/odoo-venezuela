from . import models
from . import wizard

old_module = "binaural_stock"
new_module = "l10n_ve_stock"

def pre_init_hook(env):
    reassign_xml_groups_ids(env.cr)
    reassign_xml_product_category_ids(env.cr)

def reassign_xml_groups_ids(env):
    execute_script_sql(env, "group_")

def reassign_xml_product_category_ids(env):
    execute_script_sql(env, "product_category_multi_company_rule")

def execute_script_sql(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    )
