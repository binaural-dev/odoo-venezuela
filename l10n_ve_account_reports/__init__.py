from . import controllers
from . import models
from . import tools

old_module = "binaural_account_reports"
new_module = "l10n_ve_account_reports"

def pre_init_hook(env):
    reassign_xml_account_report_actions_ids(env.cr)
    reassign_xml_daily_ledger_ids(env.cr)
    reassign_xml_financial_situation_statement_ids(env.cr)
    reassign_xml_result_statement_ids(env.cr)
    reassign_xml_show_amount_currency_ids(env.cr)
    
def reassign_xml_account_report_actions_ids(env):
    execute_script_sql(env, "action_account_report_")

def reassign_xml_daily_ledger_ids(env):
    execute_script_sql_two(env, "daily_ledger_report")
    
def reassign_xml_financial_situation_statement_ids(env):
    execute_script_sql(env, "account_financial_report_")
    execute_script_sql(env, "financial_situation_statement")
    
def reassign_xml_result_statement_ids(env):
    execute_script_sql(env, "result_statement")

def reassign_xml_show_amount_currency_ids(env):
    execute_script_sql(env, "show_amount_currency_general_ledger")

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