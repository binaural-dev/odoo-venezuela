from lxml import etree

from odoo.tests import TransactionCase, tagged

# Condición `invisible` del núcleo de cada alerta de "créditos/débitos pendientes": identifica la alerta
# sin depender de su posición en el formulario.
CORE_ALERT_MARKERS = {
    "out_invoice": "'out_invoice', 'out_receipt'",
    "in_invoice": "'in_invoice', 'in_receipt'",
    "out_refund": "move_type != 'out_refund'",
    "in_refund": "move_type != 'in_refund'",
}
FOREIGN_ALERT_TEXT = "FOREIGN_MODULE_ALERT"


@tagged("igtf_account_move_alert_views", "-at_install", "post_install")
class TestAccountMoveAlertViews(TransactionCase):
    """Las alertas de anticipos de IGTF reemplazan las del núcleo sin depender de su posición.

    `l10n_ve_igtf` reemplazaba las cuatro alertas de "créditos/débitos pendientes" del núcleo con
    `//div[hasclass('alert', 'alert-info')][N]`. Cualquier módulo que agregue un `alert-info` antes de
    ellas corría el índice: su aviso se perdía y las variantes de IGTF caían en el div equivocado (con
    `l10n_ve_sale` se perdía el aviso "usa la tasa de la orden"). No es una relación directa entre los
    módulos: la prueba crea la vista de un tercero que inserta su aviso donde lo hace `l10n_ve_sale`
    (hija de la vista de `l10n_ve_accountant`, que se aplica antes que la de IGTF)."""

    def setUp(self):
        super().setUp()
        self.env["ir.ui.view"].create({
            "name": "test.alert.before.core.alerts",
            "model": "account.move",
            "type": "form",
            "inherit_id": self.env.ref("l10n_ve_accountant.view_account_move_form_l10n_ve_accountant").id,
            "arch": (
                "<data><xpath expr=\"//header\" position=\"after\">"
                "<div class=\"alert alert-info mb-0\" role=\"alert\" invisible=\"not id\">%s</div>"
                "</xpath></data>" % FOREIGN_ALERT_TEXT
            ),
        })
        arch = self.env["account.move"].get_view(view_type="form")["arch"]
        self.tree = etree.fromstring(arch)

    def _alert_divs(self):
        return self.tree.xpath("//div[contains(@class, 'alert-info')]")

    def test_foreign_alert_survives(self):
        """El aviso de otro módulo, antes de las alertas del núcleo, no lo reemplaza IGTF."""
        foreign = [div for div in self._alert_divs() if FOREIGN_ALERT_TEXT in (div.text or "")]
        self.assertEqual(len(foreign), 1, "El aviso insertado por otro módulo debe seguir en la vista.")

    def test_each_outstanding_alert_is_replaced_once_by_igtf(self):
        """Cada alerta del núcleo (factura y nota de crédito, de cliente y de proveedor) queda reemplazada
        una sola vez, por la variante de IGTF que menciona los anticipos."""
        outstanding = [
            div for div in self._alert_divs() if "invoice_has_outstanding" in (div.get("invisible") or "")
        ]
        self.assertEqual(len(outstanding), len(CORE_ALERT_MARKERS))
        for move_kind, marker in CORE_ALERT_MARKERS.items():
            matching = [div for div in outstanding if marker in div.get("invisible")]
            self.assertEqual(len(matching), 1, "Una sola alerta de %s." % move_kind)
            text = " ".join(matching[0].xpath("string()").split())
            self.assertIn("advances", text, "La alerta de %s debe ser la variante de IGTF." % move_kind)
