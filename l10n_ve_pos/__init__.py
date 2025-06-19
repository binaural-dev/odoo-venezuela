from . import models
from . import report
from . import controllers
from . import wizard

import logging
_logger = logging.getLogger(__name__)

old_module = "binaural_pos"
new_module = "l10n_ve_pos"

def pre_init_hook(env):
    reassign_xml_groups_ids(env.cr)

def reassign_xml_groups_ids(env):
    execute_script_sql(env, "group_")

def execute_script_sql(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    )    
