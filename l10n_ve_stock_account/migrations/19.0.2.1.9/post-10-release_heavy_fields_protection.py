"""Release the protection StockPicking._auto_init pushed for this module's heavy fields.

What: pops the env.transaction.protected layer that stock_picking.py's
_l10n_ve_stock_account_protect_heavy_fields pushed and deliberately left pushed, now that this
module's own data/views have finished loading too. No-op if that method never pushed one this
run (registry attribute _l10n_ve_stock_account_heavy_fields_protected).

Why: a migration script only gets a bare cr, not the model instance; the registry (env.registry)
is what carries the signal from _auto_init to here within the same run. See
_l10n_ve_stock_account_protect_heavy_fields's docstring for why the protection must outlive
_auto_init itself.

Task: <TICKET>
"""

from odoo import SUPERUSER_ID
from odoo.orm.environments import Environment


def migrate(cr, version):
    env = Environment(cr, SUPERUSER_ID, {})
    if not getattr(env.registry, "_l10n_ve_stock_account_heavy_fields_protected", False):
        return
    env.transaction.protected.popmap()
    del env.registry._l10n_ve_stock_account_heavy_fields_protected
