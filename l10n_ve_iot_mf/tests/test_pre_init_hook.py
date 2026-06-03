from unittest.mock import MagicMock
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_iot_mf")
class TestPreInitHook(TransactionCase):

    def test_execute_script_sql_called(self):
        """execute_script_sql debe ejecutar SQL actualizando ir_model_data."""
        mock_env = MagicMock()
        mock_env.execute = MagicMock()

        from .. import execute_script_sql
        execute_script_sql(mock_env, "iot_port_com_")

        mock_env.execute.assert_called_once()
        args, _ = mock_env.execute.call_args
        self.assertIn("UPDATE ir_model_data", args[0])
        self.assertIn("iot_port_com_%", args[3])

    def test_reassign_xml_iot_port_ids_calls_execute(self):
        """reassign_xml_iot_port_ids debe llamar a execute_script_sql con iot_port_com_."""
        mock_env = MagicMock()
        mock_env.execute = MagicMock()

        from .. import reassign_xml_iot_port_ids
        reassign_xml_iot_port_ids(mock_env)

        mock_env.execute.assert_called_once()
        args, _ = mock_env.execute.call_args
        self.assertIn("iot_port_com_%", args[3])
