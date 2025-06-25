from . import models
from . import wizards
from . import controllers

old_module = "binaural_iot_mf"
new_module = "l10n_ve_iot_mf"

def pre_init_hook(env):
    reassign_xml_iot_port_ids(env.cr)

def reassign_xml_iot_port_ids(env):
    execute_script_sql(env, "iot_port_com_")

def execute_script_sql(env, xml_id_prefix): 
    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    )
