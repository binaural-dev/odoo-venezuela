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
    execute_script_sql(env, "tax_unit_data_")
    
def execute_script_sql(env, xml_id_prefix): 
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    )