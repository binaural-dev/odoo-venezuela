from . import models
import logging

_logger = logging.getLogger(__name__)

old_module = "binaural_location"
new_module = "l10n_ve_location"

def pre_init_hook(env):
    reassign_xml_ids(env.cr)
    reassign_xml_parish_ids(env.cr)
    reassign_xml_municipality_ids(env.cr)

def reassign_xml_ids(env):
    execute_script_sql(env, "res_country_state_")
    
def reassign_xml_parish_ids(env):
    execute_script_sql(env, "res_country_parish_")

def reassign_xml_municipality_ids(env):
    execute_script_sql(env, "res_country_municipality_")

def execute_script_sql(env, xml_id_prefix): 
    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    )