"""Elimina price_unit_ves/ves_currency_id, reemplazados por
account.move.company_currency_line_totals. El ORM ya no declara estos
campos; sin este script sus columnas quedarian huerfanas en la tabla.
"""


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE account_move_line "
        "DROP COLUMN IF EXISTS price_unit_ves, "
        "DROP COLUMN IF EXISTS ves_currency_id"
    )
