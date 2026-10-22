import warnings

from . import models
from . import wizard

# stock.picking.location_id (models/stock_picking.py) is re-declared here
# with compute="_compute_location_id" (overriding core's own
# _compute_location_id) to add 'sale_id' to its @api.depends -- but core's
# location_id/location_dest_id are precompute=True, and the re-declaration
# doesn't restate that flag, nor is 'sale_id' itself precomputable (core's
# own compute='_compute_sale_id', no precompute). Odoo escalates that
# mismatch to a UserWarning on every registry load ("Field
# stock.picking.location_id/location_dest_id cannot be precomputed..."),
# harmless at runtime (same category as l10n_ve_accountant's
# company_currency_id/invoice_currency_rate case -- see that module's
# __init__.py for the full story and why touching precompute flags here
# instead was ruled out) but fatal in odoo.sh's test-mode registry build
# (warnings-as-errors), aborting it before a single test runs.
warnings.filterwarnings(
    "ignore",
    message=r"Field stock\.picking\.location_(id|dest_id) cannot be "
            r"precomputed as it depends on non-precomputed field "
            r"stock\.picking\.sale_id",
    category=UserWarning,
)
# Sibling warning, same root cause: location_id loses precompute (the
# re-declaration above doesn't restate it) while location_dest_id keeps
# core's precompute=True untouched -- two fields computed by the same
# method now disagree on 'precompute', which Odoo flags on its own,
# separately from the "depends on non-precomputed field" one above.
warnings.filterwarnings(
    "ignore",
    message=r"stock\.picking: inconsistent 'precompute' for computed "
            r"fields location_id, location_dest_id",
    category=UserWarning,
)

old_module = "binaural_stock_accountant"
new_module = "l10n_ve_stock_account"
other_module = "l10n_ve_inventory_book"

def pre_init_hook(env):
    reassign_xml_ir_cron_ids(env.cr)
    reassign_xml_seq_guide_ids(env.cr)
    reassign_xml_transfer_reason_ids(env.cr)

def reassign_xml_ir_cron_ids(env):
    execute_script_sql_two(env, "ir_cron_auto_invoice_stock")

def reassign_xml_seq_guide_ids(env):
    execute_script_sql_two(env, "seq_guide_number")    
    
def reassign_xml_transfer_reason_ids(env):
    execute_script_sql_other(env, "transfer_reason_")
    
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
    
def execute_script_sql_other(env, xml_id_prefix):    
    env.execute(
        """
        UPDATE ir_model_data
        SET module=%s
        WHERE module=%s AND name LIKE %s
        """,
        (new_module, other_module, f"{xml_id_prefix}%"),
    ) 