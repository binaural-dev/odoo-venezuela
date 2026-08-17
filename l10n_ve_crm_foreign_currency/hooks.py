from odoo import fields


def post_init_hook(env):
    """Puebla los campos en moneda comercial (*_foreign) a partir de los
    montos históricos que ya existían en moneda de la compañía, en las
    columnas que expected_revenue/recurring_revenue/invoiced_target dejan de
    leer al pasar de store=True a compute=/store=False. Odoo no elimina esas
    columnas al cambiar el campo a no-almacenado, así que todavía se pueden
    leer por SQL directo.

    No se valida acá que toda compañía tenga moneda comercial configurada:
    se asume que toda instancia Binaural la tiene (constraint permanente en
    res.company), pero no se aborta la instalación por eso — una compañía
    sin configurar simplemente no recibe backfill (ver guarda más abajo) y
    queda en 0 hasta que se configure la moneda y se edite el registro a
    mano.

    La escritura del backfill se hace también por SQL directo (no
    record.write()), a propósito:
    - No dispara tracking/chatter (expected_revenue_foreign tiene
      tracking=True): una BD con miles de leads no genera miles de
      mail.message.
    - No pasa por los @api.constrains del módulo (monto > 0): un monto
      histórico ínfimo que redondee a 0 no puede abortar la instalación
      completa; ese caso puntual queda en 0 hasta que alguien lo edite.
    - El propio UPDATE es idempotente: solo toca columnas que sigan en su
      valor por defecto (0), así que una reinstalación no pisa ediciones que
      el usuario ya haya hecho a mano.

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
        expected_revenue_foreign = (
            company.currency_id._convert(expected_revenue, foreign_currency, company, rate_date)
            if expected_revenue else 0.0
        )
        recurring_revenue_foreign = (
            company.currency_id._convert(recurring_revenue, foreign_currency, company, rate_date)
            if recurring_revenue else 0.0
        )
        env.cr.execute(
            """
            UPDATE crm_lead
            SET expected_revenue_foreign = CASE WHEN expected_revenue_foreign = 0
                    THEN %s ELSE expected_revenue_foreign END,
                recurring_revenue_foreign = CASE WHEN recurring_revenue_foreign = 0
                    THEN %s ELSE recurring_revenue_foreign END
            WHERE id = %s
            """,
            (expected_revenue_foreign, recurring_revenue_foreign, lead_id),
        )


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
        env.cr.execute(
            """
            UPDATE crm_team
            SET invoiced_target_foreign = CASE WHEN invoiced_target_foreign = 0
                    THEN %s ELSE invoiced_target_foreign END
            WHERE id = %s
            """,
            (invoiced_target_foreign, team_id),
        )
