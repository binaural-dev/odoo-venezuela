# Este post-migration corre DESPUÉS de que el ORM crea la columna company_id
# en fees_retention (campo nuevo, required, default=env.company). Para bases
# ya existentes eso deja todas las tarifas asignadas a una sola compañía (la
# que estaba activa durante el upgrade); este script las duplica al resto de
# las compañías para que cada una tenga su propio catálogo, incluyendo sus
# líneas de accumulated.fees (fees_id es Many2one, cada tarifa necesita sus
# propias líneas, no pueden compartirse entre compañías).
_SKIP_COLUMNS = {
    "id", "company_id",
    "create_uid", "create_date", "write_uid", "write_date",
}
_SKIP_ACCUMULATED_COLUMNS = {
    "id", "fees_id",
    "create_uid", "create_date", "write_uid", "write_date",
}


def _copyable_columns(cr, table_name, skip_columns):
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return [row[0] for row in cr.fetchall() if row[0] not in skip_columns]


def migrate(cr, version):
    cr.execute("SELECT id FROM res_company ORDER BY id")
    company_ids = [row[0] for row in cr.fetchall()]
    if len(company_ids) < 2:
        return

    first_company_id = company_ids[0]
    other_company_ids = company_ids[1:]

    cr.execute(
        "SELECT id FROM fees_retention WHERE company_id = %s",
        (first_company_id,),
    )
    source_ids = [row[0] for row in cr.fetchall()]
    if not source_ids:
        return

    fees_columns = _copyable_columns(cr, "fees_retention", _SKIP_COLUMNS)
    fees_columns_sql = ", ".join(fees_columns)
    accumulated_columns = _copyable_columns(
        cr, "accumulated_fees", _SKIP_ACCUMULATED_COLUMNS
    )
    accumulated_columns_sql = ", ".join(accumulated_columns)

    for source_id in source_ids:
        for company_id in other_company_ids:
            cr.execute(
                f"""
                INSERT INTO fees_retention ({fees_columns_sql}, company_id)
                SELECT {fees_columns_sql}, %s
                FROM fees_retention src
                WHERE src.id = %s
                  AND NOT EXISTS (
                      SELECT 1 FROM fees_retention dst
                      WHERE dst.company_id = %s
                        AND dst.name = src.name
                  )
                RETURNING id
                """,
                (company_id, source_id, company_id),
            )
            inserted = cr.fetchone()
            if not inserted:
                continue
            new_fees_id = inserted[0]

            cr.execute(
                f"""
                INSERT INTO accumulated_fees ({accumulated_columns_sql}, fees_id)
                SELECT {accumulated_columns_sql}, %s
                FROM accumulated_fees src
                WHERE src.fees_id = %s
                """,
                (new_fees_id, source_id),
            )
