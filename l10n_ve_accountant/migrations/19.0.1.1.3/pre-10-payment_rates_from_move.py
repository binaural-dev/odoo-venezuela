"""Create the payment rate columns with the rate of each payment's move, before the ORM recomputes them.

What: when account_payment has no foreign_rate column, creates foreign_currency_id, foreign_rate
    and foreign_inverse_rate and fills them from the payment's journal entry (account_move), which
    already keeps the rate the payment was posted with. Where the move has foreign_rate = 0 but an
    inverse rate, foreign_rate is taken as 1 / foreign_inverse_rate. Where the move has no
    alternate currency, the one of the payment's company is used.

Why: databases of the operativa line (binaural_* base modules, no odoo-venezuela) never had these
    payment fields. In v19 this module declares them stored and computed by _compute_rate, so when
    the ORM creates the columns it recomputes them on every payment through
    res.currency.rate.compute_rate, which looks for a rate dated exactly on the payment date and
    raises otherwise. Any payment on a day without a rate (weekends, holidays) stops the whole
    update: castic_19_operativo had 646 payments on 139 such dates, the first on 2024-03-18
    ("There is no rate assigned for USD on 2024-03-18"). Even where a rate exists, the recompute
    would replace the rate the payment was really posted with by the one in the rate table, and
    compute_rate looks it up in the active company (the main one during the update), not in the
    payment's.

    The ORM does not recompute a stored computed field whose column already exists when the model
    is loaded, so the columns are created here, in pre-.

    It does not depend on the version the module comes from: the operativa databases arrive with
    the binaural_* versions (16.0.x or 17.0.x). On a database of the homologated line, or one
    born in 19, the column already exists and nothing is done.

If it does not run: on an operativa database the update stops in l10n_ve_accountant with
    "There is no rate assigned for USD on <date>" as soon as one payment falls on a day without a
    rate; where it does not stop, every payment gets the rate-table rate instead of its own.

How to revert: restore the database. The moves are only read.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if util.column_exists(cr, "account_payment", "foreign_rate"):
        return

    util.create_column(cr, "account_payment", "foreign_currency_id", "int4")
    util.create_column(cr, "account_payment", "foreign_rate", "numeric")
    util.create_column(cr, "account_payment", "foreign_inverse_rate", "numeric")

    cr.execute(
        """
        UPDATE account_payment p
           SET foreign_currency_id = COALESCE(p.foreign_currency_id, m.foreign_currency_id,
                                              c.foreign_currency_id),
               foreign_rate = CASE
                   WHEN COALESCE(m.foreign_rate, 0) = 0 AND COALESCE(m.foreign_inverse_rate, 0) <> 0
                       THEN 1 / m.foreign_inverse_rate
                   ELSE m.foreign_rate
               END,
               foreign_inverse_rate = m.foreign_inverse_rate
          FROM account_move m
          JOIN res_company c ON c.id = m.company_id
         WHERE m.id = p.move_id
        """
    )
    _logger.info("Payment rates taken from their move on %s payments", cr.rowcount)

    cr.execute(
        """
        UPDATE account_payment p
           SET foreign_currency_id = c.foreign_currency_id
          FROM res_company c
         WHERE c.id = p.company_id
           AND p.foreign_currency_id IS NULL
        """
    )
    cr.execute("SELECT count(*) FROM account_payment WHERE COALESCE(foreign_rate, 0) = 0")
    without_rate = cr.fetchone()[0]
    if without_rate:
        _logger.warning(
            "%s payments have no rate in their move either; they keep foreign_rate = 0", without_rate
        )
