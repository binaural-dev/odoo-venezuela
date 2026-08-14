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

    for orphan_id in orphan_ids:
        cr.execute(
            "UPDATE tax_unit SET company_id = %s WHERE id = %s",
            (company_ids[0], orphan_id),
        )
        for company_id in company_ids[1:]:
            cr.execute(
                """
                INSERT INTO tax_unit (name, value, status, available_date, company_id)
                SELECT name, value, status, available_date, %s
                FROM tax_unit WHERE id = %s
                """,
                (company_id, orphan_id),
            )
