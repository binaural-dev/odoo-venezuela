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
    """res_company.module_binaural_igtf (línea no homologada, propio de
    binaural_tax, sin equivalente en l10n_ve_accountant) -- ver
    INVENTARIO_MODULOS_NO_HOMOLOGADOS.md, sección binaural_tax.

    Igual que el resto de esta línea, no puede vivir en migrations/
    porque l10n_ve_accountant es instalación nueva para estos clientes
    (los pre/post-migrate.py de una carpeta de versión no se ejecutan en
    instalación nueva -- solo en 'to upgrade' de un módulo ya
    instalado).
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
    """Adopta el tax.unit ya migrado desde binaural_payment_extension (si
    existe) en vez de dejar que l10n_ve_accountant y
    l10n_ve_payment_extension creen, cada uno, su propia fila nueva con el
    mismo valor de UT (0,40) -- ver INVENTARIO_MODULOS_NO_HOMOLOGADOS.md,
    sección tax_unit duplicado.

    El fix anterior solo renombraba el xmlid hacia el nombre que espera
    l10n_ve_accountant/data/tax_unit_data.xml
    (tax_unit_data_l10n_ve_payment_extension), pero
    l10n_ve_payment_extension/data/tax_unit_data.xml usa un xmlid DISTINTO
    (tax_unit_data_binaural_payment_extension) -- con solo un rename,
    cuando ese segundo módulo se instalara igual creaba su propia fila
    nueva. Aquí se resuelve creando DOS punteros (ir_model_data) al mismo
    registro, uno para cada nombre que cada módulo espera encontrar ya
    creado.
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
        # Sin dato migrado de binaural_payment_extension (instalación
        # limpia, o línea homologada) -- cada módulo crea su propio seed
        # normalmente, no hay nada que adoptar.
        return
    res_id = row[0]

    # Reasigna el xmlid original al nombre que espera
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

    # Crea además un alias bajo el nombre que espera
    # l10n_ve_accountant/data/tax_unit_data.xml, apuntando al MISMO
    # registro -- así tampoco crea una fila nueva.
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
