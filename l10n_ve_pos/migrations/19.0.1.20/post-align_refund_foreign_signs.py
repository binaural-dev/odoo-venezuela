import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Align the foreign amounts of the orders of sessions that are still
    open (task 83148, H1).

    Before this version the POS stored refunds with ``foreign_amount`` and
    ``foreign_amount_total`` positive next to a negative ``amount``. The fix
    corrects new orders, but a refund already stored in a session that is
    open while the module is updated would still be added as cash coming in
    at close, and the close would crash on
    ``account_move_line_check_amount_currency_balance_sign`` when the net of
    a foreign cash method is a refund.

    Closed sessions are left untouched: their moves are already posted.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env["pos.order"].search([("session_id.state", "!=", "closed")])
    orders._align_foreign_signs()
    _logger.info("l10n_ve_pos: foreign signs aligned on %s orders of open sessions", len(orders))
