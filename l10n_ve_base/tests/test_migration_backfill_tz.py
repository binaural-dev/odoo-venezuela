import importlib.util
import os

from odoo.tests import TransactionCase, tagged

_MODULE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MIGRATION_FILE = os.path.join(
    _MODULE_ROOT, "migrations", "19.0.1.0.1", "post-migrate.py"
)


def _load_migration():
    """`migrations/19.0.1.0.1/` isn't a valid Python package name (dots),
    so it can't be reached with a normal import -- load the script straight
    from its file path instead."""
    spec = importlib.util.spec_from_file_location(
        "l10n_ve_base_post_migrate_19_0_1_0_1", _MIGRATION_FILE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install", "l10n_ve_base")
class TestMigrationBackfillTz(TransactionCase):
    """migrations/19.0.1.0.1/post-migrate.py backfills the timezone of
    existing users whose `tz` is empty -- the model-level default
    (res_partner.py) only reaches records created after the module update,
    so this script is what fixes the ones that already exist.

    No demo/fixture data is used: the users involved are created inline,
    each explicitly forced to a known `tz` (including `False`) so the test
    doesn't depend on -- or get masked by -- the create-time default itself.
    """

    def setUp(self):
        super().setUp()
        self.migration = _load_migration()

    def _create_user(self, login, tz):
        return self.env["res.users"].create({
            "name": login,
            "login": login,
            "email": f"{login}@example.com",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            # Explicit value: bypasses the create-time default entirely, so
            # this reproduces a user left over from before that default
            # existed, regardless of what the default itself would pick.
            "tz": tz,
        })

    def test_backfills_users_with_empty_tz(self):
        user = self._create_user("test_l10n_ve_base_migrate_empty", tz=False)
        self.assertFalse(user.tz)

        self.migration.migrate(self.env.cr, "19.0.1.0.1")

        self.assertEqual(user.tz, "America/Caracas")

    def test_does_not_touch_users_with_tz_already_set(self):
        user = self._create_user("test_l10n_ve_base_migrate_set", tz="UTC")

        self.migration.migrate(self.env.cr, "19.0.1.0.1")

        self.assertEqual(user.tz, "UTC")

    def test_backfills_archived_users_with_empty_tz(self):
        """`res.users.search()` uses `active_test=True` by default and would
        silently skip archived accounts -- notably OdooBot (uid=1) and the
        Public user, which run crons/portal requests without an interactive
        session and are exactly the accounts most likely to trigger the
        original bug. The migration must reach them too."""
        user = self._create_user("test_l10n_ve_base_migrate_archived", tz=False)
        # Archiving the user is enough to drop out of the default
        # `active_test=True` search -- no need to (and some enterprise
        # modules like `web_map` won't let us) archive the partner directly
        # while it's still linked to an active user.
        user.active = False
        self.assertFalse(user.tz)

        self.migration.migrate(self.env.cr, "19.0.1.0.1")

        self.assertEqual(
            user.with_context(active_test=False).tz, "America/Caracas"
        )

    def test_noop_when_no_user_has_empty_tz(self):
        """Guard against the early-return path raising or misbehaving when
        there's nothing to backfill. The migration's domain now always
        includes system/archived users (`active_test=False`), so the noop
        state can't just rely on "no users created in this test" -- it must
        be forced explicitly, otherwise pre-existing system users (e.g.
        OdooBot) with an empty `tz` would make this test backfill something
        anyway."""
        self._create_user("test_l10n_ve_base_migrate_noop", tz="UTC")
        self.env["res.users"].with_context(active_test=False).search(
            [("tz", "=", False), ("share", "=", False)]
        ).partner_id.write({"tz": "UTC"})

        self.migration.migrate(self.env.cr, "19.0.1.0.1")
