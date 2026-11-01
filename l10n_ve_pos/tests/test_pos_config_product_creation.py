from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_pos")
class TestPosConfigProductCreation(TransactionCase):
    """TA-85594: "Allow product creation" (``allow_product_creation_in_pos``)
    decides whether the PoS shows the option to create products."""

    def test_new_config_does_not_allow_product_creation(self):
        # Off by default: a register creates products only if it is enabled.
        config = self.env["pos.config"].create({"name": "Caja creación"})
        self.assertFalse(config.allow_product_creation_in_pos)

    def test_settings_write_the_config(self):
        config = self.env["pos.config"].create({"name": "Caja ajustes"})
        self.env["res.config.settings"].create(
            {
                "pos_config_id": config.id,
                "allow_product_creation_in_pos": True,
            }
        )
        self.assertTrue(config.allow_product_creation_in_pos)

    def test_field_in_settings_view(self):
        arch = self.env.ref("l10n_ve_pos.res_config_settings_l10n_ve_pos").arch_db
        self.assertIn("allow_product_creation_in_pos", arch)
