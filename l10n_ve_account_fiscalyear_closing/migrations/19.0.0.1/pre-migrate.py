def migrate(cr, version):
    cr.execute(
        "ALTER TABLE account_fiscalyear_closing "
        "DROP CONSTRAINT IF EXISTS account_fiscalyear_closing_year_company_uniq"
    )
