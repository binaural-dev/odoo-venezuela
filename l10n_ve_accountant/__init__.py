from odoo import _
from odoo.exceptions import UserError

from . import models
from . import wizard
from . import report

old_module = "binaural_accountant"
new_module = "l10n_ve_accountant"

def pre_init_hook(env):
    _check_account_move_partner_consistency(env.cr)
    reassign_account_data_ids(env.cr)
    reassign_tax_unit_data_ids(env.cr)

def _check_account_move_partner_consistency(cr):
    """Aborta la instalación si existen facturas de proveedor posteadas
    con el mismo nombre para el mismo proveedor/diario/compañía.

    El _auto_init de account_move.py necesita que estos grupos no
    existan para poder crear el índice único account_move_unique_name_ve
    sin tocar ningún dato. Si aquí se detectan, casi siempre es porque
    la migración de datos de proveedores (binaural_accountant ->
    l10n_ve_accountant) todavía no terminó de asignar el partner_id
    definitivo -- instalar en ese estado puede hacer que el índice no
    se cree (queda solo un warning en el log, sin daño a los datos,
    pero conviene resolverlo antes en vez de dejarlo pasar en silencio).
    """
    cr.execute(
        """
        SELECT rp.name, am.journal_id, am.name, COUNT(*)
        FROM account_move am
        LEFT JOIN res_partner rp ON rp.id = am.partner_id
        WHERE am.state = 'posted'
        AND am.name != '/'
        AND am.move_type IN ('in_invoice', 'in_refund', 'in_receipt')
        GROUP BY am.partner_id, am.journal_id, am.company_id, am.name, rp.name
        HAVING COUNT(*) > 1
        ORDER BY 4 DESC
        """
    )
    collisions = cr.fetchall()
    if not collisions:
        return

    detail = "\n".join(
        "  - Proveedor: %s | Diario: %s | Número: %s | Repeticiones: %s"
        % (partner_name or "(sin proveedor)", journal_id, name, count)
        for partner_name, journal_id, name, count in collisions[:20]
    )
    more = ""
    if len(collisions) > 20:
        more = _("\n  ... y %d grupo(s) más.") % (len(collisions) - 20)

    raise UserError(
        _(
            "No se puede instalar l10n_ve_accountant: se detectaron %(count)d "
            "grupo(s) de facturas de proveedor posteadas con el mismo número "
            "para el mismo proveedor y diario. Esto puede indicar datos de "
            "migración sin finalizar (proveedor transitorio) o duplicados "
            "reales sin resolver.\n\n"
            "%(detail)s%(more)s\n\n"
            "Corrija o confirme estos casos antes de continuar. Una vez "
            "resueltos, vuelva a actualizar el módulo -- el índice único se "
            "creará automáticamente sin necesidad de ningún paso adicional."
        )
        % {"count": len(collisions), "detail": detail, "more": more}
    )

def reassign_account_data_ids(env):
    execute_script_sql(env, "alternative_")
    
def reassign_tax_unit_data_ids(env):
    tax_unit_data = {
        "tax_unit_data_binaural_payment_extension":"tax_unit_data_l10n_ve_payment_extension"        
    }
    
    for old_name, new_name in tax_unit_data.items():
        execute_script_sql_two(env, new_name, old_name)

    
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