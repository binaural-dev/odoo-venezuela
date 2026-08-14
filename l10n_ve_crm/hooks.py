from odoo import fields


def post_init_hook(env):
    """Puebla los campos en moneda comercial (*_foreign) a partir de los
    montos históricos que ya existían en moneda de la compañía, en las
    columnas que expected_revenue/recurring_revenue/invoiced_target dejan de
    leer al pasar de store=True a compute=/store=False. Odoo no elimina esas
    columnas al cambiar el campo a no-almacenado, así que todavía se pueden
    leer por SQL directo antes de que quede cualquier duda de que están ahí.

    La conversión usa la tasa vigente en la fecha de creación de cada
    registro (no la del día de la migración), para que el monto migrado sea
    fiel al momento real en que se cargó."""
    _backfill_crm_lead_foreign_amounts(env)
    _backfill_crm_team_foreign_amounts(env)


def _backfill_crm_lead_foreign_amounts(env):
    env.cr.execute("""
        SELECT id, expected_revenue, recurring_revenue, create_date, company_id
        FROM crm_lead
        WHERE (expected_revenue IS NOT NULL AND expected_revenue != 0)
           OR (recurring_revenue IS NOT NULL AND recurring_revenue != 0)
    """)
    rows = env.cr.fetchall()
    for lead_id, expected_revenue, recurring_revenue, create_date, company_id in rows:
        company = env["res.company"].browse(company_id) if company_id else env.company
        foreign_currency = company.foreign_currency_id
        if not foreign_currency or not company.currency_id:
            continue

        rate_date = create_date.date() if create_date else fields.Date.today()
        vals = {}
        if expected_revenue:
            vals["expected_revenue_foreign"] = company.currency_id._convert(
                expected_revenue, foreign_currency, company, rate_date
            )
        if recurring_revenue:
            vals["recurring_revenue_foreign"] = company.currency_id._convert(
                recurring_revenue, foreign_currency, company, rate_date
            )
        if vals:
            env["crm.lead"].browse(lead_id).write(vals)


def _backfill_crm_team_foreign_amounts(env):
    env.cr.execute("""
        SELECT id, invoiced_target, create_date, company_id
        FROM crm_team
        WHERE invoiced_target IS NOT NULL AND invoiced_target != 0
    """)
    rows = env.cr.fetchall()
    for team_id, invoiced_target, create_date, company_id in rows:
        company = env["res.company"].browse(company_id) if company_id else env.company
        foreign_currency = company.foreign_currency_id
        if not foreign_currency or not company.currency_id:
            continue

        rate_date = create_date.date() if create_date else fields.Date.today()
        invoiced_target_foreign = company.currency_id._convert(
            invoiced_target, foreign_currency, company, rate_date
        )
        env["crm.team"].browse(team_id).write(
            {"invoiced_target_foreign": invoiced_target_foreign}
        )
