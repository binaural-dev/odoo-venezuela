def migrate(cr, version):
    """Backfills invoices that were left in 'none' because their journal
    never had digital invoicing enabled, in companies that do use TFHKA --
    same criterion as ``account.move._tfhka_should_mark_not_applicable()``.
    Without this, existing data stays indistinguishable from "not posted
    yet" while only newly-posted invoices get the new 'not_applicable'
    state going forward.

    Applies regardless of ``digitalization_with_payment_tfhka``: that mode
    only changes how an eligible move gets enqueued, it doesn't bypass the
    digital-journal requirement (the manual "Generate Digital Invoice"
    button is hidden without one too -- see ``_compute_invisible_check``).

    Only account.move: account.retention and stock.picking have their own,
    different non-eligibility criteria and don't gain this state at all
    (see ``account.move._tfhka_should_mark_not_applicable``).
    """
    if not version:
        return

    cr.execute("""
        UPDATE account_move am
        SET tfhka_digitalization_state = 'not_applicable'
        FROM account_journal aj, res_company rc
        WHERE am.journal_id = aj.id
          AND am.company_id = rc.id
          AND am.tfhka_digitalization_state = 'none'
          AND am.move_type IN ('out_invoice', 'out_refund')
          AND rc.invoice_digital_tfhka = true
          AND COALESCE(aj.digital_invoice, false) = false
    """)
