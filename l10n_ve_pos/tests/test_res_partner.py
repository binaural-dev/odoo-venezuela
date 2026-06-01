from odoo.tests.common import TransactionCase
from odoo.tests import tagged
from odoo.exceptions import MissingError
from unittest.mock import patch


@tagged("post_install", "-at_install", "res_partner")
class ResPartnerTest(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Test Partner",
            "vat": "12345678",
        })

    def test_01_pos_user_group_xml_ids_computed(self):
        self.partner._compute_pos_user_group_xml_ids()
        self.assertTrue(
            self.partner.pos_user_group_xml_ids is False
            or isinstance(self.partner.pos_user_group_xml_ids, list)
        )

    def _patch_parent(self, model_name, method_name, **kwargs):
        model_class = self.env[model_name].__class__
        for klass in model_class.__mro__[1:]:
            if method_name in klass.__dict__:
                return patch.object(klass, method_name, **kwargs)
        return patch.object(model_class.__bases__[0], method_name, **kwargs)

    def test_02_create_from_ui_with_city_id(self):
        partner_data = {
            "name": "UI Partner",
            "city_id": "123",
        }
        with self._patch_parent("res.partner", "create_from_ui", return_value={"id": 1}):
            result = self.env["res.partner"].create_from_ui(partner_data)
            self.assertEqual(result, {"id": 1})

    def test_03_create_from_ui_without_city_id(self):
        partner_data = {
            "name": "UI Partner No City",
        }
        with self._patch_parent("res.partner", "create_from_ui", return_value={"id": 1}):
            result = self.env["res.partner"].create_from_ui(partner_data)
            self.assertEqual(result, {"id": 1})

    def test_04_load_pos_data_fields(self):
        config = self.env["pos.config"].create({
            "name": "Test Config",
            "company_id": self.env.company.id,
        })
        fields = self.env["res.partner"]._load_pos_data_fields(config.id)
        self.assertIn("city_id", fields)
        self.assertIn("pos_user_group_xml_ids", fields)

    def test_05_get_default_name_by_vat_success(self):
        with patch(
            "odoo.addons.l10n_ve_pos.models.res_partner.binaural_cne_query.get_default_name_by_vat"
        ) as mock_cne:
            mock_cne.return_value = ("John Doe", True)
            name = self.partner.get_default_name_by_vat_param("V", "12345678")
            self.assertEqual(name, "John Doe")

    def test_06_get_default_name_by_vat_failure(self):
        with patch(
            "odoo.addons.l10n_ve_pos.models.res_partner.binaural_cne_query.get_default_name_by_vat"
        ) as mock_cne:
            mock_cne.return_value = ("", False)
            with self.assertRaises(MissingError):
                self.partner.get_default_name_by_vat_param("V", "12345678")
