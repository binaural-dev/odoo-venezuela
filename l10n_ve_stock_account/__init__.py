from . import models
from . import wizard

old_module = "binaural_stock_account"
new_module = "l10n_ve_stock_account"

def pre_init_hook(env):
    reassign_xml_ir_cron_ids(env.cr)
    reassign_xml_seq_guide_ids(env.cr)
    reassign_xml_transfer_reason_ids(env.cr)

def reassign_xml_ir_cron_ids(env):
    execute_script_sql_two(env, "ir_cron_auto_invoice_stock")

def reassign_xml_seq_guide_ids(env):
    execute_script_sql_two(env, "seq_guide_number")    
    
def reassign_xml_transfer_reason_ids(env):
    execute_script_sql(env, "transfer_reason_")
    
def execute_script_sql(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    ) 

def execute_script_sql_two(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name=%s
        """,
        (new_module, old_module, xml_id_prefix),
    ) 
    
