from datetime import date

from odoo.tests import TransactionCase, tagged

from .common_rates import set_rate


@tagged("post_install", "-at_install", "l10n_ve_accountant")
class TestAccountMoveCreateRateDate(TransactionCase):
    """``account.move.create()``'s own rate-change-logging check
    (l10n_ve_accountant/models/account_move.py) used
    ``move.invoice_date or fields.Date.today()`` to pick the date for its
    ``compute_rate()`` lookup. A non-invoice move (a plain journal entry --
    e.g. the one point_of_sale creates when closing a POS session) never
    has ``invoice_date`` set, so this always fell straight to
    ``fields.Date.today()``, the server's raw clock, completely ignoring
    the move's own ``date`` field, which the real ``_compute_rate()``
    (called right above it) had already resolved correctly.

    This is what actually broke in production: closing a POS session late
    in the Venezuelan evening gave the closing entry the right `date`, but
    this redundant check still demanded a rate for a different day (the
    server's "today") and raised, blocking the close -- regardless of the
    cashier's own timezone, since this check never looked at any tz at
    all, only at the server's clock.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.company.currency_id = self.ves
        self.company.foreign_currency_id = self.usd
        self.journal = self.env["account.journal"].create({
            "name": "TZ Journal",
            "type": "general",
            "code": "TZJ",
        })

    def test_create_uses_move_date_not_servers_today(self):
        """A rate exists only for 2026-10-26 (the move's own `date`); none
        exists for "today" (fields.Date.today(), the real server date in
        this environment). Creating a plain journal entry dated 2026-10-26
        must not demand a rate for today instead."""
        set_rate(self.env, self.usd, date(2026, 10, 26), self.company, 1.0 / 380.0)

        move = self.env["account.move"].create({
            "journal_id": self.journal.id,
            "date": date(2026, 10, 26),
            "move_type": "entry",
        })

        self.assertNotEqual(move.foreign_rate, 0.0)
