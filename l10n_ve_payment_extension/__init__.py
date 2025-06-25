from . import controllers
from . import models
from . import wizard
from . import report

old_module = "binaural_payment_extension"
new_module = "l10n_ve_payment_extension"
    
def pre_init_hook(env):
    reassign_xml_withholding_ids(env.cr)
    reassign_xml_fees_retention_ids(env.cr)
    reassign_xml_type_person_ids(env.cr)
    handle_payment_concepts(env.cr)
    reassign_xml_accumulated_ids(env.cr)
    reassign_xml_tax_unit_data_ids(env.cr)
    reassign_xml_ir_rule_ids(env.cr)
    
def reassign_xml_withholding_ids(env):
    execute_script_sql(env, "account_withholding_type_")

def reassign_xml_fees_retention_ids(env):
    
    fess_retention_data = {
        "fees_retention_data_substrat_binaural_payment_extension":"fees_retention_data_substrat_l10n_ve_payment_extension",
        "fees_retention_data_percentage_one_binaural_payment_extension":"fees_retention_data_percentage_one_l10n_ve_payment_extension",
        "fees_retention_data_percentage_two_binaural_payment_extension":"fees_retention_data_percentage_two_l10n_ve_payment_extension",
        "fees_retention_data_substrat_second_binaural_payment_extension":"fees_retention_data_substrat_second_l10n_ve_payment_extension",
        "fees_retention_data_binaural_percentage_three_payment_extension":"fees_retention_data_l10n_ve_percentage_three_payment_extension",
        "fees_retention_data_percentage_four_binaural_payment_extension":"fees_retention_data_percentage_four_l10n_ve_payment_extension",
        "fees_retention_data_percentage_five_binaural_payment_extension" :"fees_retention_data_percentage_five_l10n_ve_payment_extension"   
    }
    
    for old_name, new_name in fess_retention_data.items():
        execute_script_sql_two(env, new_name, old_name)
    
def reassign_xml_type_person_ids(env):

    type_person_data = {
        "type_person_binaural_payment_extension":"type_person_l10n_ve_payment_extension",
        "type_person_two_binaural_payment_extension":"type_person_two_l10n_ve_payment_extension",
        "type_person_three_binaural_payment_extension":"type_person_three_l10n_ve_payment_extension",
        "type_person_four_binaural_payment_extension":"type_person_four_l10n_ve_payment_extension",
        "type_person_five_binaural_payment_extension":"type_person_five_l10n_ve_payment_extension",
        "type_person_six_binaural_payment_extension":"type_person_six_l10n_ve_payment_extension",
        "type_person_seven_binaural_payment_extension":"type_person_seven_l10n_ve_payment_extension"        
    }
    
    for old_name, new_name in type_person_data.items():
        execute_script_sql_two(env, new_name, old_name)

def handle_payment_concepts(env):
    
    payment_concepts_data = {
        "payment_concept_one_binaural_payment_extension":"payment_concept_one_l10n_ve_payment_extension",
        "payment_concept_two_binaural_payment_extension":"payment_concept_two_l10n_ve_payment_extension",
        "payment_concept_three_binaural_payment_extension":"payment_concept_three_l10n_ve_payment_extension",
        "payment_concept_four_binaural_payment_extension":"payment_concept_four_l10n_ve_payment_extension",
        "payment_concept_five_binaural_payment_extension":"payment_concept_five_l10n_ve_payment_extension",
        "payment_concept_six_binaural_payment_extension":"payment_concept_six_l10n_ve_payment_extension",
        "payment_concept_seven_binaural_payment_extension":"payment_concept_seven_l10n_ve_payment_extension"
    }

    for old_name, new_name in payment_concepts_data.items():
        execute_script_sql_two(env, new_name, old_name)

def reassign_xml_accumulated_ids(env):
    execute_script_sql(env, "accumulated_fees_")
    
def reassign_xml_sequence_ids(env):
    execute_script_sql(env, "sequence_")
    
def reassign_xml_tax_unit_data_ids(env):
    execute_script_sql(env, "tax_unit_data_")
    
def reassign_xml_ir_rule_ids(env):
    execute_script_sql(env, "retention_")
    
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
        WHERE module=%s AND name=%s
        """,
        (new_module, new_name, old_module, old_name),
    )