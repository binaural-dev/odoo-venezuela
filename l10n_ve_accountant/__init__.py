from . import models
from . import wizard
from . import report

old_module = "binaural_accountant"
new_module = "l10n_ve_accountant"

def pre_init_hook(env):
    reassign_account_data_ids(env.cr)
    reassign_tax_unit_data_ids(env.cr)

def reassign_account_data_ids(env):
    execute_script_sql(env, "alternative_")
    
def reassign_tax_unit_data_ids(env):
    tax_unit_data = {
        "tax_unit_data_binaural_payment_extension":"tax_unit_data_l10n_ve_payment_extension"        
    }
    
    for old_name, new_name in tax_unit_data.items():
        execute_script_sql_two(env, new_name, old_name)
    
def execute_script_sql(env, xml_id_prefix): 
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    )
    
def execute_script_sql_two(env, new_name, old_name): 
    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s, name=%s
        WHERE name=%s
        """,
        (new_module, new_name, old_name)
    )