def migrate(cr, version):
    """See l10n_ve_invoice_digital's migration of the same name -- same
    backfill, for stock.picking (its is_digitalized/tfhka_digitalization_state
    fields are defined in this module instead)."""
    if not version:
        return

    cr.execute("""
        UPDATE stock_picking
        SET tfhka_digitalization_state = 'success'
        WHERE is_digitalized = true
          AND tfhka_digitalization_state = 'none'
    """)
