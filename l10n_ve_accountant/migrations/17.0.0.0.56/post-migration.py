import logging
from contextlib import contextmanager
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

PARTIAL_FIELDS = [
    'foreign_amount',
    'debit_foreign_amount_currency',
    'credit_foreign_amount_currency',
]


def _is_period_unlocked(move, company):
    if not company.tax_lock_date:
        return True
    return move.date > company.tax_lock_date


def _is_reconciled(move):
    lines = move.line_ids.filtered(lambda l: l.account_id.reconcile)
    for line in lines:
        if line.full_reconcile_id or line.matched_debit_ids or line.matched_credit_ids:
            return True
    return False


def _do_sql_rounding(cr, fc_id, precision, state_filter):
    """Round foreign monetary fields via SQL (reliable, no ORM flush issues)."""
    # account_move_line foreign_* fields
    cr.execute("""
        UPDATE account_move_line l
        SET foreign_price = ROUND(l.foreign_price, %(prec)s),
            foreign_subtotal = ROUND(l.foreign_subtotal, %(prec)s),
            foreign_price_total = ROUND(l.foreign_price_total, %(prec)s),
            foreign_debit = ROUND(l.foreign_debit, %(prec)s),
            foreign_credit = ROUND(l.foreign_credit, %(prec)s),
            foreign_balance = ROUND(l.foreign_balance, %(prec)s),
            foreign_debit_adjustment = ROUND(l.foreign_debit_adjustment, %(prec)s),
            foreign_credit_adjustment = ROUND(l.foreign_credit_adjustment, %(prec)s),
            foreign_amount_residual = ROUND(l.foreign_amount_residual, %(prec)s),
            foreign_amount_residual_currency = ROUND(l.foreign_amount_residual_currency, %(prec)s)
        FROM account_move m
        WHERE l.move_id = m.id
          AND m.state IN %(states)s
          AND (l.foreign_price IS NOT NULL OR l.foreign_debit IS NOT NULL OR l.foreign_credit IS NOT NULL)
          AND m.move_type IN ('out_invoice','out_refund','in_invoice','in_refund','out_receipt','in_receipt','entry')
    """, {'prec': precision, 'states': state_filter})
    _logger.info("    SQL foreign_* lines: %s rows updated", cr.rowcount)

    # account_move foreign_total_billed
    cr.execute("""
        UPDATE account_move m
        SET foreign_total_billed = ROUND(foreign_total_billed, %(prec)s)
        FROM res_company c
        WHERE m.company_id = c.id
          AND c.currency_foreign_id = %(fc_id)s
          AND m.state IN %(states)s
          AND m.foreign_total_billed IS NOT NULL
          AND m.move_type IN ('out_invoice','out_refund','in_invoice','in_refund','out_receipt','in_receipt')
    """, {'prec': precision, 'fc_id': fc_id, 'states': state_filter})
    _logger.info("    SQL foreign_total_billed: %s rows updated", cr.rowcount)

    # amount_currency (uses move's own currency precision, not foreign)
    cr.execute("""
        UPDATE account_move_line l
        SET amount_currency = ROUND(l.amount_currency, c.decimal_places)
        FROM res_currency c, account_move m
        WHERE l.move_id = m.id
          AND m.currency_id = c.id
          AND l.amount_currency IS NOT NULL
          AND ROUND(l.amount_currency, c.decimal_places) != l.amount_currency
          AND m.state IN %(states)s
          AND m.move_type IN ('out_invoice','out_refund','in_invoice','in_refund','out_receipt','in_receipt','entry')
    """, {'states': state_filter})
    _logger.info("    SQL amount_currency: %s rows updated", cr.rowcount)

    # account_partial_reconcile
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET foreign_amount = ROUND(p.foreign_amount, %(prec)s),
            debit_foreign_amount_currency = ROUND(p.debit_foreign_amount_currency, %(prec_fc)s),
            credit_foreign_amount_currency = ROUND(p.credit_foreign_amount_currency, %(prec_fc)s)
        FROM account_move_line dml, account_move dm, res_company c
        WHERE p.debit_move_id = dml.id
          AND dml.move_id = dm.id
          AND dm.company_id = c.id
          AND c.currency_foreign_id = %(fc_id)s
          AND dm.state IN %(states)s
          AND p.foreign_amount IS NOT NULL
    """, {'prec': precision, 'prec_fc': precision, 'fc_id': fc_id, 'states': state_filter})
    _logger.info("    SQL partial_reconcile: %s rows updated", cr.rowcount)


def _fix_draft_real_portion(move, company):
    """Trigger real_portion ORM chain for draft invoices only.
    Uses a savepoint so that if any ORM operation fails (e.g. missing columns
    from other modules), the transaction is not aborted and SQL can continue.
    """
    with move.env.cr.savepoint():
        move.write({
            'manually_set_rate': True,
            'foreign_inverse_rate': move.foreign_inverse_rate,
        })

        move._distribute_final_real_portion(move)
        move._compute_foreign_tax_balance(move)
        move._distribute_foreign_pt_residual(move)
        move._compute_foreign_total_billed()
        move.env.flush_all()


def migrate(cr, version):
    _logger.info("Rounding Monetary values via SQL + ORM real_portion chain")

    env = api.Environment(cr, SUPERUSER_ID, {})

    companies = env['res.company'].search([
        ('currency_foreign_id', '!=', False),
    ])
    _logger.info("Companies with foreign currency: %s", len(companies))

    USD_NAME = 'USD'
    VEF_NAMES = ('VEF', 'VES', 'VED')

    move_types = (
        'out_invoice', 'out_refund',
        'in_invoice', 'in_refund',
        'out_receipt', 'in_receipt',
        'entry',
    )

    for company in companies:
        fc = company.currency_foreign_id
        if not fc:
            continue
        if not company.currency_id or company.currency_id == fc:
            continue

        fc_name = fc.name.upper()
        fc_precision = fc.decimal_places

        if fc_name == USD_NAME:
            log_tag = 'base=VEF (full: draft+posted)'
            process_posted = True
        elif fc_name in VEF_NAMES:
            log_tag = 'base=USD (draft only)'
            process_posted = False
        else:
            _logger.info(
                "  %s: foreign=%s no es USD ni VEF, se omite",
                company.name, fc_name,
            )
            continue

        _logger.info("  %s (base=%s, foreign=%s): %s",
                     company.name, company.currency_id.name, fc_name, log_tag)

        # ---- DRAFT real_portion chain (ORM, only for invoices) ----
        draft_domain = [
            ('company_id', '=', company.id),
            ('state', '=', 'draft'),
            ('move_type', 'in', move_types),
            '|',
            ('currency_id', '!=', company.currency_id.id),
            ('foreign_inverse_rate', '>', 0),
        ]
        draft_moves = env['account.move'].search(draft_domain)

        for move in draft_moves:
            if not _is_period_unlocked(move, company):
                continue
            try:
                _fix_draft_real_portion(move, company)
                _logger.info("    Draft %s: ORM chain OK", move.name)
            except Exception as e:
                _logger.error("    Draft %s: ORM ERROR: %s", move.name, e)

        # ---- SQL rounding for draft (reliable) ----
        _logger.info("    Draft SQL rounding...")
        _do_sql_rounding(cr, fc.id, fc_precision, ('draft',))

        # ---- POSTED SQL rounding (only VEF base) ----
        if process_posted:
            _logger.info("    Posted SQL rounding...")
            _do_sql_rounding(cr, fc.id, fc_precision, ('posted',))

    _logger.info("Monetary rounding migration complete")
