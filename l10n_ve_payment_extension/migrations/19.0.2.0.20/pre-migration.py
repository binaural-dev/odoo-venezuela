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
    cr.execute("""
        UPDATE tax_unit
        SET company_id = 1
        WHERE company_id IS NULL
    """)
