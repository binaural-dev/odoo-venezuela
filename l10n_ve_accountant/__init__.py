from . import models
from . import wizard
from . import report

from odoo import SUPERUSER_ID, api
old_module = "binaural_accountant"
new_module = "l10n_ve_accountant"

def pre_init_hook(env):
    reassign_account_data_ids(env.cr)
    reassign_tax_unit_data_ids(env.cr)
    retire_module_binaural_igtf_column(env.cr)


def retire_module_binaural_igtf_column(cr):
    """res_company.module_binaural_igtf (non-homologated line, specific to
    binaural_tax, with no equivalent in l10n_ve_accountant) -- see
    INVENTARIO_MODULOS_NO_HOMOLOGADOS.md, binaural_tax section.

    Like the rest of this line, it cannot live in migrations/ because
    l10n_ve_accountant is a fresh install for these clients (the
    pre/post-migrate.py files of a version folder do not run on a fresh
    install -- only on 'to upgrade' of a module that is already
    installed).
    """
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'res_company' AND column_name = 'module_binaural_igtf'"
    )
    if not cr.fetchone():
        return

    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS l10n_ve_accountant_migration_v17_backup (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR NOT NULL,
            source_column VARCHAR NOT NULL,
            record_id INTEGER NOT NULL,
            value_text TEXT,
            backed_up_at TIMESTAMP DEFAULT now()
        )
        """
    )
    cr.execute(
        "SELECT id, module_binaural_igtf FROM res_company "
        "WHERE module_binaural_igtf IS NOT NULL"
    )
    rows = cr.fetchall()
    if rows:
        cr.executemany(
            """
            INSERT INTO l10n_ve_accountant_migration_v17_backup
                (source_table, source_column, record_id, value_text)
            VALUES ('res_company', 'module_binaural_igtf', %s, %s)
            """,
            [(rec_id, str(value)) for rec_id, value in rows],
        )

    cr.execute("ALTER TABLE res_company DROP COLUMN module_binaural_igtf")

def reassign_account_data_ids(env):
    execute_script_sql(env, "alternative_")
    
def reassign_tax_unit_data_ids(env):
    """Adopt the tax.unit already migrated from binaural_payment_extension
    (if it exists) instead of letting l10n_ve_accountant and
    l10n_ve_payment_extension each create their own new row with the
    same UT value (0.40) -- see INVENTARIO_MODULOS_NO_HOMOLOGADOS.md,
    duplicate tax_unit section.

    The previous fix only renamed the xmlid to the name expected by
    l10n_ve_accountant/data/tax_unit_data.xml
    (tax_unit_data_l10n_ve_payment_extension), but
    l10n_ve_payment_extension/data/tax_unit_data.xml uses a DIFFERENT xmlid
    (tax_unit_data_binaural_payment_extension) -- with only a rename,
    when that second module was installed it still created its own new
    row. This is solved here by creating TWO pointers (ir_model_data) to
    the same record, one for each name that each module expects to find
    already created.
    """
    cr = env.cr if hasattr(env, "cr") else env
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = 'binaural_payment_extension'
          AND name = 'tax_unit_data_binaural_payment_extension'
          AND model = 'tax.unit'
        """
    )
    row = cr.fetchone()
    if not row:
        # No migrated data from binaural_payment_extension (clean
        # install, or homologated line) -- each module creates its own
        # seed normally, there is nothing to adopt.
        return
    res_id = row[0]

    # Reassign the original xmlid to the name expected by
    # l10n_ve_payment_extension/data/tax_unit_data.xml.
    cr.execute(
        """
        UPDATE ir_model_data
        SET module = 'l10n_ve_payment_extension',
            name = 'tax_unit_data_binaural_payment_extension'
        WHERE module = 'binaural_payment_extension'
          AND name = 'tax_unit_data_binaural_payment_extension'
          AND model = 'tax.unit'
        """
    )

    # Also create an alias under the name expected by
    # l10n_ve_accountant/data/tax_unit_data.xml, pointing to the SAME
    # record -- so it does not create a new row either.
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        VALUES ('l10n_ve_accountant', 'tax_unit_data_l10n_ve_payment_extension', 'tax.unit', %s, TRUE)
        ON CONFLICT (module, name) DO NOTHING
        """,
        (res_id,),
    )
    
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
def set_main_company_currency_to_vef(env):
    """Set main company currency to VEF via SQL.

    The ORM's ``account.models.company.write`` raises ``UserError`` when
    journal items exist (installed by ``account`` module before this
    post-hook runs), so we bypass it with a direct SQL update.
    """
    env.cr.execute(
        """UPDATE res_company SET currency_id = (
               SELECT res_id FROM ir_model_data
               WHERE module='base' AND name='VEF'
               LIMIT 1
           ) WHERE id = (
               SELECT res_id FROM ir_model_data
               WHERE module='base' AND name='main_company'
               LIMIT 1
           )"""
    )
