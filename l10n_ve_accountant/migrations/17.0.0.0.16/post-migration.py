
def migrate(cr, version):
    """
    Script de migración para eliminar la restricción 'unique_name' de la tabla 'account_move'.
    """
    cr.execute("""
        ALTER TABLE account_move
        DROP CONSTRAINT IF EXISTS unique_name;
    """)