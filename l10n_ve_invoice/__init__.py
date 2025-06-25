from . import controllers
from . import models
from . import wizard

old_module = "binaural_invoice"
new_module = "l10n_ve_invoice"

def pre_init_hook(env):
    reassign_xml_invoice_correlative_ids(env.cr)
    reassign_xml_series_invoicing_ids(env.cr)
    reassign_xml_group_sales_invoicing_ids(env.cr)

def reassign_xml_invoice_correlative_ids(env):
    execute_script_sql(env, "invoice_correlative")
    
def reassign_xml_series_invoicing_ids(env):
    execute_script_sql(env, "series_invoicing_correlative")
    
def reassign_xml_group_sales_invoicing_ids(env):
    execute_script_sql(env, "group_sales_invoicing_series")

def execute_script_sql(env, xml_id_prefix): 
    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, old_module, f"{xml_id_prefix}%"),
    )