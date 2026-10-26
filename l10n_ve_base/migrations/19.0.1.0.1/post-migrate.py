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
      archived users -- notably OdooBot (uid=1) and the Public user(s),
      which are exactly the accounts that run crons, background jobs and
      public/portal requests without an interactive session (and
      therefore without a `tz` in context). These are the accounts most
      likely to trigger the original bug, so excluding them would defeat
      the purpose of the backfill.
    - `share = False` OR member of `base.group_public`: `share = True`
      covers both customer portal users and the Public user(s) (one per
      company), but only the portal users are actual customer partners --
      the Public user is a system account, not a customer's identity.
      Filtering solely by `share = False` (an earlier version of this
      migration did) excluded the Public user too, which is exactly the
      actor reported in TI-15211 (documents created through the public/
      digitization flow). Matching `base.group_public` on top of
      `share = False` reaches the Public user(s) without touching portal
      users, whose timezone is customer data and not this migration's
      concern.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    group_public = env.ref("base.group_public", raise_if_not_found=False)
    if group_public:
        domain = [
            "&", ("tz", "=", False),
            "|", ("group_ids", "in", group_public.id), ("share", "=", False),
        ]
    else:
        domain = [("tz", "=", False), ("share", "=", False)]
    users = env["res.users"].with_context(active_test=False).search(domain)
    if not users:
        return

    users.partner_id.write({"tz": DEFAULT_TZ})

    _logger.info(
        "l10n_ve_base 19.0.1.0.1: backfilled tz='%s' for %d user(s) with no "
        "timezone set. User ids: %s",
        DEFAULT_TZ, len(users), users.ids,
    )
