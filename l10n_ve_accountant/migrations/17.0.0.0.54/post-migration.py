import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "Forzando debit/credit_amount_currency = amount en account_partial_reconcile "
        "cuando la moneda de la reconciliacion es la moneda de la compania"
    )

    # Lado debito: cuando debit_currency_id es la moneda de la compania, el monto en esa
    # moneda (debit_amount_currency) tiene que ser identico a 'amount' (ya en moneda de
    # compania). El _convert() sin redondear de l10n_ve_rate dejaba estos dos valores
    # divergir: 'amount' se guardaba con precision cruda y 'debit_amount_currency' con
    # un redondeo distinto, dejando residuos fantasma de centimos (ticket #16187).
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET debit_amount_currency = p.amount
        FROM account_move_line dml, account_move dm, res_company comp
        WHERE p.debit_move_id = dml.id
          AND dml.move_id = dm.id
          AND dm.company_id = comp.id
          AND p.debit_currency_id = comp.currency_id
          AND p.debit_amount_currency IS DISTINCT FROM p.amount
        RETURNING p.debit_move_id, p.credit_move_id
    """)
    affected_line_ids = {row[0] for row in cr.fetchall()}
    _logger.info("  account_partial_reconcile.debit_amount_currency: %s rows updated", len(affected_line_ids))

    # Lado credito: mismo caso, cuando credit_currency_id es la moneda de la compania.
    cr.execute("""
        UPDATE account_partial_reconcile p
        SET credit_amount_currency = p.amount
        FROM account_move_line cml, account_move cm, res_company comp
        WHERE p.credit_move_id = cml.id
          AND cml.move_id = cm.id
          AND cm.company_id = comp.id
          AND p.credit_currency_id = comp.currency_id
          AND p.credit_amount_currency IS DISTINCT FROM p.amount
        RETURNING p.debit_move_id, p.credit_move_id
    """)
    for debit_id, credit_id in cr.fetchall():
        affected_line_ids.add(debit_id)
        affected_line_ids.add(credit_id)
    _logger.info("  account_partial_reconcile.credit_amount_currency: %s lineas afectadas en total", len(affected_line_ids))

    if not affected_line_ids:
        _logger.info("Correccion de amount_currency en reconciliaciones de moneda unica completa (nada que recomputar)")
        return

    # amount_residual / amount_residual_currency / reconciled son campos almacenados en
    # account.move.line que se calculan sumando estas mismas filas de
    # account_partial_reconcile: como las actualizamos por SQL crudo, no se recomputan
    # solos. Se fuerza el recompute via ORM para que la columna en BD quede consistente.
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["account.move.line"].browse(list(affected_line_ids)).exists()
    lines._compute_amount_residual()
    lines.flush_recordset(["amount_residual", "amount_residual_currency", "reconciled"])
    _logger.info("  account_move_line: %s lineas recomputadas (amount_residual/reconciled)", len(lines))

    moves = lines.move_id
    moves._compute_payment_state()
    moves.flush_recordset(["payment_state"])
    _logger.info("  account_move: %s facturas recomputadas (payment_state)", len(moves))

    _logger.info("Correccion de amount_currency en reconciliaciones de moneda unica completa")
