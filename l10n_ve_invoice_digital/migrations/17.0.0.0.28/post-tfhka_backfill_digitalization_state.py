def migrate(cr, version):
    """Invoices digitalized before the digitalization queue's state machine
    existed have ``is_digitalized = true`` but ``tfhka_digitalization_state``
    still at its default ``'none'`` -- the field didn't exist yet when they
    were originally digitalized. Backfill them to ``'success'`` so they're
    consistent with invoices digitalized since (the view hides the status
    badge once it's ``'success'``, and the halt-on-error queue guard only
    looks at ``tfhka_digitalization_state``).
    """
    if not version:
        return

    cr.execute("""
        UPDATE account_move
        SET tfhka_digitalization_state = 'success'
        WHERE is_digitalized = true
          AND tfhka_digitalization_state = 'none'
    """)
