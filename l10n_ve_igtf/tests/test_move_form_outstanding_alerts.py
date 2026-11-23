from odoo.tests import TransactionCase, tagged

# Fragmento del `invisible` del core que identifica el aviso de pendientes de cada tipo de documento.
OUTSTANDING_ALERT_MOVE_TYPES = {
    "out_invoice": "move_type not in ('out_invoice', 'out_receipt')",
    "in_invoice": "move_type not in ('in_invoice', 'in_receipt')",
    "out_refund": "move_type != 'out_refund'",
    "in_refund": "move_type != 'in_refund'",
}


@tagged("l10n_ve_igtf", "-at_install", "post_install")
class TestMoveFormOutstandingAlerts(TransactionCase):
    """El formulario de la factura DEBE mostrar un único aviso de pendientes por tipo de documento, y que
    sea el de IGTF (créditos/débitos y anticipos), aunque otros módulos agreguen avisos `alert-info`
    antes. Ticket 16602: con los reemplazos por posición, los avisos de tasa de compra/venta corrían
    las posiciones y el aviso de pendientes salía duplicado."""

    def _outstanding_alerts(self):
        """Avisos de pendientes del arch combinado de `account.view_move_form`, agrupados por tipo."""
        arch = self.env.ref("account.view_move_form")._get_combined_arch()
        alerts = {move_type: [] for move_type in OUTSTANDING_ALERT_MOVE_TYPES}
        for div in arch.xpath(
            "//div[hasclass('alert', 'alert-info') and contains(@invisible, 'invoice_has_outstanding')]"
        ):
            for move_type, fragment in OUTSTANDING_ALERT_MOVE_TYPES.items():
                if fragment in div.get("invisible"):
                    alerts[move_type].append(div)
        return arch, alerts

    def _assert_one_igtf_alert_per_move_type(self, alerts):
        for move_type, divs in alerts.items():
            with self.subTest(move_type=move_type):
                self.assertEqual(len(divs), 1, "Debe haber un único aviso de pendientes por tipo.")
                advance_links = divs[0].xpath(
                    ".//a[contains(@invisible, 'invoice_outstanding_credits_debits_widget_advance_payment')]"
                )
                self.assertTrue(advance_links, "El aviso debe ser el de IGTF, con el enlace de anticipos.")

    def test_one_igtf_alert_per_move_type(self):
        """Sin otros avisos: cada tipo (factura y nota de crédito, de cliente y de proveedor) tiene su
        aviso IGTF. Con el `[3]` repetido, la NC de cliente quedaba sin aviso y la de proveedor, con dos."""
        _arch, alerts = self._outstanding_alerts()
        self._assert_one_igtf_alert_per_move_type(alerts)

    def test_alerts_survive_shifted_positions(self):
        """Un módulo que agrega un `alert-info` después del header y se aplica antes que IGTF (como los
        avisos de tasa de `binaural_purchase` y `l10n_ve_sale`) no debe cambiar qué aviso reemplaza
        IGTF, y su aviso debe seguir en el formulario."""
        self.env["ir.ui.view"].create(
            {
                "name": "test.account.move.shifted.alert",
                "model": "account.move",
                "inherit_id": self.env.ref("account.view_move_form").id,
                "priority": 1,
                "arch": """
                    <xpath expr="//header" position="after">
                        <div class="alert alert-info mb-0" role="alert" name="test_shifted_alert"
                             invisible="move_type != 'in_invoice'">Shifted alert</div>
                    </xpath>
                """,
            }
        )
        arch, alerts = self._outstanding_alerts()
        self._assert_one_igtf_alert_per_move_type(alerts)
        self.assertTrue(
            arch.xpath("//div[@name='test_shifted_alert']"), "El aviso del otro módulo debe seguir en el formulario."
        )
