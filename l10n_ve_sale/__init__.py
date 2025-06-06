from . import models

old_module = "binaural_sale"
new_module = "l10n_ve_sale"

def pre_init_hook(env):
    reassign_xml_ir_cron_cancel_ids(env.cr)
    reassign_xml_group_view_ids(env.cr)
    reassign_xml_groups_ids(env.cr)

def reassign_xml_ir_cron_cancel_ids(env):
    execute_script_sql(env, "ir_cron_cancel_orders_after_date")
    
def reassign_xml_group_view_ids(env):
    execute_script_sql(env, "group_view_pricelist_items")

def reassign_xml_groups_ids(env):
    execute_script_sql_two(env, "_group")

def execute_script_sql(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name=%s
        """,
        (new_module, old_module, xml_id_prefix),
    )
    
def execute_script_sql_two(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"%{xml_id_prefix}"),
    )    
