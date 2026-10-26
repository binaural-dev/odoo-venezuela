from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAuditlogLogGroupRestriction(TransactionCase):
    """Eliminar un registro de auditoría (auditlog.log) solo debe estar
    permitido a los usuarios de l10n_ve_accountant.group_fiscal_config_support."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_support = cls.env.ref("l10n_ve_accountant.group_fiscal_config_support")
        # group_auditlog_manager es quien tiene el permiso ACL base de borrar
        # auditlog.log (auditlog/security/ir.model.access.csv); sin él, el
        # unlink() de este test fallaría por AccessError antes de llegar
        # siquiera a la regla de negocio de group_fiscal_config_support.
        cls.group_auditlog_manager = cls.env.ref("auditlog.group_auditlog_manager")
        cls.support_user = cls.env["res.users"].create({
            "name": "Fiscal Support User",
            "login": "fiscal_support_auditlog_user_test",
            "email": "fiscal_support_auditlog_user_test@example.com",
            "group_ids": [(4, cls.group_support.id), (4, cls.group_auditlog_manager.id)],
        })
        cls.manager_only_user = cls.env["res.users"].create({
            "name": "Auditlog Manager Without Fiscal Support",
            "login": "auditlog_manager_only_user_test",
            "email": "auditlog_manager_only_user_test@example.com",
            "group_ids": [(4, cls.group_auditlog_manager.id)],
        })
        cls.model_res_partner = cls.env.ref("base.model_res_partner")

    def _create_log(self):
        return self.env["auditlog.log"].create({
            "model_id": self.model_res_partner.id,
            "method": "create",
        })

    def test_unlink_raises_without_fiscal_support_group(self):
        log = self._create_log()
        with self.assertRaises(UserError):
            log.with_user(self.manager_only_user).unlink()
        self.assertTrue(log.exists())

    def test_unlink_allowed_with_fiscal_support_group(self):
        log = self._create_log()
        log.with_user(self.support_user).unlink()
        self.assertFalse(log.exists())
