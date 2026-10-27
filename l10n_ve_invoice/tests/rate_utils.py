"""Helpers to seed ``res.currency.rate`` rows from tests.

``l10n_ve_rate`` resolves the rate for the *exact* document date and
``account.move.create()`` (``l10n_ve_accountant``) looks it up for every
move that has a foreign currency, raising ``UserError`` when no rate is
configured for that date. Test fixtures therefore have to seed one rate per
currency and date they use; relying on an older rate (as the pre-19.0
backward-looking lookup allowed) no longer works.
"""

from odoo import fields
from odoo.addons.l10n_ve_accountant.tests.common_rates import set_rate


def seed_rate(env, company, currency, rate_date=None, rate=38.0):
    """Seed ``currency``'s rate for ``rate_date`` in ``company``.

    ``rate`` is the value the user sees (``foreign_rate``): ``set_rate``
    stores it as ``inverse_company_rate``, which is exactly the field
    ``l10n_ve_rate.compute_rate`` returns as ``foreign_rate`` for any
    currency that differs from the company currency.

    Returns the created/updated ``res.currency.rate`` record.
    """
    return set_rate(
        env, currency, rate_date or fields.Date.today(), company, rate
    )
