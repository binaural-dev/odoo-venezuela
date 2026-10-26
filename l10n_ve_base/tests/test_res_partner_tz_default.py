from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_base")
class TestResPartnerTzDefault(TransactionCase):
    """`res.partner.tz` (models/res_partner.py) must default new records to
    'America/Caracas' only when the creation context doesn't already carry a
    tz (e.g. the browser-detected one) -- see l10n_ve_base/models/res_partner.py.

    No demo/fixture data is used: every record involved is created inline by
    each test.
    """

    def _create_user(self, login, extra_vals=None, context=None):
        vals = {
            "name": login,
            "login": login,
            "email": f"{login}@example.com",
            # Explicit group_ids: passing it skips res.users' own default
            # group assignment, so it must be listed here too.
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        }
        if extra_vals:
            vals.update(extra_vals)
        model = self.env["res.users"]
        if context is not None:
            model = model.with_context(**context)
        return model.create(vals)

    def test_new_user_without_context_tz_gets_default(self):
        """No 'tz' key in vals, no 'tz' key in context -> falls back to the
        module's default instead of False/UTC."""
        user = self._create_user(
            "test_l10n_ve_base_tz_no_context", context={"tz": False}
        )
        self.assertEqual(user.tz, "America/Caracas")

    def test_new_user_respects_context_tz(self):
        """A tz coming from the client (context) must still win over the
        module default -- the override only fills the gap, it doesn't force
        a fixed value."""
        user = self._create_user(
            "test_l10n_ve_base_tz_context",
            context={"tz": "Europe/Madrid"},
        )
        self.assertEqual(user.tz, "Europe/Madrid")

    def test_new_user_respects_explicit_tz_value(self):
        """An explicit 'tz' passed in create() vals must not be overridden
        by the default."""
        user = self._create_user(
            "test_l10n_ve_base_tz_explicit",
            extra_vals={"tz": "UTC"},
            context={"tz": False},
        )
        self.assertEqual(user.tz, "UTC")

    def test_new_partner_without_context_tz_gets_default(self):
        """The field lives on res.partner (res.users delegates to it via
        _inherits), so the default must apply there directly too, not only
        through the res.users form."""
        partner = self.env["res.partner"].with_context(tz=False).create(
            {"name": "Test Partner No Tz Context"}
        )
        self.assertEqual(partner.tz, "America/Caracas")
