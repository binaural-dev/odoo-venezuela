"""Crea las columnas de jerarquía de combo en account_move_line
(ALTER TABLE condicional) para acelerar la actualización en bases grandes.
"""


def migrate(cr, version):
    columns = [
        ("combo_parent_line_id", "integer"),
        ("combo_root_line_id", "integer"),
        ("combo_tagged", "boolean DEFAULT false"),
        ("combo_item_qty_per_combo", "double precision DEFAULT 1.0"),
    ]
    for col_name, col_type in columns:
        cr.execute(
            f"""
            ALTER TABLE account_move_line
            ADD COLUMN IF NOT EXISTS {col_name} {col_type}
            """
        )
