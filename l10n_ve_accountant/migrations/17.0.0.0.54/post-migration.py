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
        FROM res_currency c
        INNER JOIN account_move m ON l.move_id = m.id
        INNER JOIN res_company comp ON m.company_id = comp.id
        WHERE comp.currency_foreign_id = c.id
          AND l.foreign_price IS NOT NULL
    """)
    _logger.info("  account_move_line (foreign fields): %s rows updated", cr.rowcount)

    # account_move_line.amount_currency uses move.currency_id
    cr.execute("""
        UPDATE account_move_line l
        SET amount_currency = ROUND(l.amount_currency, c.decimal_places)
        FROM res_currency c
        INNER JOIN account_move m ON l.move_id = m.id
        WHERE m.currency_id = c.id
          AND l.amount_currency IS NOT NULL
          AND ROUND(l.amount_currency, c.decimal_places) != l.amount_currency
    """)
    _logger.info("  account_move_line.amount_currency: %s rows updated", cr.rowcount)

    # account_move.foreign_total_billed uses company.currency_foreign_id
    cr.execute("""
        UPDATE account_move m
        SET foreign_total_billed = ROUND(m.foreign_total_billed, c.decimal_places)
        FROM res_currency c
        INNER JOIN res_company comp ON m.company_id = comp.id
        WHERE comp.currency_foreign_id = c.id
          AND m.foreign_total_billed IS NOT NULL
          AND ROUND(m.foreign_total_billed, c.decimal_places) != m.foreign_total_billed
    """)
    _logger.info("  account_move.foreign_total_billed: %s rows updated", cr.rowcount)

    # account_move.real_portion_amount uses company.currency_id
    cr.execute("""
        UPDATE account_move m
        SET real_portion_amount = ROUND(m.real_portion_amount, c.decimal_places)
        FROM res_currency c
        INNER JOIN res_company comp ON m.company_id = comp.id
        WHERE comp.currency_id = c.id
          AND m.real_portion_amount IS NOT NULL
          AND ROUND(m.real_portion_amount, c.decimal_places) != m.real_portion_amount
    """)
    _logger.info("  account_move.real_portion_amount: %s rows updated", cr.rowcount)

    # account_partial_reconcile.foreign_amount uses company.currency_foreign_id
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET foreign_amount = ROUND(p.foreign_amount, c.decimal_places),
            debit_foreign_amount_currency = ROUND(p.debit_foreign_amount_currency, c.decimal_places),
            credit_foreign_amount_currency = ROUND(p.credit_foreign_amount_currency, c.decimal_places)
        FROM res_currency c
        INNER JOIN account_move_line dml ON p.debit_move_id = dml.id
        INNER JOIN account_move dm ON dml.move_id = dm.id
        INNER JOIN res_company comp ON dm.company_id = comp.id
        WHERE comp.currency_foreign_id = c.id
          AND p.foreign_amount IS NOT NULL
          AND (
            ROUND(p.foreign_amount, c.decimal_places) != p.foreign_amount
            OR ROUND(p.debit_foreign_amount_currency, c.decimal_places) != p.debit_foreign_amount_currency
            OR ROUND(p.credit_foreign_amount_currency, c.decimal_places) != p.credit_foreign_amount_currency
          )
    """)
    _logger.info("  account_partial_reconcile: %s rows updated", cr.rowcount)

    _logger.info("Monetary rounding migration complete")
