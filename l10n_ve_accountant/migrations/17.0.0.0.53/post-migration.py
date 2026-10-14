import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("Rounding Monetary values to currency decimal_places (post-fields.py removal)")

    # account_move_line: foreign_* fields using company.currency_foreign_id
    cr.execute("""
        UPDATE account_move_line l
        SET foreign_price = ROUND(l.foreign_price, c.decimal_places),
            foreign_subtotal = ROUND(l.foreign_subtotal, c.decimal_places),
            foreign_price_total = ROUND(l.foreign_price_total, c.decimal_places),
            foreign_debit = ROUND(l.foreign_debit, c.decimal_places),
            foreign_credit = ROUND(l.foreign_credit, c.decimal_places),
            foreign_balance = ROUND(l.foreign_balance, c.decimal_places),
            foreign_debit_adjustment = ROUND(l.foreign_debit_adjustment, c.decimal_places),
            foreign_credit_adjustment = ROUND(l.foreign_credit_adjustment, c.decimal_places),
            foreign_amount_residual = ROUND(l.foreign_amount_residual, c.decimal_places),
            foreign_amount_residual_currency = ROUND(l.foreign_amount_residual_currency, c.decimal_places)
        FROM account_move m, res_company comp, res_currency c
        WHERE l.move_id = m.id
          AND m.company_id = comp.id
          AND comp.currency_foreign_id = c.id
          AND l.foreign_balance IS NOT NULL
    """)
    _logger.info("  account_move_line (foreign fields): %s rows updated", cr.rowcount)

    # account_move_line.amount_currency uses move.currency_id
    cr.execute("""
        UPDATE account_move_line l
        SET amount_currency = ROUND(l.amount_currency, c.decimal_places)
        FROM account_move m, res_currency c
        WHERE l.move_id = m.id
          AND m.currency_id = c.id
          AND l.amount_currency IS NOT NULL
          AND ROUND(l.amount_currency, c.decimal_places) != l.amount_currency
    """)
    _logger.info("  account_move_line.amount_currency: %s rows updated", cr.rowcount)

    # account_move.foreign_total_billed uses company.currency_foreign_id
    cr.execute("""
        UPDATE account_move m
        SET foreign_total_billed = ROUND(m.foreign_total_billed, c.decimal_places)
        FROM res_company comp, res_currency c
        WHERE m.company_id = comp.id
          AND comp.currency_foreign_id = c.id
          AND m.foreign_total_billed IS NOT NULL
          AND ROUND(m.foreign_total_billed, c.decimal_places) != m.foreign_total_billed
    """)
    _logger.info("  account_move.foreign_total_billed: %s rows updated", cr.rowcount)

    # account_partial_reconcile.foreign_amount uses the debit side's company.currency_foreign_id
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET foreign_amount = ROUND(p.foreign_amount, c.decimal_places),
            debit_foreign_amount_currency = ROUND(p.debit_foreign_amount_currency, c.decimal_places),
            credit_foreign_amount_currency = ROUND(p.credit_foreign_amount_currency, c.decimal_places)
        FROM account_move_line dml, account_move dm, res_company comp, res_currency c
        WHERE p.debit_move_id = dml.id
          AND dml.move_id = dm.id
          AND dm.company_id = comp.id
          AND comp.currency_foreign_id = c.id
          AND p.foreign_amount IS NOT NULL
          AND (
            ROUND(p.foreign_amount, c.decimal_places) != p.foreign_amount
            OR ROUND(p.debit_foreign_amount_currency, c.decimal_places) != p.debit_foreign_amount_currency
            OR ROUND(p.credit_foreign_amount_currency, c.decimal_places) != p.credit_foreign_amount_currency
          )
    """)
    _logger.info("  account_partial_reconcile: %s rows updated", cr.rowcount)

    _logger.info("Monetary rounding migration complete")
