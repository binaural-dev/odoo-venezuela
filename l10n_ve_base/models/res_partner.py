from odoo import fields, models
from odoo.tools import sql

# Last-resort fallback used only when neither the creation context nor the
# current company's partner provide a timezone. Kept as a module-level
# constant so the backfill migration (migrations/19.0.1.0.1/post-migrate.py)
# can import the exact same value instead of duplicating the literal.
DEFAULT_TZ = "America/Caracas"


class ResPartner(models.Model):
    _inherit = "res.partner"

    tz = fields.Selection(
        default=lambda self: self.env.context.get("tz")
        or self.env.company.partner_id.tz
        or DEFAULT_TZ,
    )

    def _auto_init(self):
        """
        Leave the foreign key of ``city_id`` alone while ``l10n_ve_location`` is not loaded (R-49).

        Odoo 20 installs ``base_address_extended`` with ``account`` (through ``portal``), and it
        defines ``city_id`` towards ``res.city``. ``l10n_ve_location`` defines the same field
        towards ``res.country.city`` and loads much later. When a module loaded in between updates
        ``res.partner`` (this one, ``mail``, ``contacts``...), the half-loaded registry asks for
        the key towards ``res_city``: Odoo drops the one towards ``res_country_city`` and the new
        one fails with the cities the contacts already have, which stops the update. While the
        cities of the localization exist, the key in the database is the right one: it is kept,
        and ``l10n_ve_location`` checks it when it loads.

        Since 20.0.1.0.1 ``l10n_ve_location`` moves its cities to ``res.city`` and the key points
        there: this only acts on a database whose cities have not been moved yet, until
        ``l10n_ve_location`` is updated (R-49).
        """
        result = super()._auto_init()
        field = self._fields.get("city_id")
        if field is not None and field.comodel_name == "res.city" and self._city_key_points_to_localization():
            # The key is queued with post_init, after every _auto_init: drop it after that.
            self.pool.post_init(self._keep_localization_city_foreign_key)
        return result

    def _city_key_points_to_localization(self):
        """The key of city_id in the database still points to the old cities of l10n_ve_location."""
        if not sql.table_exists(self.env.cr, "res_country_city"):
            return False
        self.env.cr.execute(
            """
            SELECT 1 FROM pg_constraint fk
            JOIN pg_attribute a ON a.attrelid = fk.conrelid AND a.attnum = fk.conkey[1]
            WHERE fk.contype = 'f' AND fk.conrelid = 'res_partner'::regclass
              AND a.attname = 'city_id' AND fk.confrelid = 'res_country_city'::regclass
            """
        )
        return bool(self.env.cr.fetchone())

    def _keep_localization_city_foreign_key(self):
        self.pool._foreign_keys.pop((self._table, "city_id"), None)
