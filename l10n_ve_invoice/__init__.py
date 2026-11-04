from . import controllers
from . import models
from . import wizard

from odoo.addons.l10n_ve_base.models.res_partner import DEFAULT_TZ

old_module = "binaural_invoice"
new_module = "l10n_ve_invoice"

def post_init_hook(env):
    # Mismo cálculo que create()/write(). Al instalar no hay usuario del
    # cliente, así que se usa la tz de la compañía (America/Caracas si no
    # tiene). Con NOW() se mezclaba la fecha local con la hora UTC y desde las
    # 20:00 en UTC-4 quedaba el día anterior (HD #15954).
    env.cr.execute("""
        SELECT company_id, invoice_date_display
          FROM account_move
         WHERE invoice_date_display IS NOT NULL
           AND invoice_date_display_datetime IS NULL
         GROUP BY company_id, invoice_date_display
    """)
    for company_id, date_value in env.cr.fetchall():
        company = env["res.company"].browse(company_id)
        move_model = env["account.move"].with_context(
            tz=company.partner_id.tz or DEFAULT_TZ
        )
        env.cr.execute(
            """
            UPDATE account_move
               SET invoice_date_display_datetime = %s
             WHERE company_id = %s
               AND invoice_date_display = %s
               AND invoice_date_display_datetime IS NULL
            """,
            (
                move_model._get_invoice_date_display_datetime(date_value),
                company_id,
                date_value,
            ),
        )

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