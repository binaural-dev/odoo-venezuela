import logging

from odoo import api, SUPERUSER_ID
from odoo.addons.l10n_ve_base.models.res_partner import DEFAULT_TZ


_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """`res.partner.tz` (delegated to `res.users`) has no static default in
    core Odoo -- it only picks up `context.get('tz')` at creation time, and
    falls back to `False` (server/UTC) when the client didn't send one. This
    caused accounting dates (`account.move.date`,
    `invoice_date_display`, computed via `fields.Date.context_today`) to
    shift to the next day for any user without a timezone set, when
    registering documents late at night local time.

    `ResPartner.tz` (models/res_partner.py) now defaults new users to
    `DEFAULT_TZ` (unless it can derive one from the context or the current
    company), but that only applies to records created after this module
    update -- defaults are evaluated once at `create()`, never
    retroactively. This migration backfills existing users whose tz is
    still empty.

    Scope of the search:
    - `active_test=False`: without it, `res.users.search()` silently skips
      archived users -- notably OdooBot (uid=1) and the Public user, which
      are exactly the accounts that run crons, background jobs and portal
      requests without an interactive session (and therefore without a
      `tz` in context). These are the accounts most likely to trigger the
      original bug, so excluding them would defeat the purpose of the
      backfill.
    - `share = False`: excludes portal/public users. Those are customer
      partners, not internal/system users -- their timezone is not this
      migration's concern, and touching them would be an unwanted side
      effect on customer data.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env["res.users"].with_context(active_test=False).search(
        [("tz", "=", False), ("share", "=", False)]
    )
    if not users:
        return

    users.partner_id.write({"tz": DEFAULT_TZ})

    _logger.info(
        "l10n_ve_base 19.0.1.0.1: backfilled tz='%s' for %d user(s) with no "
        "timezone set. User ids: %s",
        DEFAULT_TZ, len(users), users.ids,
    )
