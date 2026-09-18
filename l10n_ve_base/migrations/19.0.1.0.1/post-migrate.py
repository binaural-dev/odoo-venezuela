import logging

from odoo import api, SUPERUSER_ID


_logger = logging.getLogger(__name__)

DEFAULT_TZ = "America/Caracas"


def migrate(cr, version):
    """`res.partner.tz` (delegated to `res.users`) has no static default in
    core Odoo -- it only picks up `context.get('tz')` at creation time, and
    falls back to `False` (server/UTC) when the client didn't send one. This
    caused accounting dates (`account.move.date`,
    `invoice_date_display`, computed via `fields.Date.context_today`) to
    shift to the next day for any user without a timezone set, when
    registering documents late at night local time.

    `ResPartner.tz` (models/res_partner.py) now defaults new users to
    `America/Caracas`, but that only applies to records created after this
    module update -- defaults are evaluated once at `create()`, never
    retroactively. This migration backfills existing users whose tz is
    still empty.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env["res.users"].search([("tz", "=", False)])
    if not users:
        return

    users.partner_id.write({"tz": DEFAULT_TZ})

    _logger.info(
        "l10n_ve_base 19.0.1.0.1: backfilled tz='%s' for %d user(s) with no "
        "timezone set. User ids: %s",
        DEFAULT_TZ, len(users), users.ids,
    )
