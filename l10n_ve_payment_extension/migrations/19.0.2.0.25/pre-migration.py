# Columnas técnicas que no se deben copiar al duplicar un registro huérfano
# por compañía: id es autogenerado, company_id se asigna explícitamente, y el
# resto son metadatos de auditoría propios de cada fila.
_SKIP_COLUMNS = {
    "id", "company_id",
    "create_uid", "create_date", "write_uid", "write_date",
}


def _copyable_columns(cr):
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'tax_unit'
        ORDER BY ordinal_position
    """)
    return [row[0] for row in cr.fetchall() if row[0] not in _SKIP_COLUMNS]


def migrate(cr, version):
    cr.execute("""
        UPDATE tax_unit tu
        SET available_date = '2000-01-01'
        FROM ir_model_data imd
        WHERE imd.model = 'tax.unit'
          AND imd.module = 'l10n_ve_accountant'
          AND imd.name = 'tax_unit_data_l10n_ve_payment_extension'
          AND imd.res_id = tu.id
          AND (tu.available_date IS NULL OR tu.available_date = CURRENT_DATE)
    """)
    cr.execute("SELECT id FROM res_company ORDER BY id")
    company_ids = [row[0] for row in cr.fetchall()]
    if not company_ids:
        return

    cr.execute("SELECT id FROM tax_unit WHERE company_id IS NULL")
    orphan_ids = [row[0] for row in cr.fetchall()]
    if not orphan_ids:
        return

    columns = _copyable_columns(cr)
    columns_sql = ", ".join(columns)

    for orphan_id in orphan_ids:
        cr.execute(
            "UPDATE tax_unit SET company_id = %s WHERE id = %s",
            (company_ids[0], orphan_id),
        )
        for company_id in company_ids[1:]:
            cr.execute(
                f"""
                INSERT INTO tax_unit ({columns_sql}, company_id)
                SELECT {columns_sql}, %s
                FROM tax_unit WHERE id = %s
                """,
                (company_id, orphan_id, company_id),
            )